import Link from "next/link";
import {
  ArrowRight, Mic, Music, Cpu, Zap, AudioLines, Code2, Sparkles,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

export default function HomePage() {
  return (
    <div className="flex flex-col">
      {/* ─── Hero ──────────────────────────────────────────────────── */}
      <section className="bg-radial-violet relative overflow-hidden">
        <div className="mx-auto flex max-w-6xl flex-col items-center px-4 py-24 text-center md:py-32">
          <Badge variant="outline" className="mb-6 gap-1.5 border-primary/40 bg-primary/5 text-primary">
            <Sparkles className="h-3 w-3" />
            HS-TasNet v12 · running on your GPU
          </Badge>

          <h1 className="max-w-3xl text-balance text-5xl font-semibold tracking-tight md:text-7xl">
            Strip the music.{" "}
            <span className="text-gradient-violet-cyan">Keep the voice.</span>
          </h1>

          <p className="mt-6 max-w-2xl text-balance text-lg text-muted-foreground md:text-xl">
            Real-time vocal isolation powered by a 30M-parameter neural network.
            Upload a song, paste a YouTube link, or strip vocals live from any
            app on your laptop.
          </p>

          <div className="mt-10 flex flex-wrap items-center justify-center gap-3">
            <Button render={<Link href="/process" />} size="lg" className="text-base">
              Open Workspace
              <ArrowRight className="ml-1.5 h-4 w-4" />
            </Button>
            <Button
              render={<Link href="#how" />}
              variant="secondary"
              size="lg"
              className="text-base"
            >
              How it works
            </Button>
          </div>

          {/* Decorative EQ bars */}
          <div className="mt-16 flex h-16 items-end gap-1.5">
            {Array.from({ length: 24 }).map((_, i) => (
              <span
                key={i}
                className="eq-bar w-1.5 rounded-full bg-gradient-to-t from-primary/60 to-accent/80"
                style={{
                  height: `${30 + Math.sin(i * 0.6) * 30 + ((i * 53) % 30)}%`,
                  animationDelay: `${(i % 8) * 0.1}s`,
                }}
              />
            ))}
          </div>
        </div>
      </section>

      {/* ─── How it works ─────────────────────────────────────────── */}
      <section id="how" className="mx-auto w-full max-w-6xl px-4 py-20">
        <div className="mb-12 text-center">
          <h2 className="text-3xl font-semibold tracking-tight md:text-4xl">
            How it works
          </h2>
          <p className="mt-3 text-muted-foreground">
            A dual-branch neural network learns what voice looks like — and
            keeps only that.
          </p>
        </div>

        <div className="grid gap-4 md:grid-cols-3">
          <StepCard
            n={1}
            title="Audio in"
            icon={<Music className="h-5 w-5" />}
            body="The full stereo mixture — singer + drums + bass + everything else — arrives 372 ms at a time, or all at once if you upload a file."
          />
          <StepCard
            n={2}
            title="HS-TasNet v12"
            icon={<Cpu className="h-5 w-5" />}
            body="Two encoders (STFT + learned convolution) and five stacked LSTM blocks predict a complex mask per time-frequency bin: keep vocals, suppress music."
          />
          <StepCard
            n={3}
            title="Vocals out"
            icon={<Mic className="h-5 w-5" />}
            body="The mask is applied, the audio is decoded back to waveform, levelled, and either downloaded or played straight to your speakers — all on the GPU."
          />
        </div>
      </section>

      {/* ─── Specs ────────────────────────────────────────────────── */}
      <section className="border-y border-border/60 bg-secondary/20">
        <div className="mx-auto grid max-w-6xl gap-6 px-4 py-16 md:grid-cols-4">
          <Stat
            icon={<Zap className="h-4 w-4 text-primary" />}
            label="End-to-end latency"
            value="~190 ms"
            note="With auto-levelling on at 8192-sample blocks"
          />
          <Stat
            icon={<Cpu className="h-4 w-4 text-primary" />}
            label="GPU"
            value="RTX 4060"
            note="CUDA 12.8 · ~20 ms inference per chunk"
          />
          <Stat
            icon={<AudioLines className="h-4 w-4 text-primary" />}
            label="Model"
            value="30M params"
            note="v13 best.pt · val_loss −38.28 @ epoch 43"
          />
          <Stat
            icon={<Music className="h-4 w-4 text-primary" />}
            label="Training data"
            value="MUSDB18-HQ"
            note="150 songs · 5 isolated stems each"
          />
        </div>
      </section>

      {/* ─── CTA ──────────────────────────────────────────────────── */}
      <section className="mx-auto w-full max-w-3xl px-4 py-24 text-center">
        <h2 className="text-3xl font-semibold tracking-tight">
          Try it on your own song
        </h2>
        <p className="mt-3 text-muted-foreground">
          The workspace runs entirely on this machine. Nothing uploaded
          leaves your laptop.
        </p>
        <div className="mt-8">
          <Button render={<Link href="/process" />} size="lg">
            Open Workspace
            <ArrowRight className="ml-1.5 h-4 w-4" />
          </Button>
        </div>
      </section>

      <footer className="border-t border-border/60">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-6 text-xs text-muted-foreground">
          <span>VocalApp · FYP demo</span>
          <a
            href="https://github.com/"
            target="_blank"
            rel="noreferrer"
            className="flex items-center gap-1.5 hover:text-foreground"
          >
            <Code2 className="h-3.5 w-3.5" />
            Source
          </a>
        </div>
      </footer>
    </div>
  );
}

function StepCard({
  n, title, icon, body,
}: { n: number; title: string; icon: React.ReactNode; body: string }) {
  return (
    <Card className="relative overflow-hidden">
      <CardContent className="space-y-3 pt-6">
        <div className="flex items-center justify-between">
          <div className="grid h-9 w-9 place-items-center rounded-md bg-primary/15 text-primary ring-1 ring-primary/30">
            {icon}
          </div>
          <span className="font-mono text-xs text-muted-foreground/70">0{n}</span>
        </div>
        <h3 className="text-lg font-semibold">{title}</h3>
        <p className="text-sm text-muted-foreground">{body}</p>
      </CardContent>
    </Card>
  );
}

function Stat({
  icon, label, value, note,
}: { icon: React.ReactNode; label: string; value: string; note: string }) {
  return (
    <div className="space-y-1.5">
      <div className="flex items-center gap-2 text-xs uppercase tracking-wide text-muted-foreground">
        {icon}
        {label}
      </div>
      <p className="text-2xl font-semibold tracking-tight">{value}</p>
      <p className="text-xs text-muted-foreground">{note}</p>
    </div>
  );
}
