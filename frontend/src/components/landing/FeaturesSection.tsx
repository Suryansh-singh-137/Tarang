"use client";

import React, { useEffect, useRef, useState } from "react";
import { LanguageCode } from "@/lib/types";
import { translations } from "@/lib/i18n";

interface Props {
  language: LanguageCode;
  className?: string;
}

/**
 * FeaturesSection — below-the-fold "What Tarang Does" section.
 *
 * PRD Part 0.1 & M10 rules:
 * - Numbered columns (01-06), NOT icon-topped cards
 * - No card borders, no shadows, no background fills per item
 * - Unequal row structure (4 columns, then 2 wider columns)
 * - Copy is specific to actual backend capabilities
 * - Staggered scroll reveals 01 -> 06 with 75ms stagger
 */

const FEATURES_ROW_1 = [
  {
    num: "01",
    index: 0,
    title: "Marine Weather",
    body: "Live wave height, wind speed, and visibility from Open-Meteo ERA5 reanalysis and ICON NWP forecasts. Sea state classification per WMO Douglas scale.",
  },
  {
    num: "02",
    index: 1,
    title: "Fishing Potential",
    body: "Chlorophyll-a based proxy zones from INCOIS Oceansat-2 satellite grid. Disclosed as historical scientific indicator, not a live official PFZ advisory.",
  },
  {
    num: "03",
    index: 2,
    title: "Hazard & Cyclone",
    body: "GDACS live tropical cyclone tracking alongside weather-code hazards. Real-time distance, wind speed, and alert level from UN disaster monitoring.",
  },
  {
    num: "04",
    index: 3,
    title: "Risk Scoring",
    body: "Deterministic, explainable composite scoring — weighted wave, wind, visibility, and cyclone proximity. No LLM in the safety-critical path.",
  },
];

const FEATURES_ROW_2 = [
  {
    num: "05",
    index: 4,
    title: "Multilingual, by voice",
    body: "Ask in English, Hindi, or Tamil — speak or type. Answers come back the same way, read aloud on request. Groq Whisper for transcription, Sarvam AI for synthesis.",
  },
  {
    num: "06",
    index: 5,
    title: "Every claim, sourced",
    body: "Answers cite the exact agent and data source behind every number — provenance tiers from official national (INCOIS/IMD) through global awareness (GDACS) to operational model (Open-Meteo). No fabricated claims, ever.",
  },
];

export const FeaturesSection: React.FC<Props> = ({
  language,
  className = "",
}) => {
  const t = translations[language] || translations.en;
  const sectionRef = useRef<HTMLElement>(null);
  const [isVisible, setIsVisible] = useState(false);

  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            setIsVisible(true);
            observer.disconnect();
          }
        });
      },
      { threshold: 0.12 }
    );

    if (sectionRef.current) {
      observer.observe(sectionRef.current);
    }

    return () => observer.disconnect();
  }, []);

  return (
    <section ref={sectionRef} className={`py-16 sm:py-20 lg:py-24 ${className}`}>
      <div className="max-w-[1200px] mx-auto w-full px-6 sm:px-10 lg:px-16">

        {/* Section label — small mono, left-aligned */}
        <div
          className={`font-mono-data text-[11px] text-[var(--ink-muted)] tracking-widest uppercase mb-4 transition-all duration-500 ${
            isVisible ? "reveal-visible" : "reveal-init"
          }`}
        >
          WHAT TARANG DOES
        </div>

        {/* Section intro — Fraunces, medium size */}
        <p
          className={`font-serif-display text-xl sm:text-2xl lg:text-3xl font-normal text-[var(--ink)] leading-snug max-w-[600px] mb-10 sm:mb-14 transition-all duration-500 delay-100 ${
            isVisible ? "reveal-visible" : "reveal-init"
          }`}
        >
          Six specialized agents, one grounded answer.
        </p>

        {/* ── Row 1: Four columns (unequal to row 2) ── */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-0 border-t border-[var(--border)]">
          {FEATURES_ROW_1.map((feat) => (
            <div
              key={feat.num}
              style={{
                transitionDelay: isVisible ? `${feat.index * 75}ms` : "0ms",
              }}
              className={`py-6 sm:py-8 pr-6 lg:pr-8 border-b lg:border-b-0 lg:border-r border-[var(--border)] last:border-r-0 last:border-b-0 flex flex-col transition-all duration-500 ${
                isVisible ? "reveal-visible" : "reveal-init"
              }`}
            >
              {/* Micro-diagram & Number row */}
              <div className="flex items-center justify-between mb-4">
                <span className="font-mono-data text-[11px] text-[var(--ink-subtle)] tracking-widest block">
                  {feat.num}
                </span>
                <div className="w-8 h-8 flex items-center justify-center text-[var(--current)]" aria-hidden="true">
                  {feat.num === "01" && (
                    <svg width="32" height="32" viewBox="0 0 34 34" fill="none" xmlns="http://www.w3.org/2000/svg">
                      <path d="M4 19C7.5 15.5 11 15.5 14.5 19C18 22.5 21.5 22.5 25 19C27.5 16.5 29.5 16.5 30 17" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                      <path d="M4 25C7.5 21.5 11 21.5 14.5 25C18 28.5 21.5 28.5 25 25C27.5 22.5 29.5 22.5 30 23" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" opacity="0.35"/>
                      <path d="M9 11C13 9 19 9 24 11" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
                      <path d="M22 8L25 11L22 14" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                    </svg>
                  )}
                  {feat.num === "02" && (
                    <svg width="32" height="32" viewBox="0 0 34 34" fill="none" xmlns="http://www.w3.org/2000/svg">
                      <circle cx="17" cy="17" r="13" stroke="currentColor" strokeWidth="1.5" opacity="0.25"/>
                      <path d="M17 17L26 8" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
                      <circle cx="17" cy="17" r="2.5" fill="currentColor"/>
                      <circle cx="21" cy="12" r="1.5" fill="var(--dawn)"/>
                      <circle cx="13" cy="22" r="1.5" fill="currentColor"/>
                      <circle cx="23" cy="20" r="1.5" fill="currentColor" opacity="0.6"/>
                      <path d="M17 4A13 13 0 0 1 30 17" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
                    </svg>
                  )}
                  {feat.num === "03" && (
                    <svg width="32" height="32" viewBox="0 0 34 34" fill="none" xmlns="http://www.w3.org/2000/svg">
                      <circle cx="17" cy="17" r="13" stroke="currentColor" strokeWidth="1.5" strokeDasharray="3 3" opacity="0.35"/>
                      <circle cx="17" cy="17" r="7" stroke="currentColor" strokeWidth="1.5" opacity="0.6"/>
                      <path d="M17 7C14 7 12 9 12 12C12 17 22 17 22 22C22 25 20 27 17 27" stroke="var(--dawn)" strokeWidth="1.5" strokeLinecap="round"/>
                      <circle cx="17" cy="17" r="2" fill="var(--dawn)"/>
                    </svg>
                  )}
                  {feat.num === "04" && (
                    <svg width="32" height="32" viewBox="0 0 34 34" fill="none" xmlns="http://www.w3.org/2000/svg">
                      <path d="M6 24A13 13 0 1 1 28 24" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
                      <path d="M17 17L22 12" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
                      <circle cx="17" cy="17" r="2.5" fill="currentColor"/>
                      <line x1="6" y1="24" x2="8" y2="24" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
                      <line x1="17" y1="4" x2="17" y2="6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
                      <line x1="28" y1="24" x2="26" y2="24" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
                    </svg>
                  )}
                </div>
              </div>

              {/* Title — sans, semibold */}
              <h3 className="text-sm sm:text-base font-semibold text-[var(--ink)] mb-2">
                {feat.title}
              </h3>

              {/* Body — small, muted, specific copy */}
              <p className="text-xs sm:text-sm text-[var(--ink-muted)] leading-relaxed">
                {feat.body}
              </p>
            </div>
          ))}
        </div>

        {/* ── Row 2: Two wider columns — deliberately asymmetric vs row 1 ── */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-0 border-t border-[var(--border)] mt-0">
          {FEATURES_ROW_2.map((feat) => (
            <div
              key={feat.num}
              style={{
                transitionDelay: isVisible ? `${feat.index * 75}ms` : "0ms",
              }}
              className={`py-6 sm:py-8 pr-6 lg:pr-12 border-b sm:border-b-0 sm:border-r border-[var(--border)] last:border-r-0 last:border-b-0 flex flex-col transition-all duration-500 ${
                isVisible ? "reveal-visible" : "reveal-init"
              }`}
            >
              {/* Micro-diagram & Number row */}
              <div className="flex items-center justify-between mb-4">
                <span className="font-mono-data text-[11px] text-[var(--ink-subtle)] tracking-widest block">
                  {feat.num}
                </span>
                <div className="w-8 h-8 flex items-center justify-center text-[var(--current)]" aria-hidden="true">
                  {feat.num === "05" && (
                    <svg width="32" height="32" viewBox="0 0 34 34" fill="none" xmlns="http://www.w3.org/2000/svg">
                      <path d="M5 9C5 6.79086 6.79086 5 9 5H21C23.2091 5 25 6.79086 25 9V17C25 19.2091 23.2091 21 21 21H13L7 26V21H9C6.79086 21 5 19.2091 5 17V9Z" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                      <path d="M11 13V13.01" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
                      <path d="M15 11V15" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
                      <path d="M19 12V14" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
                      <path d="M28 10C29.5 11.5 29.5 14.5 28 16" stroke="var(--dawn)" strokeWidth="1.5" strokeLinecap="round"/>
                    </svg>
                  )}
                  {feat.num === "06" && (
                    <svg width="32" height="32" viewBox="0 0 34 34" fill="none" xmlns="http://www.w3.org/2000/svg">
                      <circle cx="10" cy="11" r="3.5" stroke="currentColor" strokeWidth="1.5"/>
                      <circle cx="24" cy="11" r="3.5" stroke="currentColor" strokeWidth="1.5"/>
                      <circle cx="17" cy="23" r="3.5" stroke="currentColor" strokeWidth="1.5"/>
                      <path d="M13.5 11H20.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
                      <path d="M12 14L15 20" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
                      <path d="M22 14L19 20" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
                      <circle cx="17" cy="23" r="1" fill="var(--current)"/>
                    </svg>
                  )}
                </div>
              </div>

              {/* Title — sans, semibold */}
              <h3 className="text-sm sm:text-base font-semibold text-[var(--ink)] mb-2">
                {feat.title}
              </h3>

              {/* Body — small, muted, specific copy */}
              <p className="text-xs sm:text-sm text-[var(--ink-muted)] leading-relaxed">
                {feat.body}
              </p>
            </div>
          ))}
        </div>

      </div>
    </section>
  );
};
