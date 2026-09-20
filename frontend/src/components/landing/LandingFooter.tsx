import React from "react";
import { LanguageCode } from "@/lib/types";
import { translations } from "@/lib/i18n";

interface Props {
  language?: LanguageCode;
  className?: string;
}

/**
 * LandingFooter — Quiet hairline footer per PRD Part 0.1.
 * "One hairline rule, wordmark, one line of context. Small and quiet,
 * not a heavy multi-column SaaS footer with a dozen links."
 */
export const LandingFooter: React.FC<Props> = ({ language = "en", className = "" }) => {
  const t = translations[language] || translations.en;

  return (
    <footer className={`border-t border-[var(--border)] py-8 sm:py-10 ${className}`}>
      <div className="max-w-[1200px] mx-auto w-full px-6 sm:px-10 lg:px-16 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div className="flex items-center gap-4">
          <span className="font-serif-display text-base font-normal tracking-tight text-[var(--ink)]">
            tarang.
          </span>
          <span className="hidden sm:inline text-[var(--border)]" aria-hidden="true">
            /
          </span>
          <span className="font-mono-data text-[11px] text-[var(--ink-subtle)]">
            {t.footerTagline}
          </span>
        </div>

        <div className="font-mono-data text-[10px] text-[var(--ink-subtle)] tracking-wider">
          INCOIS · GDACS · OPEN-METEO · SARVAM AI
        </div>
      </div>
    </footer>
  );
};
