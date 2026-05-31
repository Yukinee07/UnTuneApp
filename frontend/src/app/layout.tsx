import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { SiteNav } from "@/components/site-nav";
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
  title: "VocalApp — Real-Time Vocal Isolation",
  description:
    "Strip the music. Keep the voice. Powered by HS-TasNet on your GPU.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    // The `dark` class is hard-pinned for v1 — the whole product is designed
    // for the dark theme.  Drop `next-themes` here later if you want a toggle.
    <html
      lang="en"
      className={`dark ${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col bg-background text-foreground">
        <SiteNav />
        <main className="flex-1 flex flex-col">{children}</main>
        <Toaster richColors closeButton position="bottom-right" />
      </body>
    </html>
  );
}
