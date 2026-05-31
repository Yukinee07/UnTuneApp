# VocalApp

Local web app for HSTasNetVocals vocal separation — file upload, YouTube URL,
or live (VB-Cable) modes — running on the RTX 4060 sitting next to you.

```
┌─────────────────┐    HTTP/WS    ┌──────────────────┐    spawns    ┌──────────────┐
│  Next.js front  │ ────────────▶ │  FastAPI back    │ ───────────▶ │  stream.py   │
│  (port 3000)    │ ◀──────────── │  (port 8000)     │              │  --vbcable   │
└─────────────────┘               │   loads best.pt  │              │  (live mode) │
                                  │   once on CUDA   │              └──────────────┘
                                  └──────────────────┘
                                          │
                                          ▼  separate.py / inference.py
                                  ┌──────────────────┐
                                  │  HSTasNetVocals  │
                                  │  on RTX 4060     │
                                  └──────────────────┘
```

## One-time setup

### 1. Drop the checkpoint into place

Manual copy (~120 MB, drag-drop in Explorer):

```
FROM:  D:\00.FYP\FYP_FINAL\Main_Code\checkpoints_v13\best.pt
TO:    D:\00.FYP\FYP_FINAL\VocalApp\backend\checkpoints\best.pt
```

### 2. Install Python deps

CUDA wheel of PyTorch first (the requirements.txt does NOT pull this for you):

```powershell
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu128
```

Then the rest:

```powershell
cd D:\00.FYP\FYP_FINAL\VocalApp\backend
pip install -r requirements.txt
```

Sanity check that CUDA is wired up:

```powershell
python -c "import torch; print(torch.cuda.is_available(), torch.cuda.get_device_name(0))"
# Expected:  True NVIDIA GeForce RTX 4060
```

### 3. Install ffmpeg if it's not already on PATH

```powershell
ffmpeg -version
# If "not recognized", install from https://www.gyan.dev/ffmpeg/builds/
# and add the bin/ folder to your PATH.
```

### 4. Install Node.js (LTS) if you don't have it

<https://nodejs.org/> — needed for the frontend.  Confirm:

```powershell
node --version    # v20 or later is fine
npm --version
```

The frontend itself will be scaffolded in the next phase.

## Running it

### Backend only (right now)

```powershell
cd D:\00.FYP\FYP_FINAL\VocalApp\backend
python -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

Test it:

```powershell
curl http://127.0.0.1:8000/api/health      # → {"ok":true}
curl http://127.0.0.1:8000/api/info        # model/checkpoint metadata
```

### Both together (after frontend exists)

```powershell
.\start.bat
```

## Folder layout

```
VocalApp/
├── backend/
│   ├── ml/                   ← copies of model.py, separate.py, stream.py
│   ├── checkpoints/best.pt   ← YOU drop the v13 best.pt here
│   ├── uploads/              ← runtime: user-uploaded files
│   ├── outputs/              ← runtime: separated vocal .wav files
│   ├── main.py               ← FastAPI app + routes
│   ├── inference.py          ← loads the model once, file-processing wrapper
│   ├── youtube.py            ← yt-dlp wrapper
│   ├── live.py               ← stream.py subprocess manager
│   └── requirements.txt
├── frontend/                 ← Next.js (scaffolded in Phase 2)
├── start.bat
└── README.md
```

## What lives where

| File | Responsibility |
|------|----------------|
| `backend/main.py` | FastAPI routes, job queue, CORS, lifespan |
| `backend/inference.py` | `ModelService` — model loaded once on CUDA, exposes `separate()` |
| `backend/youtube.py` | yt-dlp probe + download, with progress hooks |
| `backend/live.py` | `StreamManager` — spawns/kills `stream.py --vbcable` subprocess |
| `backend/ml/model.py` | Drop-in copy of Main_Code/model.py (unchanged) |
| `backend/ml/separate.py` | Drop-in copy (used by inference.py via `_separate_with_progress`) |
| `backend/ml/stream.py` | Drop-in copy (subprocess target for live mode) |

If you update model.py in Main_Code, copy it across by hand or via a make-style
script — there is intentionally no symlink (Windows + tracked dependencies).

## API endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET    | `/api/health` | Liveness probe |
| GET    | `/api/info`   | Checkpoint, device, GPU info |
| POST   | `/api/process/file` | multipart upload → `job_id` |
| POST   | `/api/process/youtube` | `{url, settings}` → `job_id` |
| GET    | `/api/youtube/probe?url=…` | Title/duration without downloading |
| GET    | `/api/jobs/{id}` | Poll job state (`queued`/`downloading`/`processing`/`done`/`error`) |
| GET    | `/api/output/{filename}` | Download the produced .wav |
| POST   | `/api/live/start` | Start `stream.py --vbcable` subprocess |
| POST   | `/api/live/stop`  | Stop it |
| GET    | `/api/live/status` | Running, dropped chunks, last stdout lines |
