"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { ArrowRight, Home } from "lucide-react";
import { cn } from "@/lib/utils";

/**
 * FloatingNav — page-aware edge navigation.
 *
 *   Landing  (/)
 *     → "Go to Workspace" pill on the middle-right, but only AFTER the
 *       hero's primary CTA (#hero-cta) has scrolled out of view.  Fades
 *       in on appearance; fades out cleanly if the user scrolls back up.
 *
 *   Workspace (/process)
 *     → "Home" icon on the middle-left, always visible.
 */
export function FloatingNav() {
  const pathname = usePathname();
  const [heroCtaVisible, setHeroCtaVisible] = useState(true);

  // Watch the hero CTA so we can hide our floater while it's on screen.
  useEffect(() => {
    if (pathname !== "/") {
      setHeroCtaVisible(false);
      return;
    }
    const target = document.getElementById("hero-cta");
    if (!target) {
      // If the page hasn't fully mounted yet, assume visible.
      setHeroCtaVisible(true);
      return;
    }
    const io = new IntersectionObserver(
      ([entry]) => setHeroCtaVisible(entry.isIntersecting),
      { threshold: 0, rootMargin: "0px" }
    );
    io.observe(target);
    return () => io.disconnect();
  }, [pathname]);

  // ── Landing page → workspace pill on the right ──────────────────────
  if (pathname === "/") {
    const show = !heroCtaVisible;
    return (
      <Link
        href="/process"
        aria-label="Go to workspace"
        aria-hidden={!show}
        tabIndex={show ? 0 : -1}
        className={cn(
          "group fixed right-6 top-1/2 z-40 -translate-y-1/2",
          "inline-flex items-center gap-3 rounded-full",
          "bg-primary px-6 py-4 text-primary-foreground",
          "shadow-lg shadow-primary/40 ring-1 ring-primary/40",
          "backdrop-blur-md",
          "transition-all duration-500 ease-out",
          "hover:scale-105 hover:shadow-2xl hover:shadow-primary/60",
          // Visibility — fade + slight slide rather than appearing instantly
          show
            ? "opacity-100 translate-x-0 pointer-events-auto"
            : "opacity-0 translate-x-8 pointer-events-none"
        )}
        style={{
          // Compose with the -50% Y transform via CSS variables would be
          // cleaner, but Tailwind's `-translate-y-1/2` already wins thanks
          // to the cascade.  The X transform on the conditional class
          // combines fine with it because Tailwind emits the full matrix.
        }}
      >
        <span className="text-sm font-semibold tracking-wide">Go to Workspace</span>
        <ArrowRight className="h-5 w-5 transition-transform duration-300 group-hover:translate-x-1" />
      </Link>
    );
  }

  // ── Workspace page → home icon on the left ──────────────────────────
  if (pathname === "/process") {
    return (
      <Link
        href="/"
        aria-label="Back to home"
        className="
          group fixed left-6 top-1/2 z-40 -translate-y-1/2
          animate-slide-in-left
          grid h-14 w-14 place-items-center rounded-full
          bg-background/80 backdrop-blur-md
          shadow-lg ring-1 ring-border
          transition-all duration-300 ease-out
          hover:scale-110 hover:bg-primary/10 hover:ring-primary/40 hover:shadow-xl hover:shadow-primary/30
        "
      >
        <Home className="h-5 w-5 text-foreground transition-colors group-hover:text-primary" />
      </Link>
    );
  }

  return null;
}
