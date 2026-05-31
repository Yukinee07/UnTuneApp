"use client";

import { useRef, useState } from "react";
import { Upload, FileAudio, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { api } from "@/lib/api";
import { useJob } from "@/lib/use-job";
import type { Settings } from "@/lib/types";
import { JobProgress } from "./job-progress";
import { toast } from "sonner";
import { cn } from "@/lib/utils";

const ACCEPT = "audio/*,video/*,.mp3,.wav,.m4a,.flac,.ogg,.mp4,.mov,.mkv,.webm";

export function FileTab({ settings }: { settings: Settings }) {
  const [file, setFile]         = useState<File | null>(null);
  const [dragging, setDragging] = useState(false);
  const [busy,     setBusy]     = useState(false);
  const [jobId,    setJobId]    = useState<string | null>(null);
  const inputRef                = useRef<HTMLInputElement>(null);

  const { job, error } = useJob(jobId);

  const pick = () => inputRef.current?.click();
  const clear = () => {
    setFile(null);
    setJobId(null);
    if (inputRef.current) inputRef.current.value = "";
  };

  const submit = async () => {
    if (!file) return;
    setBusy(true);
    try {
      const j = await api.submitFile(file, settings);
      setJobId(j.id);
      toast.success(`Queued · ${file.name}`);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-6">
      <Card
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          const f = e.dataTransfer.files?.[0];
          if (f) setFile(f);
        }}
        className={cn(
          "border-2 border-dashed transition-colors",
          dragging
            ? "border-primary bg-primary/5"
            : "border-border/60 hover:border-primary/50",
        )}
      >
        <CardContent className="flex flex-col items-center justify-center gap-3 py-12 text-center">
          {file ? (
            <>
              <div className="grid h-12 w-12 place-items-center rounded-full bg-primary/15 text-primary ring-1 ring-primary/30">
                <FileAudio className="h-6 w-6" />
              </div>
              <div className="space-y-1">
                <p className="font-medium">{file.name}</p>
                <p className="text-xs text-muted-foreground">
                  {(file.size / 1024 / 1024).toFixed(1)} MB · {file.type || "unknown"}
                </p>
              </div>
              <div className="flex gap-2 pt-1">
                <Button onClick={submit} disabled={busy}>
                  {busy ? "Sending…" : "Separate vocals"}
                </Button>
                <Button variant="ghost" onClick={clear} disabled={busy}>
                  <X className="mr-1 h-4 w-4" />
                  Clear
                </Button>
              </div>
            </>
          ) : (
            <>
              <div className="grid h-12 w-12 place-items-center rounded-full bg-secondary text-muted-foreground">
                <Upload className="h-6 w-6" />
              </div>
              <div className="space-y-1">
                <p className="font-medium">Drop a file here</p>
                <p className="text-xs text-muted-foreground">
                  audio or video — mp3, wav, m4a, flac, mp4, mov, mkv, webm…
                </p>
              </div>
              <Button variant="secondary" onClick={pick}>
                Choose file
              </Button>
              <input
                ref={inputRef}
                type="file"
                hidden
                accept={ACCEPT}
                onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              />
            </>
          )}
        </CardContent>
      </Card>

      <JobProgress job={job} error={error} />
    </div>
  );
}
