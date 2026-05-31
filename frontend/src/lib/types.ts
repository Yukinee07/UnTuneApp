// Mirrors the shapes returned by the FastAPI backend (backend/main.py).
// Keep these in lock-step with the Pydantic models / Job.to_dict() over there.

export type ModelInfo = {
  checkpoint: string;
  epoch: number | null;
  val_loss: number | null;
  device: string;
  cuda: boolean;
  gpu_name: string | null;
  n_fft: number;
  hop_length: number;
};

export type Settings = {
  mask_smooth: number;   // 1-7
  target_rms: number;    // 0.0-0.3
  gain_db: number;       // -12 .. 18
  chunk_sec: number;     // 2-30
  overlap_sec: number;   // 0-5
};

export type JobStatus =
  | "queued"
  | "downloading"
  | "processing"
  | "done"
  | "error";

export type Job = {
  id: string;
  kind: "file" | "youtube";
  status: JobStatus;
  progress: number;          // 0-100
  message: string;
  output_url: string | null;  // relative to backend, e.g. "/api/output/foo.wav"
  error: string | null;
  created: number;            // unix seconds
  duration_s: number | null;
  settings: Partial<Settings>;
};

export type LiveStatus = {
  running: boolean;
  status: "idle" | "starting" | "running" | "stopped" | "error";
  pid: number | null;
  started_at: number | null;
  dropped_chunks: number;
  last_lines: string[];
  settings: Record<string, number | boolean>;
  exit_code: number | null;
  error: string | null;
};

export type YouTubeProbe = {
  title: string | null;
  duration_s: number | null;
  uploader: string | null;
  thumbnail: string | null;
  webpage: string | null;
};

// ── Mode-specific defaults ────────────────────────────────────────────────
//
// File and YouTube modes match the CLI separate.py behaviour: raw model
// output, no mask smoothing, no auto-leveller — just a small +3 dB lift
// to compensate for the v13 checkpoint's slightly conservative levels.
// This is what gives the cleanest, most natural separation for offline
// processing (consonants stay sharp, dynamics are preserved).
//
// Live mode keeps smoothing + auto-levelling on because the model is
// emitting one short chunk at a time — without smoothing each chunk's
// mask jitters audibly ("musical noise"), and without auto-levelling
// listening level swings wildly between songs.
export const DEFAULT_FILE_SETTINGS: Settings = {
  mask_smooth: 1,        // off — matches CLI
  target_rms:  0,        // off — preserve original dynamics
  gain_db:     3,        // small lift; CLI output is a touch dim otherwise
  chunk_sec:   10,
  overlap_sec: 1,
};

export const DEFAULT_LIVE_SETTINGS: Settings = {
  mask_smooth: 5,        // smooth out per-chunk mask jitter
  target_rms:  0.12,     // constant ~-18 dBFS for live monitoring
  gain_db:     0,
  chunk_sec:   10,       // ignored in live mode (block_samples drives it)
  overlap_sec: 1,        // ignored in live mode
};

// Backwards-compat alias.  Existing imports of DEFAULT_SETTINGS keep
// working; new code should pick the mode-specific constant above.
export const DEFAULT_SETTINGS: Settings = DEFAULT_FILE_SETTINGS;
