"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Logo } from "@/components/logo";
import { ThemeToggle } from "@/components/theme-toggle";
import { cn } from "@/lib/utils";

export function SiteNav() {
  const pathname = usePathname();

  const nav = [
    { href: "/",        label: "Home"      },
    { href: "/process", label: "Workspace" },
  ];

  return (
    <header className="sticky top-0 z-40 w-full border-b border-border/60 bg-background/75 backdrop-blur supports-[backdrop-filter]:bg-background/55">
      <div className="mx-auto flex h-14 max-w-6xl items-center justify-between px-4">
        <Logo size="md" />

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
          <ThemeToggle />
          <Button render={<Link href="/process" />} size="sm" className="ml-1">
            Open Workspace
          </Button>
        </nav>
      </div>
    </header>
  );
}
