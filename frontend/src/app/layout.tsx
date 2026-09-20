import type { Metadata } from "next";
import { Fraunces, Noto_Sans, Noto_Sans_Devanagari, Noto_Sans_Tamil } from "next/font/google";
import "./globals.css";

const fraunces = Fraunces({
  variable: "--font-fraunces",
  subsets: ["latin"],
  display: "swap",
  weight: ["300", "400", "500", "600", "700"],
});

const notoSans = Noto_Sans({
  variable: "--font-noto-sans",
  subsets: ["latin"],
  display: "swap",
  weight: ["400", "500", "600", "700"],
});

const notoSansDevanagari = Noto_Sans_Devanagari({
  variable: "--font-noto-devanagari",
  subsets: ["devanagari"],
  display: "swap",
  weight: ["400", "500", "600", "700"],
});

const notoSansTamil = Noto_Sans_Tamil({
  variable: "--font-noto-tamil",
  subsets: ["tamil"],
  display: "swap",
  weight: ["400", "500", "600", "700"],
});

import { AppProviders } from "@/components/providers/AppProviders";

export const metadata: Metadata = {
  title: "Tarang — Marine Safety Intelligence",
  description: "Coastal decision support for Indian fishermen — real-time sea state, potential fishing zones, and safety advisories in your language.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      suppressHydrationWarning
      className={`${fraunces.variable} ${notoSans.variable} ${notoSansDevanagari.variable} ${notoSansTamil.variable} h-full antialiased`}
    >
      <body
        suppressHydrationWarning
        className="min-h-full flex flex-col bg-[var(--neutral)] text-[var(--ink)] font-sans selection:bg-[var(--foam)] selection:text-[var(--ink)]"
      >
        <AppProviders>{children}</AppProviders>
      </body>
    </html>
  );
}
