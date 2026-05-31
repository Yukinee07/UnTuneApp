"use client";

import { Card, CardContent } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  CheckCircle2, Download, Loader2, AlertCircle, AudioLines,
} from "lucide-react";
import { apiUrl } from "@/lib/api";
import type { Job } from "@/lib/types";

const STATUS_LABEL: Record<Job["status"], string> = {
  queued:      "Queued",
  downloading: "Downloading",
  processing:  "Separating vocals",
  done:        "Done",
  error:       "Failed",
};

export function JobProgress({
  job, error,
}: {
  job: Job | null;
  error: string | null;
}) {
  if (!job && !error) return null;

  if (error && !job) {
    return (
      <Card className="border-destructive/40 bg-destructive/5">
        <CardContent className="flex items-start gap-3 pt-6">
          <AlertCircle className="mt-0.5 h-4 w-4 text-destructive" />
          <p className="text-sm text-destructive">{error}</p>
        </CardContent>
      </Card>
    );
  }
  if (!job) return null;

  const inFlight =
    job.status === "queued" ||
    job.status === "downloading" ||
    job.status === "processing";

  return (
    <Card>
      <CardContent className="space-y-4 pt-6">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            {job.status === "done" ? (
              <CheckCircle2 className="h-4 w-4 text-emerald-400" />
            ) : job.status === "error" ? (
              <AlertCircle className="h-4 w-4 text-destructive" />
            ) : (
              <Loader2 className="h-4 w-4 animate-spin text-primary" />
            )}
            <span className="text-sm font-medium">{STATUS_LABEL[job.status]}</span>
            <Badge variant="outline" className="font-mono text-[10px]">
              {job.id}
            </Badge>
          </div>
          <span className="font-mono text-xs text-muted-foreground">
            {Math.round(job.progress)}%
          </span>
        </div>

        <Progress value={job.progress} />

        {(job.message || job.error) && (
          <p className="text-xs text-muted-foreground">
            {job.status === "error" ? job.error : job.message}
          </p>
        )}

        {job.status === "done" && job.output_url && (
          <div className="space-y-3 pt-1">
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              <AudioLines className="h-3.5 w-3.5 text-primary" />
              Vocal stem · {job.duration_s?.toFixed(1) ?? "?"} s
            </div>
            <audio
              controls
              className="w-full"
              src={apiUrl(job.output_url)}
            />
            <Button
              render={<a href={apiUrl(job.output_url)} download />}
              variant="secondary"
              size="sm"
              className="w-full"
            >
              <Download className="mr-2 h-4 w-4" />
              Download .wav
            </Button>
          </div>
        )}

        {inFlight && (
          <p className="text-[11px] text-muted-foreground/70">
            Tip: a 4-minute song takes about 30 s on an RTX 4060.
          </p>
        )}
      </CardContent>
    </Card>
  );
}
