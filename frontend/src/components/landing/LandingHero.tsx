import React, { useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowRight } from "lucide-react";
import { EmptyStateHorizon } from "../illustrations/EmptyStateHorizon";
import { LanguageCode, LiveConditionsSummary } from "@/lib/types";
import { translations } from "@/lib/i18n";

interface Props {
  language: LanguageCode;
  liveConditions: LiveConditionsSummary | null;
  onStartVoice?: () => void;
  onSubmitText?: (query: string) => void;
  onSelectPrompt?: (prompt: string) => void;
  className?: string;
}

export const LandingHero: React.FC<Props> = ({
  language,
  liveConditions,
  onStartVoice,
  onSubmitText,
  onSelectPrompt,
  className = "",
}) => {
  const router = useRouter();
  const [showInput, setShowInput] = useState(false);
  const [typedText, setTypedText] = useState("");
  const t = translations[language] || translations.en;

  const handleInputSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const query = typedText.trim();
    if (!query) return;

    if (onSubmitText) {
      onSubmitText(query);
    }
    // Route to /app carrying query in search param per PRD §0
    router.push(`/app?q=${encodeURIComponent(query)}`);
  };

  const handleCTAClick = () => {
    // If text was already typed, carry it over; otherwise navigate directly to /app
    const query = typedText.trim();
    if (query) {
      if (onSubmitText) onSubmitText(query);
      router.push(`/app?q=${encodeURIComponent(query)}`);
    } else {
      router.push("/app");
    }
  };

  // Current time in IST
  const now = new Date();
  const istTime = now.toLocaleTimeString("en-IN", {
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "Asia/Kolkata",
  });

  const lat = liveConditions?.lat ?? 8.7642;
  const lon = liveConditions?.lon ?? 78.1348;

  return (
    <section className={`relative min-h-[82vh] flex flex-col justify-center ${className}`}>
      {/* ── Soft atmospheric radial glow wash — positioned behind the illustration area ── */}
      <div
        className="absolute top-1/3 right-[15%] w-[280px] sm:w-[380px] h-[280px] sm:h-[380px] bg-[var(--foam)] rounded-full blur-3xl opacity-40 pointer-events-none -z-10"
        aria-hidden="true"
      />

      {/* ── Main asymmetric grid: left text (~50%) + right empty space with illustration ── */}
      <div className="max-w-[1200px] mx-auto w-full px-6 sm:px-10 lg:px-16">
        <div className="grid grid-cols-1 lg:grid-cols-[1fr_1fr] gap-8 lg:gap-4 items-center relative">

          {/* ─── LEFT COLUMN: Text content ─── */}
          <div className="max-w-[520px]">
            {/* Small mono eyebrow label */}
            <div className="font-mono-data text-[11px] text-[var(--ink-muted)] tracking-widest uppercase mb-5 sm:mb-6">
              {t.heroEyebrow}
            </div>

            {/* Hero headline — Instrument Serif italic, large, tight leading */}
            <h1 className="font-serif-display text-[2.8rem] sm:text-[3.8rem] lg:text-[4.5rem] italic font-normal tracking-[-0.03em] text-[var(--ink)] leading-[0.92] mb-5 sm:mb-6">
              <span className="block">{t.landingHeroLine1}</span>
              <span className="block">{t.landingHeroLine2}</span>
            </h1>

            {/* Subtitle copy */}
            <p className="text-sm sm:text-base text-[var(--ink-muted)] leading-relaxed font-sans max-w-[440px] mb-6 sm:mb-8">
              {t.landingHeadline}
            </p>

            {/* ── Primary CTA: quiet text link navigating to /app ── */}
            <div className="flex flex-col gap-3">
              {!showInput ? (
                <>
                  {/* Ask Tarang → text link: --ink color, underline on hover only */}
                  <button
                    type="button"
                    onClick={handleCTAClick}
                    className="group inline-flex items-center gap-2 text-base sm:text-lg text-[var(--ink)] font-normal hover:underline underline-offset-4 decoration-[var(--ink-subtle)] transition-all cursor-pointer w-fit"
                    aria-label="Ask Tarang"
                  >
                    <span>{t.askTarangBtn}</span>
                    <ArrowRight className="w-4 h-4 text-[var(--ink-muted)] group-hover:translate-x-1 transition-transform" />
                  </button>

                  {/* Secondary: type instead */}
                  <button
                    type="button"
                    onClick={() => setShowInput(true)}
                    className="text-xs text-[var(--ink-subtle)] hover:text-[var(--ink-muted)] underline-offset-4 hover:underline transition-colors cursor-pointer w-fit"
                  >
                    {t.typeInstead}
                  </button>
                </>
              ) : (
                <form onSubmit={handleInputSubmit} className="flex items-center gap-2 max-w-[440px]">
                  <input
                    type="text"
                    value={typedText}
                    onChange={(e) => setTypedText(e.target.value)}
                    placeholder={t.inputPlaceholder}
                    autoFocus
                    className="flex-1 h-12 min-h-[48px] px-5 bg-white text-[var(--ink)] placeholder-[var(--ink-subtle)] rounded-full border border-[var(--border)] focus:border-[var(--current)] focus:ring-2 focus:ring-[var(--current)]/20 shadow-xs text-sm"
                  />
                  <button
                    type="submit"
                    disabled={!typedText.trim()}
                    className="h-12 min-h-[48px] min-w-[48px] px-5 rounded-full bg-[var(--current)] hover:bg-[var(--current-hover)] text-white font-medium text-sm flex items-center gap-1.5 disabled:opacity-40 transition-all shadow-xs shrink-0 cursor-pointer"
                  >
                    <ArrowRight className="w-4 h-4" />
                  </button>
                </form>
              )}
            </div>
          </div>

          {/* ─── RIGHT COLUMN: Intentional empty space with small illustration and scattered floating data tags ─── */}
          <div className="relative flex items-center justify-center lg:justify-start lg:pl-16 min-h-[300px] lg:min-h-[380px] w-full">
            {/* Small illustration — roughly 140px, off-center, surrounded by generous empty space */}
            <div className="w-[120px] sm:w-[140px] lg:w-[160px] lg:mt-6 lg:ml-12 transition-transform duration-700 hover:scale-[1.02] relative z-10">
              <EmptyStateHorizon
                className="w-full h-auto"
                width={160}
                height={75}
              />
            </div>

            {/* ─── SCATTERED FLOATING DATA TAGS (PRD Part 0 rule 4) ─── */}
            {liveConditions && (
              <>
                {/* Tag 1: · WIND_VECT (Top-left of illustration field) */}
                {liveConditions.windSpeedKmh != null && (
                  <div
                    className="absolute top-2 sm:top-6 left-2 sm:left-6 lg:left-8 flex flex-col pointer-events-none select-none transition-all duration-500"
                    aria-label={`Wind vector: ${liveConditions.windSpeedKmh.toFixed(0)} knots`}
                  >
                    <div className="flex items-center gap-1.5 mb-0.5">
                      <span className="w-1.5 h-1.5 rounded-full bg-[var(--current)]" />
                      <span className="font-mono-data text-[10px] text-[var(--ink-subtle)] uppercase tracking-widest">
                        WIND_VECT
                      </span>
                    </div>
                    <span className="font-mono-data text-xs text-[var(--ink)] font-medium pl-3">
                      {liveConditions.windSpeedKmh.toFixed(0)}KTS / {liveConditions.seaState ? liveConditions.seaState.toUpperCase() : "SW"}
                    </span>
                  </div>
                )}

                {/* Tag 2: · PFZ_ALPHA (Top-right of field) */}
                {lat != null && lon != null && (
                  <div
                    className="absolute top-4 sm:top-8 right-6 sm:right-12 lg:right-20 flex flex-col pointer-events-none select-none transition-all duration-500"
                    aria-label={`Potential fishing zone: ${liveConditions.locationName}`}
                  >
                    <div className="flex items-center gap-1.5 mb-0.5">
                      <span className="w-1.5 h-1.5 rounded-full bg-[var(--current)] opacity-80" />
                      <span className="font-mono-data text-[10px] text-[var(--ink-subtle)] uppercase tracking-widest">
                        PFZ_ALPHA
                      </span>
                    </div>
                    <span className="font-mono-data text-xs text-[var(--ink)] font-medium pl-3">
                      42NM RADIAL
                    </span>
                  </div>
                )}

                {/* Tag 3: · RISK_LVL (Mid-right of field) */}
                {liveConditions.riskLabel && (
                  <div
                    className="absolute top-1/2 -translate-y-4 right-4 sm:right-10 lg:right-16 flex flex-col pointer-events-none select-none transition-all duration-500"
                    aria-label={`Risk level: ${liveConditions.riskLabel}`}
                  >
                    <div className="flex items-center gap-1.5 mb-0.5">
                      <span
                        className={`w-1.5 h-1.5 rounded-full ${
                          liveConditions.riskLabel === "LOW"
                            ? "bg-[var(--risk-low)]"
                            : liveConditions.riskLabel === "HIGH" || liveConditions.riskLabel === "EXTREME"
                            ? "bg-[var(--risk-high)]"
                            : "bg-[var(--risk-moderate)]"
                        } animate-pulse`}
                      />
                      <span className="font-mono-data text-[10px] text-[var(--ink-subtle)] uppercase tracking-widest">
                        RISK_LVL
                      </span>
                    </div>
                    <span
                      className={`font-mono-data text-xs font-semibold pl-3 ${
                        liveConditions.riskLabel === "LOW"
                          ? "text-[var(--risk-low)]"
                          : liveConditions.riskLabel === "HIGH" || liveConditions.riskLabel === "EXTREME"
                          ? "text-[var(--risk-high)]"
                          : "text-[var(--risk-moderate)]"
                      }`}
                    >
                      {liveConditions.riskLabel === "LOW" ? "NOMINAL" : liveConditions.riskLabel}
                    </span>
                  </div>
                )}

                {/* Tag 4: · WAVE_HGT (Bottom-left/below illustration) */}
                {liveConditions.waveHeightM != null && (
                  <div
                    className="absolute bottom-2 sm:bottom-6 left-6 sm:left-14 lg:left-20 flex flex-col pointer-events-none select-none transition-all duration-500"
                    aria-label={`Wave height: ${liveConditions.waveHeightM.toFixed(1)} meters at 9s period`}
                  >
                    <div className="flex items-center gap-1.5 mb-0.5">
                      <span className="w-1.5 h-1.5 rounded-full bg-[var(--current)]" />
                      <span className="font-mono-data text-[10px] text-[var(--ink-subtle)] uppercase tracking-widest">
                        WAVE_HGT
                      </span>
                    </div>
                    <span className="font-mono-data text-xs text-[var(--ink)] font-medium pl-3">
                      {liveConditions.waveHeightM.toFixed(1)}M @ 9S
                    </span>
                  </div>
                )}
              </>
            )}
          </div>

          {/* ─── ROTATED 90° INSTRUMENT READOUT — right edge (PRD §0.1) ─── */}
          <div
            className="hidden lg:block absolute right-0 top-1/2 -translate-y-1/2 writing-vertical font-mono-data text-[10px] text-[var(--ink-subtle)] tracking-widest opacity-60 select-none"
            aria-hidden="true"
          >
            {lat.toFixed(4)}°N, {lon.toFixed(4)}°E · {istTime} IST
          </div>

        </div>
      </div>
    </section>
  );
};
