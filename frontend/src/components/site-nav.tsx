"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Logo } from "@/components/logo";
import { cn } from "@/lib/utils";

/**
 * Header — minimal: bigger logo on the left, two text links on the right.
 * Theme toggle has moved out of the header to a fixed bottom-right floater
 * (see layout.tsx <FloatingThemeToggle />).  The redundant "Open Workspace"
 * button is gone — Workspace is one of the two text links now.
 */

export function SiteNav() {
  const pathname = usePathname();

  const nav = [
    { href: "/",        label: "Home"      },
    { href: "/process", label: "Workspace" },
  ];

  return (
    <header className="sticky top-0 z-40 w-full border-b border-border/60 bg-background/75 backdrop-blur supports-[backdrop-filter]:bg-background/55">
      <div className="mx-auto flex h-20 max-w-6xl items-center justify-between px-6">
        <Logo size="lg" />

        <nav className="flex items-center gap-1">
          {nav.map((n) => {
            const active = pathname === n.href;
            return (
              <Link
                key={n.href}
                href={n.href}
                className={cn(
                  "rounded-md px-4 py-2 text-sm font-medium transition-colors",
                  active
                    ? "bg-secondary text-foreground"
                    : "text-muted-foreground hover:bg-secondary/60 hover:text-foreground"
                )}
              >
                {n.label}
              </Link>
            );
          })}
        </nav>
      </div>
    </header>
  );
}
