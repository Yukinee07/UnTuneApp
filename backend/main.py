"""
main.py
───────
FastAPI app for VocalApp.

Routes:
  GET  /api/health                  liveness probe
  GET  /api/info                    model/device/checkpoint metadata
  POST /api/process/file            multipart upload → job_id
  POST /api/process/youtube         {url, settings} → job_id
  GET  /api/jobs/{job_id}           current job state
  GET  /api/output/{filename}       download finished .wav
  POST /api/live/start              start stream.py --vbcable
  POST /api/live/stop               stop it
  GET  /api/live/status             current live state

Jobs:
  In-memory dict (single-user local app — no persistence needed).
  A background thread picks jobs out of a queue and runs them through
  ModelService.separate().  One inference job at a time so the GPU isn't
  thrashed by concurrent requests.
"""
from __future__ import annotations

import asyncio
import shutil
import threading
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from queue import Queue
from typing import Optional

from fastapi import (
    FastAPI, File, Form, HTTPException, UploadFile, BackgroundTasks
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from inference import ModelService
from live      import StreamManager
import youtube as youtube_mod


# ─── Paths ─────────────────────────────────────────────────────────────────
BACKEND_DIR   = Path(__file__).parent
ML_DIR        = BACKEND_DIR / "ml"
CHECKPOINT    = BACKEND_DIR / "checkpoints" / "best.pt"
UPLOADS_DIR   = BACKEND_DIR / "uploads"
OUTPUTS_DIR   = BACKEND_DIR / "outputs"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)


# ─── Globals ───────────────────────────────────────────────────────────────
model_service: Optional[ModelService] = None
stream_mgr:    Optional[StreamManager] = None

# In-memory job store.  Single-user local app; no need for Redis.
JOBS: dict = {}
JOB_QUEUE: "Queue[str]" = Queue()
JOB_LOCK = threading.Lock()


# ─── Job model ─────────────────────────────────────────────────────────────

class Job:
    def __init__(self, kind: str, payload: dict):
        self.id        = uuid.uuid4().hex[:12]
        self.kind      = kind                  # 'file' | 'youtube'
        self.payload   = payload
        self.status    = "queued"              # queued | downloading | processing | done | error
        self.progress  = 0.0
        self.message   = ""
        self.output    = None                  # filename in OUTPUTS_DIR
        self.error     = None
        self.created   = time.time()
        self.duration_s: Optional[float] = None

    def to_dict(self) -> dict:
        return {
            "id":          self.id,
            "kind":        self.kind,
            "status":      self.status,
            "progress":    round(float(self.progress), 1),
            "message":     self.message,
            "output_url":  f"/api/output/{self.output}" if self.output else None,
            "error":       self.error,
            "created":     self.created,
            "duration_s":  self.duration_s,
            "settings":    self.payload.get("settings", {}),
        }


# ─── Request schemas ───────────────────────────────────────────────────────

class Settings(BaseModel):
    mask_smooth: int   = Field(default=5, ge=1, le=7)
    target_rms:  float = Field(default=0.12, ge=0.0, le=0.3)
    gain_db:     float = Field(default=0.0, ge=-12.0, le=18.0)
    chunk_sec:   float = Field(default=10.0, ge=2.0, le=30.0)
    overlap_sec: float = Field(default=1.0,  ge=0.0, le=5.0)


class YouTubeRequest(BaseModel):
    url:      str
    settings: Settings = Settings()


class LiveStartRequest(BaseModel):
    block_samples: int   = Field(default=8192, ge=2048, le=32768)
    mask_smooth:   int   = Field(default=5,    ge=1,    le=7)
    target_rms:    float = Field(default=0.12, ge=0.0,  le=0.3)
    gain_db:       float = Field(default=0.0,  ge=-12.0, le=18.0)
    auto_level:    bool  = True


# ─── Worker (single-thread, runs forever) ─────────────────────────────────

def _worker_loop() -> None:
    """One job at a time — keeps GPU utilisation clean."""
    while True:
        job_id = JOB_QUEUE.get()                # blocks
        if job_id is None:
            return
        with JOB_LOCK:
            job: Optional[Job] = JOBS.get(job_id)
        if job is None:
            continue

        try:
            if job.kind == "youtube":
                _run_youtube_job(job)
            elif job.kind == "file":
                _run_file_job(job)
            else:
                raise ValueError(f"Unknown job kind: {job.kind}")
        except Exception as e:
            job.status   = "error"
            job.error    = f"{type(e).__name__}: {e}"
            job.progress = 0.0


def _run_file_job(job: Job) -> None:
    settings = Settings(**job.payload["settings"])
    in_path  = Path(job.payload["input_path"])

    job.status   = "processing"
    job.message  = "Separating vocals…"
    job.progress = 5.0

    out_name = f"{in_path.stem}_vocals_{job.id}.wav"
    out_path = OUTPUTS_DIR / out_name

    def progress_cb(pct: float) -> None:
        job.progress = pct

    result = model_service.separate(
        in_path, out_path,
        mask_smooth = settings.mask_smooth,
        target_rms  = settings.target_rms,
        gain_db     = settings.gain_db,
        chunk_sec   = settings.chunk_sec,
        overlap_sec = settings.overlap_sec,
        progress_cb = progress_cb,
    )

    job.output     = out_name
    job.duration_s = result["duration_s"]
    job.progress   = 100.0
    job.status     = "done"
    job.message    = f"Done — {result['duration_s']:.1f}s of audio processed."


def _run_youtube_job(job: Job) -> None:
    settings = Settings(**job.payload["settings"])
    url      = job.payload["url"]

    job.status  = "downloading"
    job.message = "Downloading…"

    def dl_progress(pct: float, status: str) -> None:
        # Map yt-dlp 0–100 → 0–40% of overall job progress.
        job.progress = pct * 0.4
        job.message  = "Downloading…" if status == "downloading" else "Download complete"

    downloaded = youtube_mod.download(url, UPLOADS_DIR, progress_cb=dl_progress)

    job.status   = "processing"
    job.message  = "Separating vocals…"
    job.progress = 45.0

    out_name = f"{downloaded.stem}_vocals_{job.id}.wav"
    out_path = OUTPUTS_DIR / out_name

    def sep_progress(pct: float) -> None:
        # Map inference 0–100 → 45–100% of overall.
        job.progress = 45.0 + pct * 0.55

    result = model_service.separate(
        downloaded, out_path,
        mask_smooth = settings.mask_smooth,
        target_rms  = settings.target_rms,
        gain_db     = settings.gain_db,
        chunk_sec   = settings.chunk_sec,
        overlap_sec = settings.overlap_sec,
        progress_cb = sep_progress,
    )

    job.output     = out_name
    job.duration_s = result["duration_s"]
    job.progress   = 100.0
    job.status     = "done"
    job.message    = f"Done — {result['duration_s']:.1f}s of audio processed."


# ─── Lifespan: load model + start worker ──────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    global model_service, stream_mgr

    print("[main] Loading model…")
    model_service = ModelService(CHECKPOINT)
    model_service.load()

    stream_mgr = StreamManager(ML_DIR, CHECKPOINT)

    worker = threading.Thread(target=_worker_loop, daemon=True)
    worker.start()
    print("[main] Worker thread started; ready.")

    yield

    # Shutdown
    print("[main] Shutdown — stopping live stream if running…")
    try:
        stream_mgr.stop(timeout=2.0)
    except Exception:
        pass
    JOB_QUEUE.put(None)                # poison-pill worker
    model_service.unload()


app = FastAPI(title="VocalApp Backend", version="0.1.0", lifespan=lifespan)

# CORS — Next.js dev server lives on :3000.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Routes ────────────────────────────────────────────────────────────────

@app.get("/api/health")
def health():
    return {"ok": True}


@app.get("/api/info")
def info():
    if model_service is None or model_service.meta is None:
        raise HTTPException(503, "model not loaded yet")
    return model_service.meta


@app.post("/api/process/file")
async def process_file(
    file:        UploadFile = File(...),
    mask_smooth: int   = Form(5),
    target_rms:  float = Form(0.12),
    gain_db:     float = Form(0.0),
    chunk_sec:   float = Form(10.0),
    overlap_sec: float = Form(1.0),
):
    if file.filename is None:
        raise HTTPException(400, "Missing filename")

    # Sanitise just enough to avoid path traversal.
    safe_name = Path(file.filename).name
    saved     = UPLOADS_DIR / f"{uuid.uuid4().hex[:8]}_{safe_name}"

    with saved.open("wb") as f:
        shutil.copyfileobj(file.file, f)

    settings = Settings(
        mask_smooth=mask_smooth, target_rms=target_rms, gain_db=gain_db,
        chunk_sec=chunk_sec, overlap_sec=overlap_sec,
    ).model_dump()

    job = Job(kind="file", payload={"input_path": str(saved), "settings": settings})
    with JOB_LOCK:
        JOBS[job.id] = job
    JOB_QUEUE.put(job.id)

    return job.to_dict()


@app.post("/api/process/youtube")
async def process_youtube(req: YouTubeRequest):
    if not youtube_mod.is_supported_url(req.url):
        raise HTTPException(400, "URL does not look like an http(s) URL")

    job = Job(kind="youtube", payload={"url": req.url, "settings": req.settings.model_dump()})
    with JOB_LOCK:
        JOBS[job.id] = job
    JOB_QUEUE.put(job.id)

    return job.to_dict()


@app.get("/api/youtube/probe")
def youtube_probe(url: str):
    if not youtube_mod.is_supported_url(url):
        raise HTTPException(400, "URL does not look like an http(s) URL")
    try:
        return youtube_mod.probe(url)
    except Exception as e:
        raise HTTPException(400, f"Could not probe URL: {e}")


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str):
    with JOB_LOCK:
        job = JOBS.get(job_id)
    if job is None:
        raise HTTPException(404, "job not found")
    return job.to_dict()


@app.get("/api/output/{filename}")
def get_output(filename: str):
    # Strip any path components — output files live flat in OUTPUTS_DIR.
    safe = Path(filename).name
    path = OUTPUTS_DIR / safe
    if not path.exists():
        raise HTTPException(404, "output not found")
    return FileResponse(
        path,
        media_type="audio/wav",
        filename=safe,
    )


# ─── Live (subprocess) routes ─────────────────────────────────────────────

@app.post("/api/live/start")
def live_start(req: LiveStartRequest):
    if stream_mgr is None:
        raise HTTPException(503, "stream manager not ready")
    s = stream_mgr.start(
        block_samples=req.block_samples,
        mask_smooth=req.mask_smooth,
        target_rms=req.target_rms,
        gain_db=req.gain_db,
        auto_level=req.auto_level,
    )
    return s.__dict__


@app.post("/api/live/stop")
def live_stop():
    if stream_mgr is None:
        raise HTTPException(503, "stream manager not ready")
    return stream_mgr.stop().__dict__


@app.get("/api/live/status")
def live_status():
    if stream_mgr is None:
        raise HTTPException(503, "stream manager not ready")
    return stream_mgr.status().__dict__
