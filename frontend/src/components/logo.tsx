"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useTheme } from "next-themes";
import { cn } from "@/lib/utils";

/**
 * Logo — UnTuneApp brand mark, themed.
 *
 * Renders the prepared PNGs in /public/logo/.
 * Height-constrained; width follows the PNG's natural aspect ratio.
 * `mounted` guard prevents SSR/hydration mismatch.
 */

type Size = "sm" | "md" | "lg" | "xl";
const HEIGHT_PX: Record<Size, number> = { sm: 26, md: 34, lg: 52, xl: 88 };

export function Logo({
  size      = "md",
  href      = "/",
  className,
}: {
  size?:     Size;
  /** Pass `null` to render as a plain inline element instead of a link. */
  href?:     string | null;
  className?: string;
}) {
  const { resolvedTheme } = useTheme();
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  const isLight = mounted && resolvedTheme === "light";
  const src     = isLight ? "/logo/light.png" : "/logo/dark.png";
  const h       = HEIGHT_PX[size];

  const imgEl = (
    /* eslint-disable-next-line @next/next/no-img-element */
    <img
      src={src}
      alt="UnTuneApp"
      style={{ height: h, width: "auto" }}
      className={cn("select-none transition-opacity hover:opacity-90", className)}
      draggable={false}
    />
  );

  return href ? (
    <Link
      href={href}
      className="rounded outline-none focus-visible:ring-2 focus-visible:ring-ring"
    >
      {imgEl}
    </Link>
  ) : (
    imgEl
  );
}
