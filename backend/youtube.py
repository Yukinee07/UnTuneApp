"""
youtube.py
──────────
Thin wrapper around yt-dlp.  Downloads the bestaudio stream of a YouTube
(or any yt-dlp-supported) URL into uploads/ as an .mp3 / .m4a, and returns
the local Path so inference can pick it up.

We don't shell out to the yt-dlp CLI — we import the Python module so
errors surface as exceptions instead of subprocess returncodes.  Also
keeps the dependency surface explicit.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

import yt_dlp


# ── URL validation ────────────────────────────────────────────────────────
# yt-dlp supports far more than just YouTube (SoundCloud, Bandcamp, Vimeo,
# direct mp3 URLs, ...), so we only reject obvious junk and let yt-dlp itself
# decide if it can handle the rest.
_URL_RE = re.compile(r'^https?://\S+$', re.IGNORECASE)


def is_supported_url(url: str) -> bool:
    return bool(_URL_RE.match(url.strip()))


# ── Probe (cheap metadata fetch, no download) ─────────────────────────────

def probe(url: str) -> dict:
    """
    Fetch title / duration / uploader WITHOUT downloading the audio.
    Used by the frontend to show a confirmation card before committing
    to a multi-minute download.
    """
    opts = {"quiet": True, "no_warnings": True, "skip_download": True}
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)
    return {
        "title":      info.get("title"),
        "duration_s": info.get("duration"),
        "uploader":   info.get("uploader"),
        "thumbnail":  info.get("thumbnail"),
        "webpage":    info.get("webpage_url"),
    }


# ── Download ──────────────────────────────────────────────────────────────

def download(url: str, out_dir: Path, progress_cb=None) -> Path:
    """
    Download bestaudio to out_dir/<sanitised-title>.<ext>.

    progress_cb(percent: float, status: str) is called with values in
    [0, 100] during the download.  We map yt-dlp's 'downloaded_bytes' /
    'total_bytes' progress into 0–95%; the final 5% covers post-processing.

    Returns the path to the resulting audio file.
    """
    out_dir.mkdir(parents=True, exist_ok=True)

    # Container for the produced path — yt-dlp doesn't return it directly,
    # we capture it via the postprocessor hook.
    result_path: dict = {"path": None}

    def _hook(d: dict) -> None:
        if d.get("status") == "downloading" and progress_cb is not None:
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            done  = d.get("downloaded_bytes", 0)
            pct   = 95.0 * (done / total) if total else 0.0
            try:
                progress_cb(pct, "downloading")
            except Exception:
                pass
        elif d.get("status") == "finished":
            # Final file path lives in 'filename' (may still get post-processed
            # to a different extension below; we resolve again from yt-dlp's
            # info dict in the wrapper).
            result_path["path"] = d.get("filename")

    opts = {
        "format":            "bestaudio/best",
        "outtmpl":           str(out_dir / "%(title).200B.%(ext)s"),
        "quiet":             True,
        "no_warnings":       True,
        "noplaylist":        True,
        "progress_hooks":    [_hook],
        # Don't re-encode — we want the rawest audio for downstream ffmpeg
        # in inference.load_audio().  ffmpeg there will resample to 44.1 kHz.
        "postprocessors":    [],
    }

    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)
        # The actual output path can differ from the hook's 'filename' if
        # yt-dlp picked a different container.  prepare_filename() gives
        # the canonical name.
        path = Path(ydl.prepare_filename(info))

    if not path.exists():
        # Fallback to whatever the hook caught.
        if result_path["path"] and Path(result_path["path"]).exists():
            path = Path(result_path["path"])
        else:
            raise RuntimeError(
                f"yt-dlp finished but the expected output file is missing: {path}"
            )

    if progress_cb is not None:
        try:
            progress_cb(100.0, "done")
        except Exception:
            pass

    return path
