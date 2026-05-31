// Typed wrappers around the FastAPI endpoints.
// All paths are kept relative; we prepend NEXT_PUBLIC_API_URL once here so
// component code never hard-codes the backend origin.

import type {
  Job,
  LiveStatus,
  ModelInfo,
  Settings,
  YouTubeProbe,
} from "./types";

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/+$/, "") ||
  "http://127.0.0.1:8000";

/** Absolute URL for a backend-relative path like "/api/output/foo.wav". */
export function apiUrl(path: string): string {
  if (path.startsWith("http")) return path;
  return `${API_BASE}${path.startsWith("/") ? "" : "/"}${path}`;
}

async function jget<T>(path: string): Promise<T> {
  const r = await fetch(apiUrl(path), { cache: "no-store" });
  if (!r.ok) throw new Error(`${r.status} ${r.statusText} on GET ${path}`);
  return r.json() as Promise<T>;
}

async function jpost<T>(path: string, body?: unknown): Promise<T> {
  const r = await fetch(apiUrl(path), {
    method: "POST",
    headers: body ? { "content-type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!r.ok) {
    let detail = r.statusText;
    try {
      const j = await r.json();
      detail = j?.detail ?? detail;
    } catch {}
    throw new Error(`${r.status} ${detail}`);
  }
  return r.json() as Promise<T>;
}

// ── Endpoints ───────────────────────────────────────────────────────────

export const api = {
  health:  () => jget<{ ok: boolean }>("/api/health"),
  info:    () => jget<ModelInfo>("/api/info"),

  // file upload — multipart, can't share helper above
  async submitFile(file: File, settings: Settings): Promise<Job> {
    const fd = new FormData();
    fd.append("file", file);
    fd.append("mask_smooth", String(settings.mask_smooth));
    fd.append("target_rms",  String(settings.target_rms));
    fd.append("gain_db",     String(settings.gain_db));
    fd.append("chunk_sec",   String(settings.chunk_sec));
    fd.append("overlap_sec", String(settings.overlap_sec));

    const r = await fetch(apiUrl("/api/process/file"), {
      method: "POST",
      body: fd,
    });
    if (!r.ok) {
      let detail = r.statusText;
      try { detail = (await r.json())?.detail ?? detail; } catch {}
      throw new Error(`${r.status} ${detail}`);
    }
    return r.json();
  },

  submitYouTube: (url: string, settings: Settings) =>
    jpost<Job>("/api/process/youtube", { url, settings }),

  probeYouTube: (url: string) =>
    jget<YouTubeProbe>(`/api/youtube/probe?url=${encodeURIComponent(url)}`),

  getJob: (id: string) => jget<Job>(`/api/jobs/${id}`),

  // Live
  liveStart: (settings: {
    block_samples: number;
    mask_smooth: number;
    target_rms: number;
    gain_db: number;
    auto_level: boolean;
  }) => jpost<LiveStatus>("/api/live/start", settings),
  liveStop:   () => jpost<LiveStatus>("/api/live/stop"),
  liveStatus: () => jget<LiveStatus>("/api/live/status"),
};
