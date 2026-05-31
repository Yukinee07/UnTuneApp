"use client";

import { ThemeProvider as NextThemesProvider } from "next-themes";
import type { ThemeProviderProps } from "next-themes";

/**
 * Thin re-export of next-themes' provider with sensible defaults baked in.
 * Lives in client-component land because next-themes needs to read
 * localStorage + window.matchMedia, which the server can't do.
 *
 * `attribute="class"` flips a `.dark` class on <html> instead of using the
 * `data-theme` attribute — keeps it compatible with the Tailwind `dark:`
 * variant and the existing globals.css selectors.
 */
export function ThemeProvider({ children, ...props }: ThemeProviderProps) {
  return (
    <NextThemesProvider
      attribute="class"
      defaultTheme="dark"
      enableSystem
      disableTransitionOnChange
      {...props}
    >
      {children}
    </NextThemesProvider>
  );
}
