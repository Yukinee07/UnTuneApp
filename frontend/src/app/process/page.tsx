"use client";

import { useEffect, useState } from "react";
import { Upload, Video, Radio, Cpu, BadgeCheck } from "lucide-react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { SettingsPanel } from "@/components/settings-panel";
import { FileTab    } from "@/components/file-tab";
import { YouTubeTab } from "@/components/youtube-tab";
import { LiveTab    } from "@/components/live-tab";
import { api } from "@/lib/api";
import type { ModelInfo, Settings } from "@/lib/types";
import { DEFAULT_SETTINGS } from "@/lib/types";

export default function ProcessPage() {
  const [info, setInfo] = useState<ModelInfo | null>(null);
  const [infoErr, setInfoErr] = useState<string | null>(null);
  const [settings, setSettings] = useState<Settings>(DEFAULT_SETTINGS);

  useEffect(() => {
    api.info()
      .then(setInfo)
      .catch((e) => setInfoErr(e instanceof Error ? e.message : String(e)));
  }, []);

  return (
    <div className="mx-auto w-full max-w-6xl px-4 py-10">
      {/* Header */}
      <div className="mb-8 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-3xl font-semibold tracking-tight md:text-4xl">
            Workspace
          </h1>
          <p className="mt-1 text-muted-foreground">
            Upload a file, paste a URL, or stream live from any app.
          </p>
        </div>
        <ModelBadge info={info} err={infoErr} />
      </div>

      {/* Two-column layout */}
      <div className="grid gap-6 lg:grid-cols-[1fr_320px]">
        {/* Left — main work area */}
        <Tabs defaultValue="file" className="space-y-5">
          <TabsList className="grid grid-cols-3">
            <TabsTrigger value="file"    className="gap-2"><Upload  className="h-4 w-4" />File</TabsTrigger>
            <TabsTrigger value="youtube" className="gap-2"><Video className="h-4 w-4" />YouTube</TabsTrigger>
            <TabsTrigger value="live"    className="gap-2"><Radio   className="h-4 w-4" />Live</TabsTrigger>
          </TabsList>
          <TabsContent value="file">    <FileTab    settings={settings} /></TabsContent>
          <TabsContent value="youtube"> <YouTubeTab settings={settings} /></TabsContent>
          <TabsContent value="live">    <LiveTab    settings={settings} /></TabsContent>
        </Tabs>

        {/* Right — settings */}
        <aside>
          <SettingsPanel value={settings} onChange={setSettings} />
        </aside>
      </div>
    </div>
  );
}

function ModelBadge({
  info, err,
}: { info: ModelInfo | null; err: string | null }) {
  if (err) {
    return (
      <Card className="border-destructive/40 bg-destructive/5">
        <CardContent className="flex items-center gap-2 px-4 py-2 text-xs text-destructive">
          Backend unreachable — start it with{" "}
          <code className="font-mono">python -m uvicorn main:app</code>
        </CardContent>
      </Card>
    );
  }
  if (!info) {
    return <Skeleton className="h-10 w-72" />;
  }
  return (
    <Card className="bg-secondary/40">
      <CardContent className="flex items-center gap-3 px-4 py-2 text-xs">
        <BadgeCheck className="h-4 w-4 text-emerald-400" />
        <span className="font-mono">{info.checkpoint}</span>
        <Badge variant="outline" className="font-mono text-[10px]">epoch {info.epoch}</Badge>
        <span className="text-muted-foreground">·</span>
        <Cpu className="h-3.5 w-3.5 text-primary" />
        <span className="font-mono text-muted-foreground">
          {info.gpu_name ?? info.device}
        </span>
      </CardContent>
    </Card>
  );
}
