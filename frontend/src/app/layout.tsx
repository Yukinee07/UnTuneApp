import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { ThemeProvider } from "@/components/theme-provider";
import { ThemeToggle } from "@/components/theme-toggle";
import { FloatingNav } from "@/components/floating-nav";
import { Toaster } from "@/components/ui/sonner";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "UnTuneApp — Real-Time Vocal Isolation",
  description:
    "Mute the music. Keep the voice. Powered by HS-TasNet on your GPU.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    // `suppressHydrationWarning` is required because next-themes adds the
    // class on first client paint — without this React would warn about
    // a server/client mismatch.
    <html
      lang="en"
      suppressHydrationWarning
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col bg-background text-foreground">
        <ThemeProvider>
          {/* No header — navigation lives in <FloatingNav /> on the edges. */}
          <main className="flex-1 flex flex-col">{children}</main>

          {/* Edge-glued nav (different per page) */}
          <FloatingNav />

          {/* Bottom-right theme toggle, glass pill, present on every page. */}
          <div className="fixed bottom-6 right-6 z-50">
            <div className="rounded-full bg-background/80 p-1 shadow-lg ring-1 ring-border backdrop-blur-md transition-shadow hover:shadow-xl">
              <ThemeToggle />
            </div>
          </div>

          {/* Toaster at bottom-LEFT so it doesn't collide with the
              floating theme toggle at bottom-right. */}
          <Toaster richColors closeButton position="bottom-left" />
        </ThemeProvider>
      </body>
    </html>
  );
}
