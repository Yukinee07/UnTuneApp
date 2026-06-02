"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useTheme } from "next-themes";
import { cn } from "@/lib/utils";

/**
 * Logo — UnTuneApp brand mark + wordmark, themed.
 *
 * Uses the two prepared PNGs:
 *   /logo/dark.png   (light artwork on dark backgrounds)
 *   /logo/light.png  (dark artwork on light backgrounds)
 *
 * We swap the source based on the active theme via next-themes.  To avoid
 * the classic SSR/hydration mismatch (server doesn't know the user's theme
 * until JS mounts), we render the dark variant first and `<img>` is updated
 * the moment `mounted` flips true.
 *
 * Sizing is height-based; the width follows the PNG's natural aspect ratio
 * so the wordmark never gets squashed.
 */

type Size = "sm" | "md" | "lg" | "xl";
const HEIGHT_PX: Record<Size, number> = { sm: 28, md: 36, lg: 56, xl: 96 };

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

  // Pre-mount, render the dark variant unconditionally so SSR markup
  // matches the most common case (we ship with defaultTheme="dark").
  const isLight = mounted && resolvedTheme === "light";
  const src     = isLight ? "/logo/light.png" : "/logo/dark.png";

  const h = HEIGHT_PX[size];

  // We render via plain <img> rather than next/image: the asset is small
  // (~70 KB), height-constrained, and we want auto-width without having to
  // hardcode the PNG's pixel dimensions.
  const imgEl = (
    /* eslint-disable-next-line @next/next/no-img-element */
    <img
      src={src}
      alt="UnTuneApp"
      style={{ height: h, width: "auto" }}
      className={cn("select-none", className)}
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
