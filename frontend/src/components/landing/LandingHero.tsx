import React, { useState } from "react";
import { Mic, ArrowRight } from "lucide-react";
import { EmptyStateHorizon } from "../illustrations/EmptyStateHorizon";
import { LanguageCode, LiveConditionsSummary } from "@/lib/types";
import { translations } from "@/lib/i18n";

interface Props {
  language: LanguageCode;
  liveConditions: LiveConditionsSummary | null;
  onStartVoice: () => void;
  onSubmitText: (query: string) => void;
  onSelectPrompt: (prompt: string) => void;
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
  const [showInput, setShowInput] = useState(false);
  const [typedText, setTypedText] = useState("");
  const t = translations[language] || translations.en;

  const handleInputSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!typedText.trim()) return;
    onSubmitText(typedText.trim());
  };

  return (
    <div className={`relative min-h-[85vh] flex flex-col items-center justify-center text-center px-4 py-8 sm:py-14 max-w-4xl mx-auto w-full ${className}`}>
      {/* ── Soft atmospheric radial glow wash (per Sarvam accent-soft glow) ── */}
      <div
        className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[340px] sm:w-[600px] h-[340px] sm:h-[460px] bg-[var(--foam)] rounded-full blur-3xl opacity-50 pointer-events-none -z-10"
        aria-hidden="true"
      />

      {/* ── Small mono eyebrow, muted ── */}
      <div className="font-mono-data text-xs sm:text-sm text-[var(--ink-muted)] tracking-widest uppercase mb-3 sm:mb-5">
        {t.landingEyebrow}
      </div>

      {/* ── Headline: Instrument Serif / Fraunces italic, large, tight leading — NOT boxed, sits directly on the page background ── */}
      <h1 className="font-serif-display text-5xl sm:text-7xl md:text-8xl italic font-normal tracking-[-0.035em] text-[var(--ink)] leading-[0.94] max-w-2xl mx-auto">
        <span>{t.landingHeroLine1}</span>
        <br />
        <span>{t.landingHeroLine2}</span>
      </h1>

      {/* ── Horizon linework illustration:
          - NO container, NO border, NO drop shadow
          - Single 1.5px stroke weight throughout
          - Bleeds directly into the page background
      ── */}
      <div className="relative my-6 sm:my-8 w-full max-w-md mx-auto flex items-center justify-center">
        <div className="w-full max-w-sm transition-transform duration-700 hover:scale-[1.01]">
          <EmptyStateHorizon />
        </div>
      </div>

      {/* ── Subtitle in clean Noto Sans ── */}
      <p className="text-base sm:text-xl text-[var(--ink-muted)] max-w-lg mx-auto font-sans leading-relaxed font-normal mb-6 sm:mb-8">
        {t.landingHeadline}
      </p>

      {/* ── Primary CTA Area ── */}
      <div className="flex flex-col items-center gap-3 w-full max-w-md">
        {!showInput ? (
          <>
            {/* Pill Button: --current fill, min 56px height, rounded-full */}
            <button
              type="button"
              onClick={onStartVoice}
              className="w-full sm:w-auto min-w-[220px] min-h-[56px] px-8 py-3.5 rounded-full bg-[var(--current)] hover:bg-[var(--current-hover)] text-white font-medium text-base sm:text-lg flex items-center justify-center gap-3 shadow-xs hover:shadow-md active:scale-98 transition-all cursor-pointer"
              aria-label="Ask Tarang with voice"
            >
              <Mic className="w-5 h-5 text-white" />
              <span>{t.askTarangBtn}</span>
            </button>

            {/* Understated tertiary action */}
            <button
              type="button"
              onClick={() => setShowInput(true)}
              className="text-xs sm:text-sm font-medium text-[var(--ink-muted)] hover:text-[var(--current)] underline-offset-4 hover:underline py-1.5 transition-colors cursor-pointer"
            >
              {t.typeInstead}
            </button>
          </>
        ) : (
          <form onSubmit={handleInputSubmit} className="w-full flex items-center gap-2 animate-in fade-in duration-200">
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
              className="h-12 min-h-[48px] px-6 rounded-full bg-[var(--current)] hover:bg-[var(--current-hover)] text-white font-medium text-sm flex items-center gap-1.5 disabled:opacity-40 transition-all shadow-xs shrink-0 cursor-pointer"
            >
              <span>Ask</span>
              <ArrowRight className="w-4 h-4" />
            </button>
          </form>
        )}
      </div>

      {/* ── Suggested Starter Chips ── */}
      <div className="pt-5 flex flex-wrap justify-center gap-2 max-w-xl">
        {Object.values(t.prompts).slice(0, 3).map((prompt, idx) => (
          <button
            key={idx}
            type="button"
            onClick={() => onSelectPrompt(prompt)}
            className="px-3.5 py-1.5 min-h-[44px] rounded-full text-xs text-[var(--ink-muted)] bg-white hover:bg-[var(--foam)] border border-[var(--border)] hover:border-[var(--current)] transition-all shadow-2xs text-left flex items-center cursor-pointer"
          >
            "{prompt}"
          </button>
        ))}
      </div>

      {/* ── Monospace Data Strip (Part 0 PRD) ── */}
      {liveConditions && (
        <div className="mt-8 sm:mt-12 pt-6 border-t border-[var(--border)] max-w-lg w-full">
          <div className="grid grid-cols-3 gap-2 sm:gap-4 font-mono-data text-center">
            <div className="flex flex-col items-center">
              <span className="text-[10px] sm:text-[11px] text-[var(--ink-subtle)] uppercase tracking-wider">
                SURFACE TEMP
              </span>
              <span className="text-xs sm:text-sm font-semibold text-[var(--ink)] mt-0.5">
                {liveConditions.waveHeightM ? `${liveConditions.waveHeightM.toFixed(1)}m SWELL` : "24.2°C"}
              </span>
            </div>
            <div className="flex flex-col items-center border-x border-[var(--border)] px-2">
              <span className="text-[10px] sm:text-[11px] text-[var(--ink-subtle)] uppercase tracking-wider">
                SWELL VECTOR
              </span>
              <span className="text-xs sm:text-sm font-semibold text-[var(--ink)] mt-0.5">
                {liveConditions.windSpeedKmh
                  ? `${liveConditions.windSpeedKmh.toFixed(0)} km/h NW`
                  : "0.8m @ 12s"}
              </span>
            </div>
            <div className="flex flex-col items-center">
              <span className="text-[10px] sm:text-[11px] text-[var(--ink-subtle)] uppercase tracking-wider">
                RISK
              </span>
              <span
                className={`text-xs sm:text-sm font-semibold mt-0.5 flex items-center gap-1.5 ${
                  liveConditions.riskLabel === "LOW"
                    ? "text-[var(--risk-low)]"
                    : liveConditions.riskLabel === "HIGH"
                    ? "text-[var(--risk-high)]"
                    : "text-[var(--risk-moderate)]"
                }`}
              >
                <span className="w-1.5 h-1.5 rounded-full bg-current animate-pulse" />
                {liveConditions.riskLabel}
              </span>
            </div>
          </div>
          <div className="mt-2 text-center font-mono-data text-[10px] text-[var(--ink-subtle)]">
            {liveConditions.locationName.toUpperCase()} · {liveConditions.lat.toFixed(2)}°N {liveConditions.lon.toFixed(2)}°E · {liveConditions.source}
          </div>
        </div>
      )}
    </div>
  );
};
