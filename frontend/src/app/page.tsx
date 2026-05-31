import Link from "next/link";
import {
  ArrowRight, Mic, Music, Cpu, Zap, AudioLines, Code2, Sparkles,
  Upload, Video, Radio, ChevronDown, Layers, Waves,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Logo } from "@/components/logo";

export default function HomePage() {
  return (
    <div className="flex flex-col">
      {/* ── Hero ──────────────────────────────────────────────────────── */}
      <Hero />

      {/* ── The magic — animated dual-waveform reveal ─────────────────── */}
      <MagicSection />

      {/* ── How it works ──────────────────────────────────────────────── */}
      <HowSection />

      {/* ── Specs strip ────────────────────────────────────────────────── */}
      <SpecsStrip />

      {/* ── Three modes ───────────────────────────────────────────────── */}
      <ModesSection />

      {/* ── Final CTA ─────────────────────────────────────────────────── */}
      <FinalCTA />

      <Footer />
    </div>
  );
}

/* ─────────────────────────────────────────────────────────────────────── */
/* Hero                                                                    */
/* ─────────────────────────────────────────────────────────────────────── */

function Hero() {
  return (
    <section className="bg-mesh-violet relative overflow-hidden">
      {/* Faint dotted grid overlay for texture */}
      <div className="absolute inset-0 bg-dots opacity-40 pointer-events-none" />

      <div className="relative mx-auto flex max-w-6xl flex-col items-center px-4 py-24 text-center md:py-36">
        <Badge variant="outline" className="mb-6 gap-1.5 border-primary/40 bg-primary/5 text-primary backdrop-blur-sm">
          <Sparkles className="h-3 w-3" />
          HS-TasNet v12 · running on your GPU
        </Badge>

        <h1 className="max-w-4xl text-balance text-5xl font-semibold leading-[1.05] tracking-tight md:text-7xl lg:text-[5.5rem]">
          The internet is loud.{" "}
          <span className="text-gradient-violet-cyan">Mute the&nbsp;</span>
          <span className="text-gradient-violet-cyan strike-line">music.</span>
        </h1>

        <p className="mt-8 max-w-2xl text-balance text-lg text-muted-foreground md:text-xl">
          UnTuneApp pulls the vocals out of any song, video, or live stream
          in real time. No cloud round-trip — your RTX 4060 does the work.
        </p>

        <div className="mt-10 flex flex-wrap items-center justify-center gap-3">
          <Button render={<Link href="/process" />} size="lg" className="text-base">
            Open Workspace
            <ArrowRight className="ml-1.5 h-4 w-4" />
          </Button>
          <Button render={<Link href="#magic" />} variant="secondary" size="lg" className="text-base">
            See it work
            <ChevronDown className="ml-1.5 h-4 w-4" />
          </Button>
        </div>

        {/* Animated EQ bars centred under the CTAs */}
        <div className="mt-20 flex h-20 items-end gap-1.5">
          {Array.from({ length: 28 }).map((_, i) => (
            <span
              key={i}
              className="eq-bar w-1.5 rounded-full bg-gradient-to-t from-primary/60 to-accent/80"
              style={{
                height: `${30 + Math.sin(i * 0.7) * 30 + ((i * 53) % 30)}%`,
                animationDelay: `${(i % 10) * 0.1}s`,
              }}
            />
          ))}
        </div>
      </div>
    </section>
  );
}

/* ─────────────────────────────────────────────────────────────────────── */
/* "Watch the music disappear" — the headline visual                       */
/* ─────────────────────────────────────────────────────────────────────── */

function MagicSection() {
  return (
    <section id="magic" className="relative mx-auto w-full max-w-6xl px-4 py-24">
      <div className="mb-14 text-center">
        <Badge variant="secondary" className="mb-4">The magic</Badge>
        <h2 className="text-balance text-4xl font-semibold tracking-tight md:text-5xl">
          Watch the music{" "}
          <span className="text-gradient-violet-cyan">disappear</span>.
        </h2>
        <p className="mx-auto mt-3 max-w-xl text-muted-foreground">
          27 ms of GPU inference. 200 ms end-to-end. Indistinguishable
          from instant.
        </p>
      </div>

      <Card className="card-glass overflow-hidden">
        <CardContent className="grid gap-0 p-0 md:grid-cols-[1fr_auto_1fr]">
          {/* BEFORE */}
          <div className="space-y-4 p-8">
            <div className="flex items-center justify-between">
              <span className="text-xs uppercase tracking-widest text-muted-foreground">Mixture in</span>
              <Layers className="h-4 w-4 text-muted-foreground" />
            </div>
            <div className="flex h-24 items-end gap-1">
              {Array.from({ length: 48 }).map((_, i) => {
                const a = Math.abs(Math.sin(i * 0.42)) * 60 + 20;
                const b = Math.abs(Math.cos(i * 0.55 + 1)) * 40 + 10;
                return (
                  <div key={i} className="flex-1 space-y-0.5">
                    <div
                      className="eq-bar rounded-sm bg-accent/80"
                      style={{ height: `${b}%`, animationDelay: `${(i * 0.06) % 1.2}s` }}
                    />
                    <div
                      className="eq-bar rounded-sm bg-primary/80"
                      style={{ height: `${a}%`, animationDelay: `${(i * 0.04 + 0.3) % 1.2}s` }}
                    />
                  </div>
                );
              })}
            </div>
            <div className="flex flex-wrap gap-1.5">
              <TinyTag color="primary">vocals</TinyTag>
              <TinyTag color="accent">drums</TinyTag>
              <TinyTag color="primary">bass</TinyTag>
              <TinyTag color="accent">guitar</TinyTag>
              <TinyTag color="primary">keys</TinyTag>
            </div>
          </div>

          {/* ARROW */}
          <div className="flex items-center justify-center px-2 py-4 md:px-8">
            <div className="grid h-12 w-12 place-items-center rounded-full bg-primary/15 text-primary ring-1 ring-primary/30">
              <ArrowRight className="h-5 w-5" />
            </div>
          </div>

          {/* AFTER */}
          <div className="space-y-4 border-t border-border/60 p-8 md:border-t-0 md:border-l">
            <div className="flex items-center justify-between">
              <span className="text-xs uppercase tracking-widest text-primary">Vocals only</span>
              <Waves className="h-4 w-4 text-primary" />
            </div>
            <div className="flex h-24 items-end gap-1">
              {Array.from({ length: 48 }).map((_, i) => {
                const v = Math.abs(Math.sin(i * 0.38)) * 65 + 15;
                return (
                  <div
                    key={i}
                    className="eq-bar flex-1 rounded-sm bg-gradient-to-t from-primary to-accent"
                    style={{ height: `${v}%`, animationDelay: `${(i * 0.07) % 1.4}s` }}
                  />
                );
              })}
            </div>
            <div>
              <TinyTag color="primary">vocals</TinyTag>
            </div>
          </div>
        </CardContent>
      </Card>
    </section>
  );
}

function TinyTag({ children, color }: { children: React.ReactNode; color: "primary" | "accent" }) {
  return (
    <span className={
      "rounded-full px-2 py-0.5 font-mono text-[10px] uppercase tracking-wider " +
      (color === "primary"
        ? "bg-primary/15 text-primary ring-1 ring-primary/30"
        : "bg-accent/15 text-accent  ring-1 ring-accent/30")
    }>
      {children}
    </span>
  );
}

/* ─────────────────────────────────────────────────────────────────────── */
/* How it works                                                            */
/* ─────────────────────────────────────────────────────────────────────── */

function HowSection() {
  return (
    <section className="relative bg-dots/40">
      <div className="mx-auto w-full max-w-6xl px-4 py-24">
        <div className="mb-14 text-center">
          <Badge variant="secondary" className="mb-4">How it works</Badge>
          <h2 className="text-balance text-4xl font-semibold tracking-tight md:text-5xl">
            Three steps. Two layers. <span className="text-gradient-violet-cyan">One voice.</span>
          </h2>
        </div>

        {/* Connector line behind the cards on desktop */}
        <div className="relative grid gap-6 md:grid-cols-3">
          <div className="pointer-events-none absolute left-[16.7%] right-[16.7%] top-12 hidden h-px md:block bg-gradient-to-r from-transparent via-primary/40 to-transparent" />

          <StepCard
            n="01"
            title="Audio in"
            icon={<Music className="h-5 w-5" />}
            body="The full stereo mixture — singer, drums, bass, the lot — arrives 372 ms at a time, or all at once if you upload a file."
          />
          <StepCard
            n="02"
            title="HS-TasNet v12"
            icon={<Cpu className="h-5 w-5" />}
            body="Two encoders — STFT spectrogram + learned convolution — feed five LSTM blocks that predict a complex mask per time-frequency bin."
            highlight
          />
          <StepCard
            n="03"
            title="Vocals out"
            icon={<Mic className="h-5 w-5" />}
            body="The mask is applied, the audio is decoded back to waveform, auto-levelled, then handed straight to your speakers or saved as .wav."
          />
        </div>
      </div>
    </section>
  );
}

function StepCard({
  n, title, icon, body, highlight = false,
}: {
  n: string; title: string; icon: React.ReactNode; body: string; highlight?: boolean;
}) {
  return (
    <Card className={
      "relative overflow-hidden transition-transform hover:-translate-y-0.5 " +
      (highlight ? "ring-1 ring-primary/40 bg-primary/[0.03]" : "")
    }>
      <CardContent className="space-y-4 pt-6">
        <div className="flex items-center justify-between">
          <div className="grid h-10 w-10 place-items-center rounded-lg bg-primary/15 text-primary ring-1 ring-primary/30">
            {icon}
          </div>
          <span className="step-num font-mono text-2xl text-muted-foreground/40">{n}</span>
        </div>
        <h3 className="text-xl font-semibold">{title}</h3>
        <p className="text-sm leading-relaxed text-muted-foreground">{body}</p>
      </CardContent>
    </Card>
  );
}

/* ─────────────────────────────────────────────────────────────────────── */
/* Specs strip                                                             */
/* ─────────────────────────────────────────────────────────────────────── */

function SpecsStrip() {
  return (
    <section className="border-y border-border/60 bg-secondary/20">
      <div className="mx-auto grid max-w-6xl gap-px overflow-hidden rounded-lg border border-border/40 my-12 md:grid-cols-4 mx-4">
        <Stat icon={<Zap        className="h-4 w-4 text-primary" />} label="End-to-end latency" value="~190 ms" note="Auto-levelling on, 8192-sample blocks" />
        <Stat icon={<Cpu        className="h-4 w-4 text-primary" />} label="GPU"               value="RTX 4060" note="CUDA 12.8 · ~27 ms per chunk" />
        <Stat icon={<AudioLines className="h-4 w-4 text-primary" />} label="Model"             value="30M params" note="v13 best.pt · val_loss −38.28 @ epoch 43" />
        <Stat icon={<Music      className="h-4 w-4 text-primary" />} label="Training set"      value="MUSDB18-HQ" note="150 songs · 5 isolated stems each" />
      </div>
    </section>
  );
}

function Stat({
  icon, label, value, note,
}: { icon: React.ReactNode; label: string; value: string; note: string }) {
  return (
    <div className="card-glass space-y-1.5 bg-background/40 px-6 py-7">
      <div className="flex items-center gap-2 text-[10px] uppercase tracking-widest text-muted-foreground">
        {icon}
        {label}
      </div>
      <p className="text-2xl font-semibold tracking-tight">{value}</p>
      <p className="text-xs text-muted-foreground">{note}</p>
    </div>
  );
}

/* ─────────────────────────────────────────────────────────────────────── */
/* Three ways to use it                                                    */
/* ─────────────────────────────────────────────────────────────────────── */

function ModesSection() {
  return (
    <section className="mx-auto w-full max-w-6xl px-4 py-24">
      <div className="mb-14 text-center">
        <Badge variant="secondary" className="mb-4">Use it your way</Badge>
        <h2 className="text-balance text-4xl font-semibold tracking-tight md:text-5xl">
          Three ways in. <span className="text-gradient-violet-cyan">One way out.</span>
        </h2>
        <p className="mx-auto mt-3 max-w-xl text-muted-foreground">
          Drop a file, paste a URL, or pipe live audio from anywhere on your
          system. All three flows hit the same model on the same GPU.
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        <ModeCard
          icon={<Upload className="h-5 w-5" />}
          title="File"
          tagline="Drag a song in."
          body="MP3, WAV, M4A, FLAC, OGG — or any video container (MP4, MOV, MKV, WebM). FFmpeg decodes, the model separates, you download the .wav."
        />
        <ModeCard
          icon={<Video className="h-5 w-5" />}
          title="YouTube"
          tagline="Paste a URL."
          body="YouTube, SoundCloud, Bandcamp, direct mp3s — anything yt-dlp understands. Preview the thumbnail before committing to the download."
        />
        <ModeCard
          icon={<Radio className="h-5 w-5" />}
          title="Live"
          tagline="Strip from any app."
          body="Route system audio through VB-Cable; the streamer runs as a subprocess and pipes vocals straight to your real speakers. Spotify, YouTube, anything that makes sound."
          highlight
        />
      </div>
    </section>
  );
}

function ModeCard({
  icon, title, tagline, body, highlight = false,
}: {
  icon: React.ReactNode; title: string; tagline: string; body: string; highlight?: boolean;
}) {
  return (
    <Card className={
      "group relative overflow-hidden transition-all hover:-translate-y-1 hover:shadow-lg hover:shadow-primary/10 " +
      (highlight ? "bg-gradient-to-br from-primary/[0.08] to-accent/[0.04] ring-1 ring-primary/40" : "")
    }>
      <CardContent className="space-y-3 pt-6">
        <div className="grid h-10 w-10 place-items-center rounded-lg bg-primary/15 text-primary ring-1 ring-primary/30 group-hover:bg-primary/25 transition-colors">
          {icon}
        </div>
        <div className="space-y-0.5">
          <h3 className="text-xl font-semibold">{title}</h3>
          <p className="text-sm text-primary">{tagline}</p>
        </div>
        <p className="text-sm leading-relaxed text-muted-foreground">{body}</p>
      </CardContent>
    </Card>
  );
}

/* ─────────────────────────────────────────────────────────────────────── */
/* Final CTA                                                               */
/* ─────────────────────────────────────────────────────────────────────── */

function FinalCTA() {
  return (
    <section className="relative overflow-hidden border-t border-border/60">
      <div className="bg-mesh-violet absolute inset-0 opacity-50" />
      <div className="relative mx-auto flex max-w-3xl flex-col items-center px-4 py-28 text-center">
        <Logo size="xl" href={null} showText={false} className="mb-6" />
        <h2 className="text-balance text-4xl font-semibold tracking-tight md:text-5xl">
          Stop hearing the music.<br />
          <span className="text-gradient-violet-cyan">Start hearing the voice.</span>
        </h2>
        <p className="mt-4 max-w-md text-muted-foreground">
          Everything runs on this machine. Nothing you upload leaves your laptop.
        </p>
        <Button render={<Link href="/process" />} size="lg" className="mt-10 text-base">
          Open Workspace
          <ArrowRight className="ml-1.5 h-4 w-4" />
        </Button>
      </div>
    </section>
  );
}

/* ─────────────────────────────────────────────────────────────────────── */
/* Footer                                                                  */
/* ─────────────────────────────────────────────────────────────────────── */

function Footer() {
  return (
    <footer className="border-t border-border/60">
      <div className="mx-auto flex max-w-6xl flex-col gap-3 px-4 py-8 text-xs text-muted-foreground md:flex-row md:items-center md:justify-between">
        <div className="flex items-center gap-3">
          <Logo size="sm" />
          <span className="hidden text-muted-foreground/60 sm:inline">·</span>
          <span className="hidden sm:inline">FYP demo · 2026</span>
        </div>
        <div className="flex items-center gap-4">
          <Link href="/process" className="hover:text-foreground transition-colors">Workspace</Link>
          <a
            href="https://github.com/Yukinee07/UnTuneApp"
            target="_blank"
            rel="noreferrer"
            className="flex items-center gap-1.5 hover:text-foreground transition-colors"
          >
            <Code2 className="h-3.5 w-3.5" />
            Source
          </a>
        </div>
      </div>
    </footer>
  );
}
