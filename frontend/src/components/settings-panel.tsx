"use client";

import { Slider } from "@/components/ui/slider";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Settings as SettingsIcon, RotateCcw } from "lucide-react";
import { Button } from "@/components/ui/button";
import type { Settings } from "@/lib/types";
import { DEFAULT_FILE_SETTINGS } from "@/lib/types";

type Props = {
  value: Settings;
  onChange: (next: Settings) => void;
  /** show chunk_sec / overlap_sec — only relevant for file/youtube modes */
  showChunking?: boolean;
  /** mode-specific defaults the Reset button restores.  Defaults to file/CLI. */
  defaults?: Settings;
  /** short tag rendered in the header — "File", "YouTube", "Live" */
  modeLabel?: string;
};

export function SettingsPanel({
  value,
  onChange,
  showChunking = true,
  defaults = DEFAULT_FILE_SETTINGS,
  modeLabel,
}: Props) {
  const set = <K extends keyof Settings>(k: K, v: Settings[K]) =>
    onChange({ ...value, [k]: v });

  // Visual cue that the user has drifted from the defaults — Reset glows
  // primary instead of muted so it's discoverable when it would actually
  // do something.
  const dirty =
    value.mask_smooth !== defaults.mask_smooth ||
    value.target_rms  !== defaults.target_rms  ||
    value.gain_db     !== defaults.gain_db     ||
    (showChunking && (
      value.chunk_sec   !== defaults.chunk_sec ||
      value.overlap_sec !== defaults.overlap_sec
    ));

  return (
    <Card className="sticky top-20">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2 text-base">
            <SettingsIcon className="h-4 w-4 text-primary" />
            Settings
            {modeLabel && (
              <span className="rounded bg-secondary px-1.5 py-0.5 text-[10px] font-normal uppercase tracking-wide text-muted-foreground">
                {modeLabel}
              </span>
            )}
          </CardTitle>
          <Button
            variant={dirty ? "secondary" : "ghost"}
            size="sm"
            className="h-7 px-2 text-xs"
            onClick={() => onChange(defaults)}
            disabled={!dirty}
            title={dirty ? "Restore defaults" : "Already at defaults"}
          >
            <RotateCcw className="mr-1 h-3 w-3" />
            Reset
          </Button>
        </div>
        <CardDescription className="text-xs">
          {modeLabel === "Live"
            ? "Live monitoring defaults: smoothing on, levels normalised."
            : "Clean offline defaults: raw mask, original dynamics, +3 dB lift."}
        </CardDescription>
      </CardHeader>

      <CardContent className="space-y-5">
        <Row
          label="Mask smoothing"
          hint="Removes 'watery' artefacts. Higher = smoother but blurs fast consonants."
          value={value.mask_smooth}
          unit="frames"
        >
          <Slider
            min={1}
            max={7}
            step={1}
            value={[value.mask_smooth]}
            onValueChange={(v) => set("mask_smooth", Array.isArray(v) ? v[0] : v)}
          />
          <Marks marks={[1, 3, 5, 7]} />
        </Row>

        <Row
          label="Target loudness (RMS)"
          hint="0 = leave the raw model output alone. 0.12 ≈ −18 dBFS, comfortable."
          value={value.target_rms.toFixed(2)}
          unit="RMS"
        >
          <Slider
            min={0}
            max={0.3}
            step={0.01}
            value={[value.target_rms]}
            onValueChange={(v) => set("target_rms", Array.isArray(v) ? v[0] : v)}
          />
          <Marks marks={["off", "soft", "loud"]} />
        </Row>

        <Row
          label="Output gain"
          hint="Final boost in dB. Applied after the auto-leveller."
          value={`${value.gain_db > 0 ? "+" : ""}${value.gain_db.toFixed(1)}`}
          unit="dB"
        >
          <Slider
            min={-6}
            max={12}
            step={0.5}
            value={[value.gain_db]}
            onValueChange={(v) => set("gain_db", Array.isArray(v) ? v[0] : v)}
          />
          <Marks marks={["−6", "0", "+12"]} />
        </Row>

        {showChunking && (
          <>
            <hr className="border-border/60" />
            <Row
              label="Chunk length"
              hint="Window the model processes at a time. Longer = more LSTM context."
              value={value.chunk_sec.toFixed(0)}
              unit="s"
            >
              <Slider
                min={2}
                max={30}
                step={1}
                value={[value.chunk_sec]}
                onValueChange={(v) => set("chunk_sec", Array.isArray(v) ? v[0] : v)}
              />
            </Row>

            <Row
              label="Overlap"
              hint="Cross-fade between chunks. Reduces boundary artefacts."
              value={value.overlap_sec.toFixed(1)}
              unit="s"
            >
              <Slider
                min={0}
                max={5}
                step={0.5}
                value={[value.overlap_sec]}
                onValueChange={(v) => set("overlap_sec", Array.isArray(v) ? v[0] : v)}
              />
            </Row>
          </>
        )}
      </CardContent>
    </Card>
  );
}

// ── Internals ─────────────────────────────────────────────────────────

function Row({
  label, hint, value, unit, children,
}: {
  label: string;
  hint: string;
  value: string | number;
  unit?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-2">
      <div className="flex items-baseline justify-between">
        <Label className="text-sm">{label}</Label>
        <Badge variant="secondary" className="font-mono text-xs">
          {value}{unit ? <span className="ml-1 text-muted-foreground">{unit}</span> : null}
        </Badge>
      </div>
      {children}
      <p className="text-xs text-muted-foreground">{hint}</p>
    </div>
  );
}

function Marks({ marks }: { marks: (string | number)[] }) {
  return (
    <div className="flex justify-between px-1 pt-0.5 text-[10px] text-muted-foreground/70">
      {marks.map((m) => (
        <span key={String(m)}>{m}</span>
      ))}
    </div>
  );
}
