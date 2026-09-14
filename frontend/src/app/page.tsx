"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { LandingHero } from "@/components/landing/LandingHero";
import { HowItWorksSection } from "@/components/landing/HowItWorksSection";
import { WhyThisMattersSection } from "@/components/landing/WhyThisMattersSection";
import { FeaturesSection } from "@/components/landing/FeaturesSection";
import { LandingFooter } from "@/components/landing/LandingFooter";
import { LanguageToggle } from "@/components/common/LanguageToggle";
import { LanguageCode, LiveConditionsSummary } from "@/lib/types";
import { ArrowRight } from "lucide-react";

export default function Home() {
  const router = useRouter();
  const [currentLanguage, setCurrentLanguage] = useState<LanguageCode>("en");
  const [userCoords, setUserCoords] = useState<{ lat: number; lon: number } | null>(null);

  const [liveConditions, setLiveConditions] = useState<LiveConditionsSummary>({
    locationName: "Thoothukudi Harbour",
    lat: 8.7642,
    lon: 78.1348,
    waveHeightM: 0.85,
    windSpeedKmh: 11.8,
    seaState: "slight",
    riskLabel: "LOW",
    source: "Open-Meteo ERA5 / Live Marine",
    isFallback: false,
  });

  // Request browser location for real-time instrument readout
  const requestBrowserLocation = () => {
    if (typeof navigator === "undefined" || !navigator.geolocation) return;

    navigator.geolocation.getCurrentPosition(
      (position) => {
        const lat = position.coords.latitude;
        const lon = position.coords.longitude;
        setUserCoords({ lat, lon });
        setLiveConditions((prev) => ({
          ...prev,
          lat,
          lon,
          locationName: `${lat.toFixed(2)}°N, ${lon.toFixed(2)}°E`,
        }));
      },
      (err) => {
        console.warn("[LANDING] Geolocation request error:", err.message);
      },
      { timeout: 10000, maximumAge: 60000 }
    );
  };

  useEffect(() => {
    requestBrowserLocation();
  }, []);

  const handleLaunchAppWithQuery = (query: string) => {
    router.push(`/app?q=${encodeURIComponent(query)}`);
  };

  return (
    <div className="min-h-screen flex flex-col bg-[var(--neutral)] text-[var(--ink)] antialiased">
      {/* ── Top Navigation Bar: Hairline-thin Nav (Part 0 PRD) ── */}
      <header className="h-14 px-4 sm:px-8 bg-[var(--surface)] border-b border-[var(--border)] flex items-center justify-between shrink-0 sticky top-0 z-30 shadow-2xs">
        <div className="flex items-center gap-6 sm:gap-8">
          {/* Wordmark: tarang. in Instrument Serif with trailing period */}
          <Link
            href="/"
            className="flex items-center gap-3 text-left group cursor-pointer"
            aria-label="Tarang Coastal Intelligence Home"
          >
            <span className="font-serif-display text-xl sm:text-2xl font-normal text-[var(--ink)] tracking-tight">
              tarang.
            </span>
          </Link>

          {/* Editorial Nav Links */}
          <nav className="hidden sm:flex items-center gap-6 font-mono-data text-[11px] text-[var(--ink-muted)]">
            <a
              href="#how-it-works"
              className="hover:text-[var(--current)] transition-colors tracking-editorial uppercase"
            >
              PIPELINE
            </a>
            <a
              href="#why-this-matters"
              className="hover:text-[var(--current)] transition-colors tracking-editorial uppercase"
            >
              WHY THIS MATTERS
            </a>
            <a
              href="#features"
              className="hover:text-[var(--current)] transition-colors tracking-editorial uppercase"
            >
              WHAT TARANG DOES
            </a>
          </nav>
        </div>

        {/* Right Nav Actions: Instrument Readout & App Launcher */}
        <div className="flex items-center gap-3 sm:gap-4 font-mono-data text-[11px]">
          <span className="hidden lg:inline text-[var(--ink-subtle)]">EST. 2024 / COASTAL SYSTEMS</span>
          <span className="hidden lg:inline text-[var(--border)]">|</span>

          {/* GPS instrument tag */}
          <button
            type="button"
            onClick={requestBrowserLocation}
            className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-[var(--foam)] text-[var(--current)] font-medium hover:bg-[var(--foam)]/80 transition-colors border border-[var(--current)]/20 cursor-pointer"
            title={userCoords ? "GPS active. Tap to refresh." : "Tap to detect device location"}
          >
            <span className="w-2 h-2 rounded-full bg-[var(--current)] animate-pulse" />
            <span className="truncate max-w-[150px]">
              📍 {userCoords ? `${userCoords.lat.toFixed(2)}°N, ${userCoords.lon.toFixed(2)}°E` : "Thoothukudi Harbour"}
            </span>
          </button>

          {/* Language Toggle (EN / हिं / த) */}
          <LanguageToggle
            currentLanguage={currentLanguage}
            onSelectLanguage={(lang) => setCurrentLanguage(lang)}
          />

          {/* Open App CTA button */}
          <Link
            href="/app"
            className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-full bg-[var(--ink)] text-white text-xs font-sans font-medium hover:bg-[var(--current)] transition-all shadow-xs cursor-pointer"
          >
            <span>Launch App</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </Link>
        </div>
      </header>

      {/* ── Main Landing Narrative Page Structure (PRD §2) ── */}
      <main className="flex-1 flex flex-col">
        {/* Hero Section (PRD Part 0 with §0.1 fix and §1.4 subtle boat bob) */}
        <LandingHero
          language={currentLanguage}
          liveConditions={liveConditions}
          onSubmitText={handleLaunchAppWithQuery}
        />

        {/* [NEW] How It Works Section (PRD §1.3: 3 numbered steps, sequential reveal) */}
        <HowItWorksSection language={currentLanguage} />

        {/* [NEW] Why This Matters Section (PRD §1.2: real stat counters, sourced) */}
        <WhyThisMattersSection language={currentLanguage} />

        {/* Features Section (PRD Part 0.1 & §1.1: six numbered columns with staggered scroll reveal) */}
        <div id="features">
          <FeaturesSection language={currentLanguage} />
        </div>

        {/* Quiet Hairline Footer (PRD Part 0) */}
        <LandingFooter />
      </main>
    </div>
  );
}
