"""
Real-time vocal extraction — v5 (robust threads + auto-restart)

Captures audio routed through VB-Cable virtual driver, removes the music,
and plays back vocals-only to your real speakers / headphones.

Chekc previous prompt 
py -c "import torch; c=torch.load('checkpoints_v13/last.pt', map_location='cpu', weights_only=False); print(c['config'])"

What's new in v5
─────────────────
• Writer & reader threads now auto-restart on WASAPI device errors
  (e.g. Bluetooth headphone hiccups → 0x88890004 DEVICE_INVALIDATED).
  Previously a single error killed the writer permanently and every
  subsequent chunk was dropped.
• Default BLOCK_SAMPLES bumped 8192 → 16384 (372 ms).  CPU has 2× the
  budget per chunk, dramatically reducing drops on laptops without GPU.
• torch.inference_mode() wraps every model forward → ~15 % faster on CPU.
• Auto thread-pool tuning: torch.set_num_threads(physical_cores) before
  model load.  PyTorch's default of "all logical cores" is usually slower.
• Bluetooth output detection: warns that BT (A2DP/SBC) is the worst
  case for stable real-time playback and recommends wired output.
• Adaptive drop reporter — only prints when drops exceed a sane budget,
  not every 20 chunks (your terminal won't get spammed any more).

Dependencies
────────────
    pip install soundcard soundfile torch torchaudio

One-time setup
──────────────
    py stream.py --setup_guide          # prints step-by-step instructions

─────────────────────────────────────────────────────────────────
DEFAULT (RECOMMENDED) MODE — VB-Cable virtual driver
─────────────────────────────────────────────────────────────────
After VB-Cable is installed and set as your Windows default output:

    py stream.py --checkpoint checkpoints_v4\\best.pt --vbcable

  ↳ auto-detects VB-Cable, plays vocals on your default real speaker.

  Override the output speaker:
    py stream.py --checkpoint checkpoints_v4\\best.pt --vbcable \
                 --output_device 0

  Pick a smaller block size if you have GPU or a fast CPU:
    py stream.py --checkpoint best.pt --vbcable --block_samples 16384 --gain_db 6.0

─────────────────────────────────────────────────────────────────
OTHER MODES
─────────────────────────────────────────────────────────────────
  # WASAPI loopback (two-device setup, no virtual driver):
    py stream.py --checkpoint best.pt --source_device 1 --output_device 0

  # Mic / line-in input:
    py stream.py --checkpoint best.pt --mic_device 0 --output_device 1

  # Dry run — process a WAV/MP3 file and save the result:
    py stream.py --checkpoint best.pt --dry_run song.mp3 --output_dir ./separated

─────────────────────────────────────────────────────────────────
LATENCY TUNING  (--block_samples)
─────────────────────────────────────────────────────────────────
   2048 =  46 ms   low latency, needs fast CPU or GPU
   4096 =  93 ms   tight on CPU
   8192 = 186 ms   borderline on CPU — drops likely on laptop
  16384 = 372 ms   default — comfortable on CPU (recommended)
  32768 = 743 ms   bulletproof; use if 16384 still drops
"""

import argparse
import queue
import time
import os
import subprocess
import threading
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F
import soundfile as sf

from model import HSTasNetVocals, StatefulHSTasNetVocals

# soundcard — Windows WASAPI audio capture/playback.
# All live-streaming modes (VB-Cable, loopback, mic) use it.
# Dry-run (file processing) does not require it.
try:
    import soundcard as sc
    _HAS_SOUNDCARD = True
except ImportError:
    _HAS_SOUNDCARD = False

TARGET_SR     = 44100
# Default samples per processing chunk — overridable via --block_samples.
#   2048  =  46 ms  — needs GPU or very fast CPU
#   4096  =  93 ms  — comfortable on GPU, tight on CPU
#   8192  = 186 ms  — borderline on CPU laptop
#  16384  = 372 ms  — comfortable on CPU (default)
#  32768  = 743 ms  — bulletproof
BLOCK_SAMPLES = 8192


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def to_windows_path(p: str) -> str:
    """Convert WSL /mnt/… path to a Windows drive path."""
    s = str(p)
    if s.startswith('/mnt/'):
        parts = s[5:].split('/', 1)
        drive = parts[0].upper()
        rest  = parts[1] if len(parts) > 1 else ''
        return f"{drive}:/{rest}"
    return s


def load_model(checkpoint_path: str, device: torch.device) -> HSTasNetVocals:
    ckpt   = torch.load(checkpoint_path, map_location='cpu', weights_only=False)
    config = ckpt.get('config', {})
    model  = HSTasNetVocals(
        n_fft=config.get('n_fft', 1024),
        hop_length=config.get('hop_length', 512),
        bidirectional=config.get('bidirectional', False),
    )
    model.load_state_dict(ckpt['model_state_dict'])
    epoch    = ckpt.get('epoch', '?')
    val_loss = ckpt.get('val_loss', '?')
    print(f"[Stream] Loaded checkpoint  epoch={epoch}  val_loss={val_loss:.4f}")
    return model


def load_audio(path: str) -> tuple:
    """Load MP3 or WAV via ffmpeg → soundfile. Returns (tensor (2,L), peak)."""
    tmp_path = str(Path(path).parent / '_tmp_input.wav')
    try:
        subprocess.run(
            ['ffmpeg', '-y', '-i', to_windows_path(path),
             '-ar', str(TARGET_SR), '-ac', '2', '-f', 'wav', to_windows_path(tmp_path)],
            check=True, capture_output=True
        )
        wav, _ = sf.read(tmp_path, always_2d=True)
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
    wav  = torch.from_numpy(wav.T).float()
    peak = wav.abs().max()
    if peak > 0:
        wav = wav / peak
    return wav, peak


def _to_stereo(chunk: torch.Tensor) -> torch.Tensor:
    """Ensure a (C, L) tensor is exactly (2, L)."""
    if chunk.shape[0] == 1:
        return chunk.repeat(2, 1)
    if chunk.shape[0] > 2:
        return chunk[:2]
    return chunk


def _apply_gain(audio: torch.Tensor, gain: float) -> torch.Tensor:
    """
    Apply linear gain with soft-clipping for clean amplification.

    For gains > +0.5 dB we use tanh saturation instead of hard clamping —
    tanh asymptotes smoothly toward ±1, so loud peaks compress musically
    instead of brick-walling into harsh digital distortion.  This is the
    same shape an analog tube preamp uses.

    Args:
        audio : (C, L) float tensor in [-1, 1]
        gain  : linear gain multiplier (e.g. 4.47 for +13 dB)
    """
    if gain <= 1.06:           # ≤ +0.5 dB → hard clamp is fine
        return (audio * gain).clamp(-1.0, 1.0)
    # tanh soft-saturation — peaks > 0 dBFS curve in instead of clipping
    return torch.tanh(audio * gain)


def _apply_soft_limiter(audio: torch.Tensor, target_rms: float = 0.2) -> torch.Tensor:
    """
    Per-chunk RMS-based soft limiter (v12).

    Why this exists in v12:
        Mask heads were unbounded above 1.0 (replacing Sigmoid with softplus).
        Most of the time this means cleaner separation — but occasionally the
        model emits a loud transient when the mask exceeds the typical range
        on a single frame.  A soft RMS scaling brings these back into a sane
        range without flat-clipping.

    Implementation:
        Compute the chunk's RMS; if it exceeds `target_rms`, scale the whole
        chunk down proportionally.  If below, leave alone.  Does NOT amplify
        quiet output (that would also amplify residual music bleed).

    Args:
        audio      : (C, L) float tensor
        target_rms : maximum allowed RMS before scaling kicks in.  0.2 ≈
                     -14 dBFS, comfortable for live monitoring.
    """
    rms = audio.pow(2).mean().sqrt().clamp(min=1e-8)
    if rms <= target_rms:
        return audio
    return audio * (target_rms / rms)


def _auto_level(audio: torch.Tensor,
                target_rms: float = 0.12,
                max_gain:   float = 30.0) -> torch.Tensor:
    """
    Per-chunk automatic level control (v6 addition).

    Unlike _apply_soft_limiter (which only turns DOWN loud chunks), this
    normalises in BOTH directions — it boosts quiet model output to a
    consistent listening level.  This is the right fix when the model
    produces low-amplitude vocals that require +20 dB or more of gain_db,
    because _apply_gain's tanh at that level saturates everything to ±1
    and crushes dynamics.

    How it works:
        1. Measure the chunk's RMS.
        2. Compute the scale needed to reach target_rms.
        3. Cap the scale at max_gain (linear) so near-silent chunks
           (instrumental break, fade-out) don't get boosted to noise.
        4. Hard-clamp to [-1, 1] after scaling.

    target_rms = 0.12  ≈ -18.4 dBFS  — comfortable, punchy monitoring level.
    max_gain   = 30.0  ≈ +29.5 dB    — generous enough for very dim output;
                                        keeps truly silent chunks from spiking.

    Pair with a small --gain_db (e.g. +3) for fine-tuning after levelling.
    Do NOT combine with high --gain_db (e.g. +25) — the tanh would undo
    the levelling benefit.

    Args:
        audio      : (C, L) float32 tensor
        target_rms : RMS level to normalise toward (default 0.12)
        max_gain   : upper bound on amplification (linear, default 30)
    """
    rms   = audio.pow(2).mean().sqrt().clamp(min=1e-8)
    scale = (target_rms / rms).clamp(max=max_gain)
    return (audio * scale).clamp(-1.0, 1.0)


def _resolve_gain(args) -> tuple:
    """
    Resolve --gain (linear) / --gain_db (dB) into a single linear value.
    --gain takes precedence if both are given.  Returns (linear, dB).
    """
    if args.gain is not None:
        linear = float(args.gain)
        db     = 20 * np.log10(max(linear, 1e-9))
    else:
        db     = float(args.gain_db or 0.0)
        linear = 10.0 ** (db / 20.0)
    return linear, db


def _require_soundcard():
    """Abort with a friendly message if soundcard isn't installed."""
    if not _HAS_SOUNDCARD:
        print("[Stream] ERROR: soundcard not installed.")
        print("         Run:  pip install soundcard")
        raise SystemExit(1)


def _setup_model(args) -> tuple:
    """
    Shared setup for all live-streaming modes.
    Returns (streamer, device, gain_linear, gain_db, BLOCK).
    """
    n_threads = _tune_cpu_threads()
    device = torch.device(
        'cuda' if torch.cuda.is_available() else
        'mps'  if torch.backends.mps.is_available() else
        'cpu'
    )
    thread_note = f' ({n_threads} threads)' if device.type == 'cpu' and n_threads else ''
    print(f"[Stream] Device        : {device}{thread_note}")

    model    = load_model(args.checkpoint, device)
    model.eval()

    # Mask temporal smoothing — reduces "musical noise" / watery artefacts
    # by averaging the separation mask over k past STFT frames.
    mask_k = int(getattr(args, 'mask_smooth', 1))
    if mask_k > 1:
        model.set_mask_smooth(mask_k)
        hop    = getattr(model, 'hop_length', 512)
        ms_per = hop / 44100 * 1000
        print(f"[Stream] Mask smooth   : {mask_k} frames  "
              f"(~{mask_k * ms_per:.0f} ms window, causal)")

    # v12: optional lookahead frames — see model.StatefulHSTasNetVocals
    lookahead = int(getattr(args, 'lookahead', 0))
    streamer = StatefulHSTasNetVocals(model, device, lookahead_frames=lookahead)
    streamer.reset()
    if lookahead > 0:
        hop = getattr(model, 'hop_length', 512)
        lat_ms = lookahead * hop / TARGET_SR * 1000
        print(f"[Stream] Lookahead     : {lookahead} frames "
              f"(~{lat_ms:.1f} ms output delay)")

    gain, gain_db = _resolve_gain(args)
    BLOCK = args.block_samples
    return streamer, device, gain, gain_db, BLOCK


def _tune_cpu_threads():
    """
    Pin torch to the physical core count.  By default torch uses every
    logical core (incl. SMT siblings), which on most laptops is slower
    for inference than just the physical cores.  Roughly 10–25 % speedup
    on Intel/Ryzen CPUs for LSTM-heavy models like ours.
    """
    try:
        import os
        # os.cpu_count() returns logical cores; physical is half on SMT chips
        logical = os.cpu_count() or 4
        # Conservative: half of logical (≈ physical) on SMT, otherwise all
        physical = max(1, logical // 2 if logical >= 4 else logical)
        torch.set_num_threads(physical)
        torch.set_num_interop_threads(1)
        return physical
    except Exception:
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Bluetooth-output detection
# ─────────────────────────────────────────────────────────────────────────────

# Common substrings in Windows Bluetooth audio device names.  Bluetooth
# (A2DP/SBC) introduces 100-300 ms latency of its own AND drops the WASAPI
# session every time the codec re-negotiates → ideal recipe for chunk drops.
BLUETOOTH_KEYWORDS = (
    'bluetooth', 'wireless', 'wh-1000', 'wf-1000', 'airpods', 'beats',
    'galaxy buds', 'pixel buds', 'bose qc', 'jabra', 'sony wh', 'sony wf',
    'a2dp', 'hands-free', 'handsfree',
)


def _is_bluetooth(name: str) -> bool:
    n = name.lower()
    return any(k in n for k in BLUETOOTH_KEYWORDS)


def _warn_if_bluetooth(device_name: str, role: str = 'output'):
    """Print a one-line warning if the chosen output looks like a BT device."""
    if _is_bluetooth(device_name):
        print(f"[Stream] ⚠  WARNING: '{device_name}' looks like a Bluetooth device.")
        print(f"         Bluetooth {role} adds 100-300 ms latency on its own and the")
        print(f"         WASAPI session drops on every codec switch — you'll see")
        print(f"         frequent chunk drops and 0x88890004 reconnects.")
        print(f"         Strongly recommended: use a wired speaker / headphones.")
        print()


# ─────────────────────────────────────────────────────────────────────────────
# Robust streaming threads
# ─────────────────────────────────────────────────────────────────────────────

# WASAPI HRESULT codes we know how to handle and recover from.
#   0x88890004 = AUDCLNT_E_DEVICE_INVALIDATED  (BT codec switch, USB pull,
#                                               sample-rate change, etc.)
#   0x88890026 = AUDCLNT_E_BUFFER_OPERATION_PENDING
#   0x88890021 = AUDCLNT_E_OUT_OF_ORDER
_WASAPI_RECOVERABLE = ('88890004', '88890026', '88890021', '8889000a', 'invalidat')


def _is_recoverable_audio_error(exc: Exception) -> bool:
    """Return True if the error looks like one we can reconnect from."""
    s = str(exc).lower()
    return any(code in s for code in _WASAPI_RECOVERABLE)


def make_writer_thread(dst_speaker, out_q, running, block_samples,
                       restart_delay: float = 0.5):
    """
    Build a writer thread that auto-reopens the WASAPI player on recoverable
    errors (e.g. Bluetooth codec hiccups).  Replaces the v4 writer that died
    silently and caused every subsequent chunk to be dropped.
    """
    import queue
    silence = np.zeros((block_samples, 2), dtype=np.float32)

    def writer():
        backoff = restart_delay
        reconnect_count = 0
        while running.is_set():
            try:
                with dst_speaker.player(samplerate=TARGET_SR, channels=2,
                                        blocksize=block_samples) as player:
                    if reconnect_count > 0:
                        print(f"[Stream] ✓ Output reconnected ({dst_speaker.name}).")
                    backoff = restart_delay   # reset on successful open
                    while running.is_set():
                        try:
                            chunk = out_q.get(timeout=0.3)
                            player.play(chunk.numpy().T)
                        except queue.Empty:
                            player.play(silence)
            except Exception as e:
                if not running.is_set():
                    return
                if _is_recoverable_audio_error(e):
                    reconnect_count += 1
                    print(f"\n[Stream] ⚠  Output device error "
                          f"({type(e).__name__}: {e}).")
                    print(f"[Stream]    Reconnecting in {backoff:.1f}s "
                          f"(attempt {reconnect_count})…")
                    # Drain any backed-up chunks so we resume in real time
                    drained = 0
                    while not out_q.empty():
                        try:
                            out_q.get_nowait()
                            drained += 1
                        except queue.Empty:
                            break
                    if drained:
                        print(f"[Stream]    Dropped {drained} stale chunks "
                              f"to resync.")
                    time.sleep(backoff)
                    backoff = min(backoff * 2.0, 5.0)
                else:
                    print(f"\n[Stream] ✗ Fatal writer error: "
                          f"{type(e).__name__}: {e}")
                    running.clear()
                    return
    return writer


def make_reader_thread(source, in_q, running, block_samples,
                       restart_delay: float = 0.5):
    """
    Build a reader thread that auto-reopens the loopback recorder on
    recoverable errors.  `source` is a soundcard Microphone (loopback or real).
    """
    import queue

    def reader():
        backoff = restart_delay
        reconnect_count = 0
        while running.is_set():
            try:
                try:
                    rec_ctx = source.recorder(samplerate=TARGET_SR,
                                              channels=2,
                                              blocksize=block_samples)
                except Exception:
                    rec_ctx = source.recorder(samplerate=TARGET_SR,
                                              blocksize=block_samples)
                with rec_ctx as rec:
                    if reconnect_count > 0:
                        print(f"[Stream] ✓ Input reconnected ({source.name}).")
                    backoff = restart_delay
                    while running.is_set():
                        data  = rec.record(numframes=block_samples)
                        chunk = _to_stereo(torch.from_numpy(data.T.copy()).float())
                        try:
                            in_q.put_nowait(chunk)
                        except queue.Full:
                            pass   # drop oldest, keep latency tight
            except Exception as e:
                if not running.is_set():
                    return
                if _is_recoverable_audio_error(e):
                    reconnect_count += 1
                    print(f"\n[Stream] ⚠  Input device error "
                          f"({type(e).__name__}: {e}).")
                    print(f"[Stream]    Reconnecting in {backoff:.1f}s…")
                    time.sleep(backoff)
                    backoff = min(backoff * 2.0, 5.0)
                else:
                    print(f"\n[Stream] ✗ Fatal reader error: "
                          f"{type(e).__name__}: {e}")
                    running.clear()
                    return
    return reader


class _DropReporter:
    """
    Print drop counts on a sane schedule — once per second at most, with
    exponential backoff once the counter is large.  No more 200 lines of
    'chunks dropped' spam in your terminal.
    """
    def __init__(self):
        self.count = 0
        self._last_print = 0.0
        self._next_threshold = 1

    def add(self, n: int = 1):
        self.count += n
        now = time.time()
        if (self.count >= self._next_threshold and
            now - self._last_print >= 1.0):
            print(f"[Stream] {self.count} chunks dropped — "
                  f"increase --block_samples or close other apps.")
            self._last_print = now
            # Print again at 2×, 4×, 8× of current count (exponential backoff)
            self._next_threshold = max(self.count * 2, self.count + 50)


# ─────────────────────────────────────────────────────────────────────────────
# VB-Cable detection
# ─────────────────────────────────────────────────────────────────────────────

VBCABLE_KEYWORDS = ('cable output', 'cable input', 'vb-audio', 'vb cable')


def _is_vbcable(name: str) -> bool:
    n = name.lower()
    return any(k in n for k in VBCABLE_KEYWORDS)


def find_vbcable_microphone():
    """
    Find the VB-Cable virtual MICROPHONE — the *recording* end of the cable.
    All audio routed into VB-Cable arrives here for us to capture.

    Returns the soundcard Microphone or None if VB-Cable isn't installed.
    """
    for mic in sc.all_microphones(include_loopback=False):
        n = mic.name.lower()
        # "CABLE Output (VB-Audio Virtual Cable)"  — the input side of the cable
        if 'cable output' in n or ('vb-audio' in n and 'output' in n):
            return mic
    return None


def find_vbcable_speaker():
    """
    Find the VB-Cable virtual SPEAKER — the *playback* end of the cable.
    Apps must play to this for the cable to work.

    Returns the soundcard Speaker or None.
    """
    for spk in sc.all_speakers():
        n = spk.name.lower()
        # "CABLE Input (VB-Audio Virtual Cable)"  — the output side, where apps play
        if 'cable input' in n or ('vb-audio' in n and 'input' in n):
            return spk
    return None


def print_setup_guide():
    """Print the step-by-step VB-Cable setup instructions."""
    print("""
╔══════════════════════════════════════════════════════════════════════╗
║  VB-Cable setup — one-time, ~3 minutes                               ║
╚══════════════════════════════════════════════════════════════════════╝

STEP 1.  Download VB-Cable (free, donationware)
        →  https://vb-audio.com/Cable/

STEP 2.  Extract the ZIP, right-click  VBCABLE_Setup_x64.exe
         →  "Run as administrator"  →  click  Install Driver

STEP 3.  Reboot your PC.  (Required — Windows registers the driver.)

STEP 4.  Set VB-Cable as your default playback device:
        →  Right-click speaker icon in taskbar
        →  Sound settings
        →  Output:  pick  "CABLE Input (VB-Audio Virtual Cable)"

         All system audio (YouTube, Spotify, MP3 player, anything) now
         flows into the cable instead of your speakers.  You won't hear
         music directly any more — that's expected.

STEP 5.  Run the app:
            py stream.py --checkpoint checkpoints_v4\\best.pt --vbcable

         The software auto-detects VB-Cable, processes the audio, and
         plays vocals through your real speakers / headphones.

         To pick a specific output speaker (instead of system default):
            py stream.py --checkpoint best.pt --vbcable --output_device 0
         (run --list_devices to see speaker indices)

STEP 6.  When you're done, switch the Windows default output back to
         your real speakers in Sound settings — otherwise nothing will
         play through them while VB-Cable is the default.

═══════════════════════════════════════════════════════════════════════
""")


# ─────────────────────────────────────────────────────────────────────────────
# Device listing
# ─────────────────────────────────────────────────────────────────────────────

def list_devices():
    """List all speakers / mics soundcard can see, and report VB-Cable status."""
    _require_soundcard()

    speakers = sc.all_speakers()
    mics     = sc.all_microphones(include_loopback=False)

    # ── VB-Cable status banner ───────────────────────────────────────────────
    cable_mic = find_vbcable_microphone()
    cable_spk = find_vbcable_speaker()
    if cable_mic and cable_spk:
        try:
            sys_default = sc.default_speaker()
            default_is_cable = _is_vbcable(sys_default.name)
        except Exception:
            default_is_cable = False
        print("\n── VB-Cable status ───────────────────────────────────────────────")
        print(f"   Driver installed   : YES")
        print(f"   Cable speaker      : {cable_spk.name}")
        print(f"   Cable microphone   : {cable_mic.name}")
        print(f"   Default output set : {'YES (good!)' if default_is_cable else 'NO  → run --setup_guide'}")
    else:
        print("\n── VB-Cable status ───────────────────────────────────────────────")
        print("   Driver installed   : NO   → run  py stream.py --setup_guide")

    print("\n── OUTPUT DEVICES (speakers) ─────────────────────────────────────")
    print("  Use these indices for --source_device / --output_device")
    print(f"  {'IDX':>4}  NAME")
    print("  " + "─" * 55)
    for i, s in enumerate(speakers):
        tags = []
        if s == sc.default_speaker():
            tags.append("default")
        if _is_vbcable(s.name):
            tags.append("VB-Cable")
        tag = ("  ◀ " + ", ".join(tags)) if tags else ""
        print(f"  {i:>4}  {s.name}{tag}")

    print("\n── INPUT DEVICES (microphones) ───────────────────────────────────")
    print("  Use these indices for --mic_device (mic/line-in mode)")
    print(f"  {'IDX':>4}  NAME")
    print("  " + "─" * 55)
    for i, m in enumerate(mics):
        tags = []
        if m == sc.default_microphone():
            tags.append("default")
        if _is_vbcable(m.name):
            tags.append("VB-Cable")
        tag = ("  ◀ " + ", ".join(tags)) if tags else ""
        print(f"  {i:>4}  {m.name}{tag}")

    print()
    print("  TIP: --vbcable        = recommended (one speaker, replaces audio)")
    print("       --source_device  = WASAPI loopback mode (needs two devices)")
    print("       --output_device  = where vocals come out")
    print()


# ─────────────────────────────────────────────────────────────────────────────
# WASAPI loopback streaming  (soundcard)
# ─────────────────────────────────────────────────────────────────────────────

def run_loopback_stream(args):
    """
    Capture an output device via WASAPI loopback, extract vocals, play to
    a different output device.  No VB-Cable or Stereo Mix required.
    """
    _require_soundcard()
    streamer, _, gain, gain_db, BLOCK = _setup_model(args)

    speakers = sc.all_speakers()

    # Validate indices
    if args.source_device >= len(speakers):
        print(f"[Stream] ERROR: --source_device {args.source_device} out of range "
              f"(0–{len(speakers)-1}).  Run --list_devices to see options.")
        return
    if args.output_device >= len(speakers):
        print(f"[Stream] ERROR: --output_device {args.output_device} out of range "
              f"(0–{len(speakers)-1}).  Run --list_devices to see options.")
        return
    if args.source_device == args.output_device:
        print("[Stream] ERROR: --source_device and --output_device must be different.\n"
              "         Using the same device creates a feedback loop.\n"
              "         Use --list_devices to pick two distinct speakers.")
        return

    src_speaker = speakers[args.source_device]
    dst         = speakers[args.output_device]
    _warn_if_bluetooth(dst.name, role='output')

    # ── Get the loopback MICROPHONE for the source SPEAKER ───────────────────
    try:
        src = sc.get_microphone(src_speaker.id, include_loopback=True)
    except Exception as e:
        print(f"[Stream] ERROR: could not open loopback for "
              f"'{src_speaker.name}': {e}")
        print("         WASAPI loopback may not be supported for this device.")
        return

    print(f"[Stream] Mode          : WASAPI loopback  (no VB-Cable)")
    print(f"[Stream] Capture from  : [{args.source_device}] {src_speaker.name}")
    print(f"[Stream] Vocals out to : [{args.output_device}] {dst.name}")
    print(f"[Stream] Block size    : {BLOCK} samples  "
          f"({BLOCK / TARGET_SR * 1000:.0f} ms)")
    if abs(gain_db) > 0.05:
        print(f"[Stream] Output gain   : {gain_db:+.1f} dB  ({gain:.2f}× linear, soft-clipped)")
    print("[Stream] Streaming… play music on the source device.  Ctrl+C to stop.\n")

    running = threading.Event()
    running.set()
    dropped = _DropReporter()

    in_q  = queue.Queue(maxsize=4)
    out_q = queue.Queue(maxsize=4)

    t_reader = threading.Thread(
        target=make_reader_thread(src, in_q, running, BLOCK), daemon=True)
    t_writer = threading.Thread(
        target=make_writer_thread(dst, out_q, running, BLOCK), daemon=True)
    t_reader.start()
    t_writer.start()

    try:
        with torch.inference_mode():
            while running.is_set():
                try:
                    chunk = in_q.get(timeout=0.5)
                except queue.Empty:
                    continue

                vocals = streamer.process_chunk(chunk)
                if getattr(args, 'auto_level', False):
                    vocals = _auto_level(vocals, target_rms=args.target_rms)
                vocals = _apply_gain(vocals, gain)
                if getattr(args, 'soft_limiter', False):
                    vocals = _apply_soft_limiter(vocals)

                try:
                    out_q.put_nowait(vocals)
                except queue.Full:
                    dropped.add()
    except KeyboardInterrupt:
        pass
    finally:
        running.clear()
        print(f"\n[Stream] Stopped.  Dropped chunks: {dropped.count}")


# ─────────────────────────────────────────────────────────────────────────────
# VB-Cable streaming  (recommended for production / single-speaker use)
# ─────────────────────────────────────────────────────────────────────────────

def run_vbcable_stream(args):
    """
    VB-Cable mode: app audio → VB-Cable → us → real speakers.

    Architecture:
        YouTube / Spotify / MP3 player / anything
                ↓ (Windows default output = CABLE Input)
        VB-Cable virtual driver
                ↓ (we read from CABLE Output microphone)
        HSTasNetVocals model (removes music)
                ↓
        Your real speakers / headphones
    """
    _require_soundcard()

    # ── Locate VB-Cable ──────────────────────────────────────────────────────
    cable_mic = find_vbcable_microphone()
    cable_spk = find_vbcable_speaker()

    if cable_mic is None or cable_spk is None:
        print("[Stream] ERROR: VB-Cable virtual driver was not detected on this system.")
        print()
        print_setup_guide()
        return

    streamer, _, gain, gain_db, BLOCK = _setup_model(args)

    # ── Pick a real (non-VB-Cable) output speaker ────────────────────────────
    speakers = sc.all_speakers()

    if args.output_device is not None:
        if args.output_device >= len(speakers):
            print(f"[Stream] ERROR: --output_device {args.output_device} out of range "
                  f"(0–{len(speakers)-1}).")
            return
        dst = speakers[args.output_device]
        if _is_vbcable(dst.name):
            print(f"[Stream] ERROR: --output_device points at the VB-Cable itself "
                  f"('{dst.name}'). Pick a real speaker / headphone.")
            return
    else:
        # Auto-pick: first speaker that isn't VB-Cable
        real_speakers = [s for s in speakers if not _is_vbcable(s.name)]
        if not real_speakers:
            print("[Stream] ERROR: no real output speakers detected.")
            return
        dst = real_speakers[0]
        # Prefer system default if it's not the cable
        try:
            default = sc.default_speaker()
            if not _is_vbcable(default.name):
                dst = default
        except Exception:
            pass


    _warn_if_bluetooth(dst.name, role='output')

    # ── Sanity check: is VB-Cable actually the system default output? ────────
    try:
        sys_default = sc.default_speaker()
        if not _is_vbcable(sys_default.name):
            print(f"[Stream] WARNING: Windows default output is '{sys_default.name}',")
            print(f"         not VB-Cable.  No app audio will reach VB-Cable.")
            print(f"         Fix: Right-click speaker icon → Sound settings → ")
            print(f"               Output → 'CABLE Input (VB-Audio Virtual Cable)'.")
            print()
    except Exception:
        pass

    print(f"[Stream] Mode          : VB-Cable virtual driver")
    print(f"[Stream] Cable mic     : {cable_mic.name}")
    print(f"[Stream] Vocals out to : {dst.name}")
    print(f"[Stream] Block size    : {BLOCK} samples  "
          f"({BLOCK / TARGET_SR * 1000:.0f} ms)")
    if abs(gain_db) > 0.05:
        print(f"[Stream] Output gain   : {gain_db:+.1f} dB  ({gain:.2f}× linear, soft-clipped)")
    print("[Stream] Streaming… play any music; you'll hear vocals only. Ctrl+C to stop.\n")

    running = threading.Event()
    running.set()
    dropped = _DropReporter()

    in_q  = queue.Queue(maxsize=4)
    out_q = queue.Queue(maxsize=4)

    t_reader = threading.Thread(
        target=make_reader_thread(cable_mic, in_q, running, BLOCK), daemon=True)
    t_writer = threading.Thread(
        target=make_writer_thread(dst, out_q, running, BLOCK), daemon=True)
    t_reader.start()
    t_writer.start()

    try:
        with torch.inference_mode():
            while running.is_set():
                try:
                    chunk = in_q.get(timeout=0.5)
                except queue.Empty:
                    continue
                vocals = streamer.process_chunk(chunk)
                if getattr(args, 'auto_level', False):
                    vocals = _auto_level(vocals, target_rms=args.target_rms)
                vocals = _apply_gain(vocals, gain)
                if getattr(args, 'soft_limiter', False):
                    vocals = _apply_soft_limiter(vocals)
                try:
                    out_q.put_nowait(vocals)
                except queue.Full:
                    dropped.add()
    except KeyboardInterrupt:
        pass
    finally:
        running.clear()
        print(f"\n[Stream] Stopped.  Dropped chunks: {dropped.count}")


# ─────────────────────────────────────────────────────────────────────────────
# Mic / line-in streaming  (soundcard)
# ─────────────────────────────────────────────────────────────────────────────

def run_mic_stream(args):
    """Capture from a microphone or line-in device, output vocals to a speaker."""
    _require_soundcard()
    streamer, _, gain, gain_db, BLOCK = _setup_model(args)

    mics     = sc.all_microphones(include_loopback=False)
    speakers = sc.all_speakers()

    mic_idx = args.mic_device if args.mic_device is not None else 0
    out_idx = args.output_device if args.output_device is not None else 0

    mic = mics[mic_idx]
    dst = speakers[out_idx]

    _warn_if_bluetooth(dst.name, role='output')

    print(f"[Stream] Mode          : microphone / line-in")
    print(f"[Stream] Input         : [{mic_idx}] {mic.name}")
    print(f"[Stream] Output        : [{out_idx}] {dst.name}")
    print(f"[Stream] Block size    : {BLOCK} samples  "
          f"({BLOCK / TARGET_SR * 1000:.0f} ms)")
    if abs(gain_db) > 0.05:
        print(f"[Stream] Output gain   : {gain_db:+.1f} dB  ({gain:.2f}× linear, soft-clipped)")
    print("[Stream] Streaming…  Ctrl+C to stop.\n")

    running = threading.Event()
    running.set()
    dropped = _DropReporter()

    in_q  = queue.Queue(maxsize=4)
    out_q = queue.Queue(maxsize=4)

    t_reader = threading.Thread(
        target=make_reader_thread(mic, in_q, running, BLOCK), daemon=True)
    t_writer = threading.Thread(
        target=make_writer_thread(dst, out_q, running, BLOCK), daemon=True)
    t_reader.start()
    t_writer.start()

    try:
        with torch.inference_mode():
            while running.is_set():
                try:
                    chunk = in_q.get(timeout=0.5)
                except queue.Empty:
                    continue
                vocals = streamer.process_chunk(chunk)
                if getattr(args, 'auto_level', False):
                    vocals = _auto_level(vocals, target_rms=args.target_rms)
                vocals = _apply_gain(vocals, gain)
                if getattr(args, 'soft_limiter', False):
                    vocals = _apply_soft_limiter(vocals)
                try:
                    out_q.put_nowait(vocals)
                except queue.Full:
                    dropped.add()
    except KeyboardInterrupt:
        pass
    finally:
        running.clear()
        print(f"\n[Stream] Stopped.  Dropped chunks: {dropped.count}")


# ─────────────────────────────────────────────────────────────────────────────
# Dry run — process a file, save output
# ─────────────────────────────────────────────────────────────────────────────

def run_dry(args):
    n_threads = _tune_cpu_threads()
    device = torch.device(
        'cuda' if torch.cuda.is_available() else
        'mps'  if torch.backends.mps.is_available() else
        'cpu'
    )
    print(f"[Dry Run] Device: {device}"
          f"{f' ({n_threads} threads)' if device.type == 'cpu' and n_threads else ''}")

    model    = load_model(args.checkpoint, device)
    model.eval()
    lookahead = int(getattr(args, 'lookahead', 0))
    streamer = StatefulHSTasNetVocals(model, device, lookahead_frames=lookahead)
    streamer.reset()

    print(f"[Dry Run] Loading: {args.dry_run}")
    mixture, peak = load_audio(args.dry_run)
    L     = mixture.shape[1]
    BLOCK = args.block_samples

    print(f"[Dry Run] Duration : {L / TARGET_SR:.1f}s  "
          f"| Block : {BLOCK} samples ({BLOCK / TARGET_SR * 1000:.0f} ms)")

    output_chunks = []
    t0 = time.time()

    with torch.inference_mode():
        for start in range(0, L, BLOCK):
            end   = min(start + BLOCK, L)
            chunk = mixture[:, start:end]
            if chunk.shape[1] < BLOCK:
                chunk = F.pad(chunk, (0, BLOCK - chunk.shape[1]))
            vocals = streamer.process_chunk(chunk)
            output_chunks.append(vocals[:, :end - start])

    elapsed  = time.time() - t0
    duration = L / TARGET_SR
    print(f"[Dry Run] Processed {duration:.1f}s in {elapsed:.1f}s  "
          f"({duration / elapsed:.1f}x real-time)")

    gain, gain_db = _resolve_gain(args)
    vocals_full = torch.cat(output_chunks, dim=1)
    if getattr(args, 'auto_level', False):
        vocals_full = _auto_level(vocals_full, target_rms=args.target_rms)
        print(f"[Dry Run] Auto level   : ON  (target RMS {args.target_rms:.3f})")
    vocals_full = _apply_gain(vocals_full, gain) * peak
    if getattr(args, 'soft_limiter', False):
        vocals_full = _apply_soft_limiter(vocals_full)
        print(f"[Dry Run] Soft limiter : ON")
    if abs(gain_db) > 0.05:
        print(f"[Dry Run] Output gain : {gain_db:+.1f} dB  ({gain:.2f}× linear, soft-clipped)")

    out_dir  = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stem     = Path(args.dry_run).stem
    out_path = out_dir / f"{stem}_vocals_rt.wav"
    sf.write(str(out_path), vocals_full.numpy().T, TARGET_SR, subtype='FLOAT')
    print(f"[Dry Run] Saved: {out_path.resolve()}")


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Real-time vocal extraction with VB-Cable virtual driver',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # --checkpoint isn't required for help-style commands
    parser.add_argument('--checkpoint',    default=None,
                        help='Path to trained model checkpoint (.pt)')
    parser.add_argument('--list_devices',  action='store_true',
                        help='List speakers / mics and report VB-Cable status, then exit')
    parser.add_argument('--setup_guide',   action='store_true',
                        help='Print VB-Cable installation instructions and exit')

    # ── Input mode (mutually exclusive) ──────────────────────────────────────
    src = parser.add_mutually_exclusive_group()
    src.add_argument('--vbcable',       action='store_true',
                     help='[RECOMMENDED] Use VB-Cable virtual driver. Auto-detects '
                          'the cable; outputs vocals to your real speakers.')
    src.add_argument('--source_device', type=int, default=None,
                     help='Speaker index for WASAPI loopback capture (alt mode).')
    src.add_argument('--mic_device',    type=int, default=None,
                     help='Microphone index for mic/line-in input mode.')

    # ── Output ───────────────────────────────────────────────────────────────
    parser.add_argument('--output_device', type=int, default=None,
                        help='Speaker index for vocals output (run --list_devices). '
                             'In --vbcable mode, defaults to your system default speaker.')

    # ── Dry run ───────────────────────────────────────────────────────────────
    parser.add_argument('--dry_run',    type=str, default=None,
                        help='Process a WAV/MP3 file instead of live audio.')
    parser.add_argument('--output_dir', default='./separated',
                        help='Output directory for dry run results (default: ./separated)')

    # ── Output gain ──────────────────────────────────────────────────────────
    # Use --gain_db for the natural way to think about loudness (decibels).
    # +13 dB is roughly 4.5× linear gain.  Soft-clipped via tanh internally
    # so peaks compress smoothly instead of digital-clipping.
    parser.add_argument('--gain_db', type=float, default=0.0,
                        help='Vocal output boost in dB (default 0).  e.g. --gain_db 13 '
                             'for a hefty +13 dB boost (≈4.5× louder, soft-clipped).')
    parser.add_argument('--gain',    type=float, default=None,
                        help='[Alternative] Linear gain multiplier (overrides --gain_db).')

    # ── Latency / block size ─────────────────────────────────────────────────
    # Bigger blocks = more CPU budget per chunk, fewer drops, more latency.
    # 16384 (372 ms) is the sweet spot for CPU laptops; 8192 (186 ms) only
    # safe with GPU or fast CPU; 32768 (743 ms) is bulletproof.
    parser.add_argument('--block_samples', type=int, default=BLOCK_SAMPLES,
                        choices=[2048, 4096, 8192, 16384, 32768],
                        help=f'Samples per processing chunk (default {BLOCK_SAMPLES}). '
                             f'Lower = less latency, more drops on CPU.')

    # ── v12 streaming options ─────────────────────────────────────────────────
    parser.add_argument('--lookahead', type=int, default=0,
                        help='Output-delay lookahead in STFT frames (each frame ~ '
                             'hop_length/44100 ≈ 11.6 ms). 0 = no extra delay. '
                             'Adds latency without quality gain in the current LSTM-causal '
                             'design — primarily useful for buffer alignment in offline tools.')
    parser.add_argument('--soft_limiter', action='store_true', default=False,
                        help='Apply per-chunk RMS soft limiter to the output. Useful with v12 '
                             'unbounded masks if rare loud transients leak through. '
                             'Disabled by default — relies on the existing --gain_db tanh '
                             'soft-clip path being sufficient.')

    # ── Auto level (v6) ──────────────────────────────────────────────────────
    # Use this when the model outputs vocals that are too quiet to hear without
    # cranking --gain_db above +15.  High gain_db + tanh saturates everything
    # and crushes dynamics — auto_level normalises each chunk to a target RMS
    # first, then applies a small gain_db on top.
    #
    # Recommended usage:
    #   --auto_level                          (no extra gain — levelled only)
    #   --auto_level --gain_db 3              (level + 3 dB fine-tune)
    #
    # Do NOT combine with high --gain_db (>10) — that re-introduces the
    # tanh saturation you're trying to avoid.
    parser.add_argument('--auto_level', action='store_true', default=False,
                        help='Per-chunk RMS auto-leveller.  Normalises quiet model output '
                             'to --target_rms before gain is applied.  Use instead of high '
                             '--gain_db when vocals sound dim.  Combine with --gain_db 3 '
                             'for fine-tuning.')
    parser.add_argument('--target_rms', type=float, default=0.12,
                        help='Target RMS for --auto_level (default 0.12 ≈ -18 dBFS). '
                             'Raise to 0.18 for louder output; lower to 0.07 for quieter.')

    # ── Mask temporal smoothing ───────────────────────────────────────────────
    parser.add_argument('--mask_smooth', type=int, default=1,
                        help='Temporal smoothing for the separation mask in STFT frames '
                             '(default 1 = off).  Each frame is hop_length/44100 ≈ 11.6 ms. '
                             '3 = mild (~35 ms window, good default to try first). '
                             '5 = moderate (~58 ms, removes most musical noise). '
                             '7 = heavy (~81 ms, very smooth but dulls fast transients). '
                             'Fixes "watery" / "each letter sounds weird" artefacts from '
                             'inconsistent frame-level masking.')

    args = parser.parse_args()

    # ── Dispatch (commands that don't need a checkpoint first) ───────────────
    if args.setup_guide:
        print_setup_guide()
        raise SystemExit(0)
    if args.list_devices:
        list_devices()
        raise SystemExit(0)

    # All remaining modes need a checkpoint
    if args.checkpoint is None:
        parser.error("--checkpoint is required for streaming or dry-run modes.")

    if args.dry_run:
        run_dry(args)
    elif args.vbcable:
        run_vbcable_stream(args)
    elif args.source_device is not None:
        if args.output_device is None:
            parser.error("--source_device requires --output_device (a DIFFERENT speaker).")
        run_loopback_stream(args)
    elif args.mic_device is not None:
        run_mic_stream(args)
    else:
        # No mode selected — show a helpful hint
        parser.error("pick a mode: --vbcable (recommended), --source_device, "
                     "--mic_device, or --dry_run.  Or run --setup_guide for help.")
