"use client";

import { useCallback, useEffect, useState } from "react";
import {
  Radio, Play, Square, Activity, AlertCircle, Cable,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { api } from "@/lib/api";
import type { LiveStatus, Settings } from "@/lib/types";
import { toast } from "sonner";
import { cn } from "@/lib/utils";

export function LiveTab({ settings }: { settings: Settings }) {
  const [status, setStatus] = useState<LiveStatus | null>(null);
  const [busy,   setBusy]   = useState(false);

  const poll = useCallback(async () => {
    try { setStatus(await api.liveStatus()); }
    catch (e) { console.error(e); }
  }, []);

  useEffect(() => {
    void poll();
    const t = setInterval(poll, 1000);
    return () => clearInterval(t);
  }, [poll]);

  const start = async () => {
    setBusy(true);
    try {
      const s = await api.liveStart({
        block_samples: 8192,
        mask_smooth:   settings.mask_smooth,
        target_rms:    settings.target_rms,
        gain_db:       settings.gain_db,
        auto_level:    settings.target_rms > 0,
      });
      setStatus(s);
      if (s.status === "error") toast.error(s.error ?? "Failed to start.");
      else toast.success("Live stream starting…");
    } catch (e) {
      toast.error(e instanceof Error ? e.message : String(e));
    } finally { setBusy(false); }
  };

  const stop = async () => {
    setBusy(true);
    try { setStatus(await api.liveStop()); toast.info("Live stream stopped."); }
    catch (e) { toast.error(e instanceof Error ? e.message : String(e)); }
    finally { setBusy(false); }
  };

  const running = status?.running ?? false;
  const indicator = INDICATORS[status?.status ?? "idle"];

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="flex items-center gap-2 text-base">
            <Cable className="h-4 w-4 text-primary" />
            VB-Cable required
          </CardTitle>
          <CardDescription className="text-xs">
            Live mode reads all system audio via VB-Cable and plays back vocals
            to your real speakers. Install it from{" "}
            <a className="text-primary underline" href="https://vb-audio.com/Cable/" target="_blank" rel="noreferrer">vb-audio.com/Cable</a>{" "}
            and set it as your Windows default output before starting.
          </CardDescription>
        </CardHeader>
      </Card>

      <Card>
        <CardContent className="pt-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className={cn(
                "grid h-10 w-10 place-items-center rounded-full ring-1",
                indicator.ring,
              )}>
                <Radio className={cn("h-5 w-5", indicator.icon, running && "animate-pulse")} />
              </div>
              <div>
                <p className="text-sm font-medium">{indicator.label}</p>
                <p className="text-xs text-muted-foreground">
                  {status?.pid ? `pid ${status.pid}` : "subprocess idle"}
                  {status?.dropped_chunks ? ` · ${status.dropped_chunks} chunks dropped` : null}
                </p>
              </div>
            </div>

            <div className="flex gap-2">
              {running ? (
                <Button variant="destructive" onClick={stop} disabled={busy}>
                  <Square className="mr-2 h-4 w-4" />
                  Stop
                </Button>
              ) : (
                <Button onClick={start} disabled={busy}>
                  <Play className="mr-2 h-4 w-4" />
                  Start live stream
                </Button>
              )}
            </div>
          </div>

          {status?.error && (
            <div className="mt-4 flex items-start gap-2 rounded border border-destructive/40 bg-destructive/5 p-3 text-xs text-destructive">
              <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
              <span className="break-all">{status.error}</span>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Log feed — only shown while we have lines */}
      {status && status.last_lines.length > 0 && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-2 text-sm font-medium">
              <Activity className="h-4 w-4 text-accent" />
              stream.py output
              <Badge variant="outline" className="ml-auto font-mono text-[10px]">
                {status.last_lines.length} lines
              </Badge>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <pre className="max-h-72 overflow-auto rounded border border-border/60 bg-background/60 p-3 font-mono text-[11px] leading-relaxed text-muted-foreground">
              {status.last_lines.join("\n")}
            </pre>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

const INDICATORS: Record<LiveStatus["status"] | "idle", {
  label: string; ring: string; icon: string;
}> = {
  idle:     { label: "Idle",     ring: "ring-border",            icon: "text-muted-foreground" },
  starting: { label: "Starting", ring: "ring-amber-400/50",       icon: "text-amber-400" },
  running:  { label: "Live",     ring: "ring-emerald-400/50",     icon: "text-emerald-400" },
  stopped:  { label: "Stopped",  ring: "ring-border",            icon: "text-muted-foreground" },
  error:    { label: "Error",    ring: "ring-destructive/50",     icon: "text-destructive" },
};
