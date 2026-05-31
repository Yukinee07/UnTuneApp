"use client";

import { useEffect, useRef, useState } from "react";
import { api } from "./api";
import type { Job } from "./types";

/**
 * Polls /api/jobs/{id} every `intervalMs` until status becomes 'done' or
 * 'error'.  Returns the latest job snapshot, plus a loading/error flag.
 *
 * Pass `jobId = null` to disable.
 *
 * We use a ref-tracked interval (not a recursive timeout) so React-strict-
 * mode double-mounts in dev don't leak pollers.
 */
export function useJob(jobId: string | null, intervalMs = 700) {
  const [job, setJob]     = useState<Job | null>(null);
  const [error, setError] = useState<string | null>(null);
  const tickRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    if (!jobId) {
      setJob(null);
      setError(null);
      return;
    }

    let cancelled = false;

    const tick = async () => {
      try {
        const j = await api.getJob(jobId);
        if (cancelled) return;
        setJob(j);
        if (j.status === "done" || j.status === "error") {
          if (tickRef.current) clearInterval(tickRef.current);
          tickRef.current = null;
        }
      } catch (e) {
        if (cancelled) return;
        setError(e instanceof Error ? e.message : String(e));
      }
    };

    // Fire immediately so users don't wait `intervalMs` for the first poll.
    void tick();
    tickRef.current = setInterval(tick, intervalMs);

    return () => {
      cancelled = true;
      if (tickRef.current) {
        clearInterval(tickRef.current);
        tickRef.current = null;
      }
    };
  }, [jobId, intervalMs]);

  return { job, error };
}
