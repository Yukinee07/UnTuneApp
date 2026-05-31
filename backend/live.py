"""
live.py
───────
Subprocess manager for stream.py --vbcable.

Why a subprocess instead of importing stream.py directly:
  stream.py owns its own torch.inference_mode loop, its own threads, and
  its own WASAPI session.  Embedding it in the FastAPI process would mean
  the audio I/O loop competes with uvicorn's event loop and any model
  inference happening for file requests.  A separate process keeps the
  live pipeline isolated — if it crashes, the backend stays up.

What this module owns:
  • One global StreamManager (single live session at a time — desktop UX).
  • Background reader thread that scrapes stream.py's stdout into:
      - dropped_chunks (int)   — last "[Stream] N chunks dropped" line
      - last_lines     (list)  — rolling window of recent stdout lines
      - status         (str)   — 'idle' | 'starting' | 'running' | 'stopped' | 'error'
"""
from __future__ import annotations

import os
import signal
import subprocess
import sys
import threading
import time
import re
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

_DROP_RE = re.compile(r"\[Stream\]\s+(\d+)\s+chunks dropped")


# ───────────────────────────────────────────────────────────────────────────
# Public state shape (what main.py returns from GET /api/live/status)
# ───────────────────────────────────────────────────────────────────────────

@dataclass
class LiveStatus:
    running:        bool        = False
    status:         str         = "idle"
    pid:            Optional[int]   = None
    started_at:     Optional[float] = None
    dropped_chunks: int         = 0
    last_lines:     list        = field(default_factory=list)
    settings:       dict        = field(default_factory=dict)
    exit_code:      Optional[int]   = None
    error:          Optional[str]   = None


# ───────────────────────────────────────────────────────────────────────────
# Manager
# ───────────────────────────────────────────────────────────────────────────

class StreamManager:
    """Single-session subprocess manager."""

    def __init__(self, ml_dir: Path, checkpoint_path: Path, python_exe: str = sys.executable):
        self.ml_dir          = Path(ml_dir)
        self.checkpoint_path = Path(checkpoint_path)
        self.python_exe      = python_exe

        self._proc:    Optional[subprocess.Popen] = None
        self._reader_thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

        self._state = LiveStatus()
        self._last_lines: deque = deque(maxlen=40)

    # ── Public API ────────────────────────────────────────────────────────

    def start(self,
              block_samples: int   = 8192,
              mask_smooth:   int   = 5,
              target_rms:    float = 0.12,
              gain_db:       float = 0.0,
              auto_level:    bool  = True) -> LiveStatus:
        """Start stream.py --vbcable with the given settings.  Idempotent."""
        with self._lock:
            if self._proc is not None and self._proc.poll() is None:
                return self.status()   # already running

            if not self.checkpoint_path.exists():
                self._state = LiveStatus(
                    status="error",
                    error=f"Checkpoint not found: {self.checkpoint_path}",
                )
                return self._state

            cmd = [
                self.python_exe,
                "stream.py",
                "--checkpoint", str(self.checkpoint_path.resolve()),
                "--vbcable",
                "--block_samples", str(int(block_samples)),
                "--mask_smooth",   str(int(mask_smooth)),
            ]
            if auto_level:
                cmd += ["--auto_level", "--target_rms", str(float(target_rms))]
            if abs(gain_db) > 0.05:
                cmd += ["--gain_db", str(float(gain_db))]

            settings = {
                "block_samples": block_samples,
                "mask_smooth":   mask_smooth,
                "target_rms":    target_rms,
                "gain_db":       gain_db,
                "auto_level":    auto_level,
            }

            # cwd=ml_dir so stream.py's `from model import ...` resolves to
            # the colocated model.py.  Match training environment encoding to
            # keep the live output (e.g. the "✓ Output reconnected" lines)
            # legible in our reader thread.
            try:
                self._proc = subprocess.Popen(
                    cmd,
                    cwd=str(self.ml_dir),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,                 # line-buffered
                    encoding="utf-8",
                    errors="replace",
                    creationflags=(
                        subprocess.CREATE_NEW_PROCESS_GROUP   # Windows: lets us send Ctrl+Break to terminate cleanly
                        if os.name == "nt" else 0
                    ),
                )
            except Exception as e:
                self._state = LiveStatus(status="error", error=str(e))
                return self._state

            self._state = LiveStatus(
                running=True,
                status="starting",
                pid=self._proc.pid,
                started_at=time.time(),
                settings=settings,
            )
            self._last_lines.clear()

            self._reader_thread = threading.Thread(
                target=self._read_stdout, daemon=True
            )
            self._reader_thread.start()

            return self.status()

    def stop(self, timeout: float = 5.0) -> LiveStatus:
        """Politely stop the subprocess.  Returns final status."""
        with self._lock:
            if self._proc is None:
                return self.status()
            if self._proc.poll() is not None:
                # Already exited.
                self._state.running = False
                self._state.status  = "stopped" if self._state.status != "error" else "error"
                self._state.exit_code = self._proc.returncode
                return self.status()

            try:
                if os.name == "nt":
                    # CTRL_BREAK_EVENT works because we set CREATE_NEW_PROCESS_GROUP.
                    self._proc.send_signal(signal.CTRL_BREAK_EVENT)
                else:
                    self._proc.terminate()
            except Exception:
                pass

            try:
                self._proc.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                self._proc.kill()
                self._proc.wait()

            self._state.running   = False
            self._state.status    = "stopped"
            self._state.exit_code = self._proc.returncode
            return self.status()

    def status(self) -> LiveStatus:
        # Materialise a copy of the rolling line buffer (the deque is mutated
        # from the reader thread).
        s = self._state
        return LiveStatus(
            running        = s.running,
            status         = s.status,
            pid            = s.pid,
            started_at     = s.started_at,
            dropped_chunks = s.dropped_chunks,
            last_lines     = list(self._last_lines),
            settings       = dict(s.settings),
            exit_code      = s.exit_code,
            error          = s.error,
        )

    # ── Internals ─────────────────────────────────────────────────────────

    def _read_stdout(self) -> None:
        """Background: drain stdout, parse drops, detect ready state."""
        assert self._proc is not None
        try:
            for line in self._proc.stdout:                # blocks until EOF
                line = line.rstrip()
                if not line:
                    continue
                self._last_lines.append(line)

                # Promote 'starting' → 'running' as soon as we see the
                # "Streaming…" banner stream.py prints once the threads
                # are wired up.
                if self._state.status == "starting" and "Streaming" in line:
                    self._state.status = "running"

                m = _DROP_RE.search(line)
                if m:
                    try:
                        self._state.dropped_chunks = int(m.group(1))
                    except ValueError:
                        pass
        except Exception as e:
            self._state.error = f"reader: {e}"
        finally:
            rc = self._proc.poll()
            self._state.running   = False
            self._state.exit_code = rc
            if self._state.status not in ("stopped", "error"):
                # Process died on its own.
                self._state.status = "error" if rc not in (0, None) else "stopped"
