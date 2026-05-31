"""
File-based vocal separation using a trained HSTasNetVocals checkpoint.

Usage:
    python3 separate.py --checkpoint ./checkpoints_v4/best.pt --input ./song3.mp3 --output_dir ./separated
"""

import argparse
import os
import subprocess
from pathlib import Path

import numpy as np
import torch
import soundfile as sf

from model import HSTasNetVocals, StatefulHSTasNetVocals

TARGET_SR = 44100


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def to_windows_path(p) -> str:
    s = str(p)
    if s.startswith('/mnt/'):
        parts = s[5:].split('/', 1)
        drive = parts[0].upper()
        rest  = parts[1] if len(parts) > 1 else ''
        s = f"{drive}:/{rest}"
    return s


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

    wav  = torch.from_numpy(wav.T).float()   # (2, L)
    peak = wav.abs().max()
    if peak > 0:
        wav = wav / peak
    return wav, peak


def save_audio(tensor: torch.Tensor, path: str, sr: int = TARGET_SR):
    """Save (2, L) tensor to WAV via soundfile."""
    data = tensor.cpu().clamp(-1, 1).numpy().T   # (L, 2)
    sf.write(path, data, sr, subtype='FLOAT')


def _apply_gain(audio: torch.Tensor, gain_db: float) -> torch.Tensor:
    """
    Boost output by gain_db decibels with tanh soft-clip for safety.
    Soft-clip prevents harsh digital distortion on loud peaks — same shape
    an analog tube preamp uses.  Mirrors stream.py's _apply_gain.
    """
    if abs(gain_db) < 0.05:
        return audio
    linear = 10.0 ** (gain_db / 20.0)
    if linear <= 1.06:          # ≤ +0.5 dB — hard clamp is fine
        return (audio * linear).clamp(-1.0, 1.0)
    return torch.tanh(audio * linear)


def load_model(checkpoint_path: str, device: torch.device) -> HSTasNetVocals:
    ckpt   = torch.load(checkpoint_path, map_location='cpu')
    config = ckpt.get('config', {})
    model  = HSTasNetVocals(
        n_fft=config.get('n_fft', 1024),
        hop_length=config.get('hop_length', 512),
    )
    model.load_state_dict(ckpt['model_state_dict'])
    epoch    = ckpt.get('epoch', '?')
    val_loss = ckpt.get('val_loss', '?')
    print(f"[Separate] Loaded checkpoint  epoch={epoch}  val_loss={val_loss}")
    return model


# ---------------------------------------------------------------------------
# Chunked stateful inference
# ---------------------------------------------------------------------------

def separate_file(
    streamer: StatefulHSTasNetVocals,
    mixture: torch.Tensor,
    chunk_samples: int = 44100 * 10,
    overlap_samples: int = 44100,
) -> torch.Tensor:
    """
    Process a full file using the stateful streamer with crossfade overlap.
    mixture : (2, L)
    returns : (2, L) vocals
    """
    L      = mixture.shape[1]
    output = torch.zeros(2, L)
    weight = torch.zeros(L)
    hop    = chunk_samples - overlap_samples

    fade_in  = torch.linspace(0, 1, overlap_samples)
    fade_out = torch.linspace(1, 0, overlap_samples)

    streamer.reset()
    pos, idx = 0, 0

    while pos < L:
        end   = min(pos + chunk_samples, L)
        chunk = mixture[:, pos:end]

        # Pad last chunk
        pad = chunk_samples - chunk.shape[1]
        if pad > 0:
            chunk = torch.nn.functional.pad(chunk, (0, pad))

        vocals = streamer.process_chunk(chunk)[:, :end - pos]

        actual = end - pos
        w = torch.ones(actual)
        if idx > 0:
            fl = min(overlap_samples, actual)
            w[:fl] = w[:fl] * fade_in[:fl]
        if end < L:
            fl = min(overlap_samples, actual)
            w[-fl:] = w[-fl:] * fade_out[-fl:]

        output[:, pos:end] += vocals * w.unsqueeze(0)
        weight[pos:end]    += w

        pos += hop
        idx += 1

    output = output / weight.clamp(min=1e-8).unsqueeze(0)
    return output


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def separate(args):
    device = torch.device(
        'cuda' if torch.cuda.is_available() else
        'mps'  if torch.backends.mps.is_available() else
        'cpu'
    )
    print(f"[Separate] Device: {device}")

    model    = load_model(args.checkpoint, device)
    streamer = StatefulHSTasNetVocals(model, device)

    input_path = Path(args.input)
    if not input_path.exists():
        raise FileNotFoundError(f"Input not found: {input_path}")

    print(f"[Separate] Loading: {input_path.name}")
    mixture, peak = load_audio(str(input_path))
    print(f"[Separate] Duration: {mixture.shape[1]/TARGET_SR:.1f}s")

    print("[Separate] Separating vocals...")
    vocals = separate_file(
        streamer, mixture,
        chunk_samples=int(args.chunk_sec * TARGET_SR),
        overlap_samples=int(args.overlap_sec * TARGET_SR),
    )
    vocals = vocals * peak   # restore original loudness

    # Optional gain boost with soft-clip (mirrors stream.py)
    if args.gain_db != 0.0:
        vocals = _apply_gain(vocals, args.gain_db)
        linear = 10.0 ** (args.gain_db / 20.0)
        print(f"[Separate] Output gain: {args.gain_db:+.1f} dB "
              f"({linear:.2f}x linear, soft-clipped)")

    out_dir  = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{input_path.stem}_vocals.wav"
    save_audio(vocals, str(out_path))
    print(f"[Separate] Saved: {out_path.resolve()}")


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--checkpoint',  required=True)
    parser.add_argument('--input',       required=True)
    parser.add_argument('--output_dir',  default='./separated')
    parser.add_argument('--chunk_sec',   type=float, default=10.0)
    parser.add_argument('--overlap_sec', type=float, default=1.0)
    parser.add_argument('--gain_db',     type=float, default=0.0,
                        help='Boost vocal output by N dB with tanh soft-clip. '
                             'e.g. --gain_db 8 (~2.5x louder), 13 (~4.5x louder).')
    args = parser.parse_args()
    separate(args)
