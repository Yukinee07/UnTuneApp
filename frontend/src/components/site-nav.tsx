"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { AudioLines } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export function SiteNav() {
  const pathname = usePathname();

  const nav = [
    { href: "/",        label: "Home"      },
    { href: "/process", label: "Workspace" },
  ];

  return (
    <header className="sticky top-0 z-40 w-full border-b border-border/60 bg-background/80 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <div className="mx-auto flex h-14 max-w-6xl items-center justify-between px-4">
        <Link href="/" className="flex items-center gap-2 font-semibold tracking-tight">
          <span className="grid h-7 w-7 place-items-center rounded-md bg-primary/15 text-primary ring-1 ring-primary/30">
            <AudioLines className="h-4 w-4" />
          </span>
          <span>VocalApp</span>
          <span className="hidden text-xs font-normal text-muted-foreground sm:inline">
            · Real-Time Vocal Isolation
          </span>
        </Link>

        <nav className="flex items-center gap-1">
          {nav.map((n) => {
            const active = pathname === n.href;
            return (
              <Link
                key={n.href}
                href={n.href}
                className={cn(
                  "rounded-md px-3 py-1.5 text-sm transition-colors",
                  active
                    ? "bg-secondary text-foreground"
                    : "text-muted-foreground hover:bg-secondary/60 hover:text-foreground"
                )}
              >
                {n.label}
              </Link>
            );
          })}
          <Button render={<Link href="/process" />} size="sm" className="ml-2">
            Open Workspace
          </Button>
        </nav>
      </div>
    </header>
  );
}
