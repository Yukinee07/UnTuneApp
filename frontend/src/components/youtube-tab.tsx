"use client";

import { useState } from "react";
import { Link2, Loader2, Video } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { api } from "@/lib/api";
import { useJob } from "@/lib/use-job";
import type { Settings, YouTubeProbe } from "@/lib/types";
import { JobProgress } from "./job-progress";
import { toast } from "sonner";

export function YouTubeTab({ settings }: { settings: Settings }) {
  const [url, setUrl]       = useState("");
  const [probe, setProbe]   = useState<YouTubeProbe | null>(null);
  const [probing, setProbing] = useState(false);
  const [busy,  setBusy]    = useState(false);
  const [jobId, setJobId]   = useState<string | null>(null);

  const { job, error } = useJob(jobId);

  const doProbe = async () => {
    if (!url.trim()) return;
    setProbing(true);
    setProbe(null);
    try {
      const p = await api.probeYouTube(url.trim());
      setProbe(p);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : String(e));
    } finally {
      setProbing(false);
    }
  };

  const submit = async () => {
    if (!url.trim()) return;
    setBusy(true);
    try {
      const j = await api.submitYouTube(url.trim(), settings);
      setJobId(j.id);
      toast.success("Queued — downloading first, then separating.");
    } catch (e) {
      toast.error(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const fmtDuration = (s: number | null) => {
    if (!s) return "?";
    const m = Math.floor(s / 60);
    const r = Math.floor(s % 60).toString().padStart(2, "0");
    return `${m}:${r}`;
  };
  const tooLong = probe?.duration_s != null && probe.duration_s > 600;

  return (
    <div className="space-y-6">
      <Card>
        <CardContent className="space-y-4 pt-6">
          <div className="space-y-2">
            <Label htmlFor="yt-url" className="flex items-center gap-2 text-sm">
              <Video className="h-4 w-4 text-primary" />
              YouTube, SoundCloud, direct mp3, or any yt-dlp-supported URL
            </Label>
            <div className="flex gap-2">
              <Input
                id="yt-url"
                value={url}
                onChange={(e) => { setUrl(e.target.value); setProbe(null); }}
                placeholder="https://www.youtube.com/watch?v=…"
                className="font-mono text-sm"
              />
              <Button
                type="button"
                variant="secondary"
                onClick={doProbe}
                disabled={!url.trim() || probing}
              >
                {probing ? <Loader2 className="h-4 w-4 animate-spin" /> : <Link2 className="h-4 w-4" />}
                <span className="ml-2">Preview</span>
              </Button>
            </div>
          </div>

          {probe && (
            <div className="flex gap-4 rounded-lg border border-border/60 bg-secondary/30 p-3">
              {probe.thumbnail && (
                /* eslint-disable-next-line @next/next/no-img-element */
                <img
                  src={probe.thumbnail}
                  alt=""
                  className="h-20 w-32 rounded object-cover ring-1 ring-border/60"
                />
              )}
              <div className="min-w-0 flex-1 space-y-1">
                <p className="truncate font-medium">{probe.title ?? "(no title)"}</p>
                {probe.uploader && (
                  <p className="text-xs text-muted-foreground">{probe.uploader}</p>
                )}
                <p className="font-mono text-xs text-muted-foreground">
                  {fmtDuration(probe.duration_s)}
                  {tooLong && (
                    <span className="ml-2 text-amber-400">
                      · long video — separation may take a minute or two
                    </span>
                  )}
                </p>
              </div>
            </div>
          )}

          <Button
            onClick={submit}
            disabled={!url.trim() || busy}
            className="w-full"
          >
            {busy ? "Sending…" : "Download & separate vocals"}
          </Button>
        </CardContent>
      </Card>

      <JobProgress job={job} error={error} />
    </div>
  );
}
