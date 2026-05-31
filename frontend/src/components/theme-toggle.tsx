"use client";

import { useEffect, useState } from "react";
import { useTheme } from "next-themes";
import { Moon, Sun } from "lucide-react";
import { Button } from "@/components/ui/button";

/**
 * Compact icon button that toggles between dark and light themes.
 *
 * Mounts as a skeleton on first paint to avoid the classic hydration
 * mismatch where the server-rendered icon (theme unknown) differs from
 * the client-rendered icon (theme resolved from localStorage).
 */
export function ThemeToggle() {
  const { resolvedTheme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);

  useEffect(() => setMounted(true), []);

  const isDark = resolvedTheme === "dark";
  const toggle = () => setTheme(isDark ? "light" : "dark");

  return (
    <Button
      variant="ghost"
      size="icon-sm"
      onClick={toggle}
      aria-label={isDark ? "Switch to light theme" : "Switch to dark theme"}
      title={isDark ? "Switch to light" : "Switch to dark"}
    >
      {mounted ? (
        isDark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />
      ) : (
        // Placeholder dot keeps button geometry stable pre-hydration.
        <span className="block h-4 w-4 rounded-full bg-muted" />
      )}
    </Button>
  );
}
