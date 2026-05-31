"""
inference.py
─────────────
Singleton ModelService that loads the HSTasNetVocals checkpoint ONCE at
backend startup and reuses it for every /api/process/file and
/api/process/youtube request.

Why a singleton:
  Loading a 30M-parameter checkpoint takes ~3 seconds and allocates ~120 MB
  of VRAM.  Re-loading on every request would dominate inference time and
  fragment GPU memory.  We load on FastAPI's lifespan startup and tear down
  on shutdown.

Threading:
  PyTorch inference is GPU-bound and releases the GIL during CUDA kernels,
  but to keep things obvious we serialise file processing with an asyncio
  lock at the route layer (main.py).  One inference job at a time on the
  GPU is the right call for a single-user local app — concurrent inference
  would just thrash the GPU.

Parameters exposed at the API:
  mask_smooth  : 1-7   (1 = off, 5 = recommended for v13/epoch-43 model)
  target_rms   : 0.0-0.3   (0 = no auto-leveller, 0.12 = recommended)
  gain_db      : -6 to +12 dB   (applied AFTER auto-leveller)
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

import torch

# Make ml/ importable by name (model.py, separate.py expect this).
_ML_DIR = Path(__file__).parent / "ml"
if str(_ML_DIR) not in sys.path:
    sys.path.insert(0, str(_ML_DIR))

from model    import HSTasNetVocals, StatefulHSTasNetVocals    # noqa: E402
from separate import load_audio, save_audio, separate_file     # noqa: E402

TARGET_SR = 44100


# ───────────────────────────────────────────────────────────────────────────
# Post-processing — mirrors stream.py's _auto_level + _apply_gain so the file
# path produces audio that sounds identical to the live path for the same
# settings.  Keeping these as plain functions (not class methods) makes them
# easy to swap if we want to expose more knobs later.
# ───────────────────────────────────────────────────────────────────────────

def _auto_level(audio: torch.Tensor,
                target_rms: float = 0.12,
                max_gain: float   = 30.0) -> torch.Tensor:
    """RMS auto-leveller (matches stream.py)."""
    rms   = audio.pow(2).mean().sqrt().clamp(min=1e-8)
    scale = (target_rms / rms).clamp(max=max_gain)
    return (audio * scale).clamp(-1.0, 1.0)


def _apply_gain(audio: torch.Tensor, gain_db: float) -> torch.Tensor:
    """tanh soft-clip gain (matches stream.py)."""
    if abs(gain_db) < 0.05:
        return audio
    linear = 10.0 ** (gain_db / 20.0)
    if linear <= 1.06:
        return (audio * linear).clamp(-1.0, 1.0)
    return torch.tanh(audio * linear)


# ───────────────────────────────────────────────────────────────────────────
# Service
# ───────────────────────────────────────────────────────────────────────────

class ModelService:
    """Lifecycle: load() at startup, separate(...) per request, unload() at shutdown."""

    def __init__(self, checkpoint_path: Path):
        self.checkpoint_path = Path(checkpoint_path)
        self.device:    Optional[torch.device] = None
        self.model:     Optional[HSTasNetVocals] = None
        self.streamer:  Optional[StatefulHSTasNetVocals] = None
        self.meta: dict = {}   # epoch / val_loss / config — exposed via /api/info

    # ── lifecycle ─────────────────────────────────────────────────────────

    def load(self) -> None:
        if not self.checkpoint_path.exists():
            raise FileNotFoundError(
                f"Checkpoint not found: {self.checkpoint_path}\n"
                f"Drag-drop your v13 best.pt into backend/checkpoints/."
            )

        self.device = torch.device(
            "cuda" if torch.cuda.is_available() else
            "mps"  if torch.backends.mps.is_available() else
            "cpu"
        )

        ckpt   = torch.load(self.checkpoint_path, map_location="cpu", weights_only=False)
        config = ckpt.get("config", {})

        self.model = HSTasNetVocals(
            n_fft         = config.get("n_fft",         1024),
            hop_length    = config.get("hop_length",    512),
            bidirectional = config.get("bidirectional", False),
        )
        self.model.load_state_dict(ckpt["model_state_dict"])
        self.model.eval().to(self.device)

        self.streamer = StatefulHSTasNetVocals(self.model, self.device)

        self.meta = {
            "checkpoint": str(self.checkpoint_path.name),
            "epoch":      ckpt.get("epoch", None),
            "val_loss":   float(ckpt["val_loss"]) if "val_loss" in ckpt else None,
            "device":     str(self.device),
            "cuda":       torch.cuda.is_available(),
            "gpu_name":   torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
            "n_fft":      config.get("n_fft", 1024),
            "hop_length": config.get("hop_length", 512),
        }
        print(f"[ModelService] Loaded {self.meta}")

    def unload(self) -> None:
        self.model = None
        self.streamer = None
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    # ── inference ─────────────────────────────────────────────────────────

    @torch.inference_mode()
    def separate(
        self,
        input_path:  Path,
        output_path: Path,
        *,
        mask_smooth: int   = 5,
        target_rms:  float = 0.12,
        gain_db:     float = 0.0,
        chunk_sec:   float = 10.0,
        overlap_sec: float = 1.0,
        progress_cb=None,
    ) -> dict:
        """
        Run vocal separation on a single audio/video file.

        progress_cb(percent: float) — optional callable invoked every chunk
                                      with a value in [0, 100].

        Returns a dict with timing + output info.
        """
        if self.model is None or self.streamer is None:
            raise RuntimeError("ModelService.load() must be called first.")

        # 1. Configure the model (mask smoothing is per-request).
        self.model.set_mask_smooth(max(1, int(mask_smooth)))

        # 2. Decode mixture via ffmpeg → tensor.
        mixture, peak = load_audio(str(input_path))
        duration = mixture.shape[1] / TARGET_SR

        # 3. Chunked stateful inference with cross-fade overlap.
        #    We wrap separate.separate_file to inject progress reporting
        #    without forking its body.
        vocals = self._separate_with_progress(
            mixture,
            chunk_samples   = int(chunk_sec   * TARGET_SR),
            overlap_samples = int(overlap_sec * TARGET_SR),
            progress_cb     = progress_cb,
        )

        # 4. Restore original loudness, then auto-level + gain.
        vocals = vocals * peak
        if target_rms > 0:
            vocals = _auto_level(vocals, target_rms=target_rms)
        if abs(gain_db) > 0.05:
            vocals = _apply_gain(vocals, gain_db)

        # 5. Persist.
        output_path.parent.mkdir(parents=True, exist_ok=True)
        save_audio(vocals, str(output_path))

        return {
            "output":      str(output_path.name),
            "duration_s":  float(duration),
            "settings":    {
                "mask_smooth": mask_smooth,
                "target_rms":  target_rms,
                "gain_db":     gain_db,
            },
        }

    # ── internals ─────────────────────────────────────────────────────────

    def _separate_with_progress(
        self,
        mixture: torch.Tensor,
        chunk_samples: int,
        overlap_samples: int,
        progress_cb,
    ) -> torch.Tensor:
        """
        Drop-in replacement for separate.separate_file() that reports progress.
        Mirrors that function's logic — same cross-fade overlap-add — but
        invokes progress_cb(percent) after each chunk so the frontend can
        show a live progress bar.
        """
        L      = mixture.shape[1]
        output = torch.zeros(2, L)
        weight = torch.zeros(L)
        hop    = chunk_samples - overlap_samples

        fade_in  = torch.linspace(0, 1, overlap_samples)
        fade_out = torch.linspace(1, 0, overlap_samples)

        self.streamer.reset()
        pos, idx = 0, 0
        total_chunks = max(1, (L + hop - 1) // hop)

        while pos < L:
            end   = min(pos + chunk_samples, L)
            chunk = mixture[:, pos:end]

            pad = chunk_samples - chunk.shape[1]
            if pad > 0:
                chunk = torch.nn.functional.pad(chunk, (0, pad))

            vocals = self.streamer.process_chunk(chunk)[:, :end - pos]

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

            if progress_cb is not None:
                # Report 5–95% during chunks; final 5% covers save+gain.
                pct = 5.0 + 90.0 * min(1.0, idx / total_chunks)
                try:
                    progress_cb(pct)
                except Exception:
                    pass   # never let a UI bug crash inference

        return output / weight.clamp(min=1e-8).unsqueeze(0)
