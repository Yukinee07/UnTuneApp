"use client";

import { useEffect, useMemo, useState } from "react";
import { Upload, Video, Radio, Cpu, BadgeCheck, Sparkles } from "lucide-react";
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
import { DEFAULT_FILE_SETTINGS, DEFAULT_LIVE_SETTINGS } from "@/lib/types";

type Mode = "file" | "youtube" | "live";

export default function ProcessPage() {
  const [info,    setInfo]    = useState<ModelInfo | null>(null);
  const [infoErr, setInfoErr] = useState<string | null>(null);

  const [mode,         setMode]         = useState<Mode>("file");
  const [fileSettings, setFileSettings] = useState<Settings>(DEFAULT_FILE_SETTINGS);
  const [ytSettings,   setYtSettings]   = useState<Settings>(DEFAULT_FILE_SETTINGS);
  const [liveSettings, setLiveSettings] = useState<Settings>(DEFAULT_LIVE_SETTINGS);

  useEffect(() => {
    api.info()
      .then(setInfo)
      .catch((e) => setInfoErr(e instanceof Error ? e.message : String(e)));
  }, []);

  const panelBinding = useMemo(() => {
    switch (mode) {
      case "file":
        return {
          value:    fileSettings,
          onChange: setFileSettings,
          defaults: DEFAULT_FILE_SETTINGS,
          label:    "File",
          chunking: true,
        };
      case "youtube":
        return {
          value:    ytSettings,
          onChange: setYtSettings,
          defaults: DEFAULT_FILE_SETTINGS,
          label:    "YouTube",
          chunking: true,
        };
      case "live":
        return {
          value:    liveSettings,
          onChange: setLiveSettings,
          defaults: DEFAULT_LIVE_SETTINGS,
          label:    "Live",
          chunking: false,
        };
    }
  }, [mode, fileSettings, ytSettings, liveSettings]);

  return (
    <div className="relative min-h-screen overflow-hidden">
      {/* ─── Vibrant background — same atmospheric language as the landing,
            slightly dialled back so the workspace stays usable ─── */}
      <div className="absolute inset-0 bg-mesh-violet pointer-events-none" />
      <div className="orb orb-violet -left-40 top-20 h-[26rem] w-[26rem] opacity-70" />
      <div className="orb orb-cyan   right-[-12%] top-[30%] h-[22rem] w-[22rem] opacity-60" />
      <div className="orb orb-violet bottom-[-10%] left-[20%] h-[24rem] w-[24rem] opacity-60" />
      <div className="absolute inset-0 noise pointer-events-none opacity-70" />

      {/* Content — generous left padding so the floating Home icon has its
          own real estate at left-6 / w-14 without colliding with content */}
      <div className="relative mx-auto w-full max-w-6xl px-6 pl-24 lg:pl-28 py-14">
        {/* ─── Header — title block + glowing model badge ────────────── */}
        <div className="mb-10 flex flex-wrap items-end justify-between gap-4 animate-fade-in-up">
          <div>
            <p className="font-mono text-[11px] uppercase tracking-[0.22em] text-primary">
              Workspace
            </p>
            <h1 className="mt-3 text-balance text-4xl font-bold tracking-tight md:text-5xl">
              <span className="text-gradient-violet-cyan">Strip the music.</span>
              <br />
              <span className="text-foreground">Three ways in.</span>
            </h1>
            <p className="mt-3 max-w-md text-sm text-muted-foreground md:text-base">
              File · YouTube · Live system audio. Same model, your hardware.
            </p>
          </div>
          <ModelBadge info={info} err={infoErr} />
        </div>

        {/* ─── Two-column layout — tabs + sticky settings panel ─────── */}
        <div className="grid gap-6 lg:grid-cols-[1fr_320px]">
          <Tabs
            value={mode}
            onValueChange={(v) => setMode(v as Mode)}
            className="space-y-5"
          >
            <TabsList className="grid grid-cols-3 bg-background/60 backdrop-blur-md ring-1 ring-border shadow-sm">
              <TabsTrigger value="file"    className="gap-2 transition-all data-[state=active]:shadow-md data-[state=active]:shadow-primary/30">
                <Upload className="h-4 w-4" />File
              </TabsTrigger>
              <TabsTrigger value="youtube" className="gap-2 transition-all data-[state=active]:shadow-md data-[state=active]:shadow-primary/30">
                <Video className="h-4 w-4" />YouTube
              </TabsTrigger>
              <TabsTrigger value="live"    className="gap-2 transition-all data-[state=active]:shadow-md data-[state=active]:shadow-primary/30">
                <Radio className="h-4 w-4" />Live
              </TabsTrigger>
            </TabsList>

            <TabsContent value="file"    className="animate-fade-in-up"><FileTab    settings={fileSettings} /></TabsContent>
            <TabsContent value="youtube" className="animate-fade-in-up"><YouTubeTab settings={ytSettings}   /></TabsContent>
            <TabsContent value="live"    className="animate-fade-in-up"><LiveTab    settings={liveSettings} /></TabsContent>
          </Tabs>

          <aside className="animate-fade-in-up">
            <SettingsPanel
              value={panelBinding.value}
              onChange={panelBinding.onChange}
              defaults={panelBinding.defaults}
              modeLabel={panelBinding.label}
              showChunking={panelBinding.chunking}
            />
          </aside>
        </div>
      </div>
    </div>
  );
}

/* ─────────────────────────────────────────────────────────────────────── */
/* Model badge — glassy, glowing, animates in                              */
/* ─────────────────────────────────────────────────────────────────────── */

function ModelBadge({
  info, err,
}: { info: ModelInfo | null; err: string | null }) {
  if (err) {
    return (
      <Card className="border-destructive/40 bg-destructive/5 animate-fade-in-up">
        <CardContent className="flex items-center gap-2 px-4 py-2 text-xs text-destructive">
          Backend unreachable — start it with{" "}
          <code className="font-mono">python -m uvicorn main:app</code>
        </CardContent>
      </Card>
    );
  }
  if (!info) {
    return <Skeleton className="h-12 w-80" />;
  }
  return (
    <Card className="card-glass glow-primary card-lift">
      <CardContent className="flex items-center gap-3 px-4 py-3 text-xs">
        <Sparkles className="h-4 w-4 text-primary" />
        <span className="font-mono font-semibold text-foreground">{info.checkpoint}</span>
        <Badge variant="outline" className="border-primary/40 bg-primary/10 font-mono text-[10px] text-primary">
          epoch {info.epoch}
        </Badge>
        <span className="text-muted-foreground">·</span>
        <BadgeCheck className="h-3.5 w-3.5 text-emerald-400" />
        <span className="text-emerald-400 text-[11px] font-semibold uppercase tracking-wider">live</span>
        <span className="text-muted-foreground">·</span>
        <Cpu className="h-3.5 w-3.5 text-primary" />
        <span className="font-mono text-muted-foreground">
          {info.gpu_name ?? info.device}
        </span>
      </CardContent>
    </Card>
  );
}
