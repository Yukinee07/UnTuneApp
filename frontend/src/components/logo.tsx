import Image from "next/image";
import Link from "next/link";
import { cn } from "@/lib/utils";

/**
 * Logo — pairs a chosen SVG mark with the UnTuneApp wordmark.
 *
 * To switch the entire app's logo, change the default `mark` here.
 * Available marks (all in /public/logos/):
 *   - "strike"    forbidden music-note inside a gradient ring   (default)
 *   - "subtract"  mixture-bars minus music-bars = vocal-bars
 *   - "isolate"   central mic with faded notes drifting away
 *   - "untune"    tuning fork with one broken / silenced prong
 */

type MarkName = "strike" | "subtract" | "isolate" | "untune";

type Size = "sm" | "md" | "lg" | "xl";
const MARK_PX: Record<Size, number> = { sm: 20, md: 26, lg: 36, xl: 56 };
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
      <Image
        src={`/logos/mark-${mark}.svg`}
        alt=""
        width={dim}
        height={dim}
        priority
        className="select-none"
      />
      {showText && (
        <span className={cn(TEXT_CLS[size], "font-semibold tracking-tight")}>
          UnTune<span className="text-primary">App</span>
        </span>
      )}
    </span>
  );

  return href ? (
    <Link href={href} className="outline-none focus-visible:ring-2 focus-visible:ring-ring rounded">
      {inner}
    </Link>
  ) : (
    inner
  );
}
