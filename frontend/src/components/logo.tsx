import Link from "next/link";
import { cn } from "@/lib/utils";

/**
 * Logo — UnTuneApp mark + wordmark.
 *
 * The SVG mark is INLINED (not loaded from /public) so it can inherit
 * `currentColor` from the surrounding text colour.  That's what makes
 * the music-note glyph flip between dark-mode-light and light-mode-dark
 * automatically without us shipping two different files.  The gradient
 * ring and red slash stay fixed across themes for brand consistency.
 *
 * The four standalone SVG files in /public/logos/ are kept around for
 * preview / reference; they're not used by the React app.
 */

type MarkName = "strike" | "subtract" | "isolate" | "untune";

type Size = "sm" | "md" | "lg" | "xl";
const MARK_PX: Record<Size, number> = { sm: 22, md: 28, lg: 36, xl: 60 };
const TEXT_CLS: Record<Size, string> = {
  sm: "text-sm",
  md: "text-base",
  lg: "text-xl",
  xl: "text-3xl",
};

export function Logo({
  mark      = "strike",
  showText  = true,
  size      = "md",
  href      = "/",
  className,
}: {
  mark?:     MarkName;
  showText?: boolean;
  size?:     Size;
  /** Pass `null` to render as a plain inline element instead of a link. */
  href?:     string | null;
  className?: string;
}) {
  const dim = MARK_PX[size];

  const inner = (
    <span className={cn("inline-flex items-center gap-2", className)}>
      <MarkSvg name={mark} size={dim} />
      {showText && (
        <span className={cn(TEXT_CLS[size], "font-semibold tracking-tight")}>
          UnTune<span className="text-primary">App</span>
        </span>
      )}
    </span>
  );

  return href ? (
    <Link
      href={href}
      className="rounded outline-none focus-visible:ring-2 focus-visible:ring-ring"
    >
      {inner}
    </Link>
  ) : (
    inner
  );
}

/* ─── Inline SVG marks ──────────────────────────────────────────────── */

function MarkSvg({ name, size }: { name: MarkName; size: number }) {
  switch (name) {
    case "strike":   return <Strike   size={size} />;
    case "subtract": return <Subtract size={size} />;
    case "isolate":  return <Isolate  size={size} />;
    case "untune":   return <Untune   size={size} />;
  }
}

/** Each mark renders into a 64×64 viewBox and uses currentColor for the
 *  parts that should track the theme's foreground. */

function Strike({ size }: { size: number }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 64 64"
      width={size}
      height={size}
      fill="none"
      className="text-foreground"
    >
      <defs>
        <linearGradient id="ut-strike-ring" x1="0" y1="0" x2="64" y2="64">
          <stop offset="0%"   stopColor="oklch(0.68 0.21 295)" />
          <stop offset="100%" stopColor="oklch(0.78 0.16 200)" />
        </linearGradient>
      </defs>
      <circle cx="32" cy="32" r="29" stroke="url(#ut-strike-ring)" strokeWidth="3" opacity="0.9" />
      <g
        fill="currentColor"
        stroke="currentColor"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <ellipse cx="22" cy="42" rx="6" ry="4.5" transform="rotate(-18 22 42)" />
        <path d="M27 41 L27 16" strokeWidth="3" fill="none" />
        <path d="M27 16 C 36 19, 39 27, 33.5 33" strokeWidth="3" fill="none" />
      </g>
      <line
        x1="14" y1="50" x2="50" y2="14"
        stroke="oklch(0.68 0.24 25)"
        strokeWidth="5"
        strokeLinecap="round"
      />
    </svg>
  );
}

function Subtract({ size }: { size: number }) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" width={size} height={size} fill="none" strokeLinecap="round">
      <g strokeWidth="3">
        <line x1="8"  y1="14" x2="8"  y2="20" stroke="oklch(0.68 0.21 295)" />
        <line x1="16" y1="10" x2="16" y2="24" stroke="oklch(0.68 0.21 295)" />
        <line x1="24" y1="13" x2="24" y2="21" stroke="oklch(0.78 0.16 200)" />
        <line x1="32" y1="8"  x2="32" y2="26" stroke="oklch(0.68 0.21 295)" />
        <line x1="40" y1="11" x2="40" y2="23" stroke="oklch(0.78 0.16 200)" />
        <line x1="48" y1="14" x2="48" y2="20" stroke="oklch(0.68 0.21 295)" />
        <line x1="56" y1="12" x2="56" y2="22" stroke="oklch(0.78 0.16 200)" />
      </g>
      <line x1="22" y1="32" x2="42" y2="32" stroke="oklch(0.68 0.24 25)" strokeWidth="4" />
      <g strokeWidth="3" stroke="oklch(0.78 0.16 200)">
        <line x1="12" y1="44" x2="12" y2="50" />
        <line x1="20" y1="42" x2="20" y2="52" />
        <line x1="28" y1="40" x2="28" y2="54" />
        <line x1="36" y1="42" x2="36" y2="52" />
        <line x1="44" y1="44" x2="44" y2="50" />
        <line x1="52" y1="43" x2="52" y2="51" />
      </g>
    </svg>
  );
}

function Isolate({ size }: { size: number }) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" width={size} height={size} fill="none" strokeLinecap="round" strokeLinejoin="round" className="text-foreground">
      <g opacity="0.45" stroke="oklch(0.68 0.21 295)" strokeWidth="2.5" fill="oklch(0.68 0.21 295)">
        <ellipse cx="9"  cy="22" rx="3" ry="2.4" transform="rotate(-18 9 22)" />
        <path d="M12 21 L12 9" fill="none" />
        <ellipse cx="55" cy="42" rx="3" ry="2.4" transform="rotate(-18 55 42)" opacity="0.7" />
        <path d="M58 41 L58 29" fill="none" opacity="0.7" />
      </g>
      <g stroke="currentColor" strokeWidth="3" fill="oklch(0.68 0.21 295)">
        <rect x="26" y="14" width="12" height="22" rx="6" />
      </g>
      <g stroke="currentColor" strokeWidth="3" fill="none">
        <path d="M20 30 C 20 38, 26 44, 32 44 C 38 44, 44 38, 44 30" />
        <line x1="32" y1="44" x2="32" y2="54" />
        <line x1="24" y1="54" x2="40" y2="54" />
      </g>
      <circle cx="32" cy="22" r="1.5" fill="oklch(0.78 0.16 200)" />
    </svg>
  );
}

function Untune({ size }: { size: number }) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" width={size} height={size} fill="none" strokeLinecap="round">
      <rect x="29" y="38" width="6" height="18" rx="2" fill="oklch(0.68 0.21 295)" />
      <path d="M21 38 L21 14" stroke="oklch(0.78 0.16 200)" strokeWidth="5" />
      <circle cx="21" cy="10" r="3" fill="oklch(0.78 0.16 200)" />
      <path d="M43 38 L43 26" stroke="oklch(0.68 0.24 25)" strokeWidth="5" opacity="0.85" />
      <line x1="38" y1="20" x2="48" y2="14" stroke="oklch(0.68 0.24 25)" strokeWidth="3" opacity="0.85" />
      <path d="M19 38 L45 38" stroke="oklch(0.68 0.21 295)" strokeWidth="5" />
    </svg>
  );
}
