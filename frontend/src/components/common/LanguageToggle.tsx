"use client";

import React, { useState, useRef, useEffect } from "react";
import { Globe, ChevronDown, Check } from "lucide-react";
import { LanguageCode } from "@/lib/types";

interface Props {
  currentLanguage: LanguageCode;
  onSelectLanguage: (lang: LanguageCode) => void;
  className?: string;
  detectedBadge?: string | null;
}

interface LanguageDef {
  code: LanguageCode;
  label: string;
  native: string;
  short: string;
  region: string;
}

export const LANGUAGES: LanguageDef[] = [
  { code: "en", label: "English", native: "English", short: "EN", region: "Maritime Lingua Franca" },
  { code: "hi", label: "Hindi", native: "हिन्दी", short: "हिं", region: "National" },
  { code: "gu", label: "Gujarati", native: "ગુજરાતી", short: "ગુજ", region: "Gujarat Coast" },
  { code: "bn", label: "Bengali", native: "বাংলা", short: "বাଂ", region: "West Bengal Coast" },
  { code: "ta", label: "Tamil", native: "தமிழ்", short: "தமி", region: "Tamil Nadu Coast" },
  { code: "te", label: "Telugu", native: "తెలుగు", short: "తెలు", region: "Andhra Coast" },
  { code: "ml", label: "Malayalam", native: "മലയാളം", short: "മല", region: "Kerala / Malabar Coast" },
  { code: "mr", label: "Marathi", native: "मराठी", short: "मरा", region: "Maharashtra / Konkan" },
  { code: "od", label: "Odia", native: "ଓଡ଼ିଆ", short: "ଓଡ଼ି", region: "Odisha Coast" },
];

export const LanguageToggle: React.FC<Props> = ({
  currentLanguage,
  onSelectLanguage,
  className = "",
  detectedBadge,
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  const activeLang = LANGUAGES.find((l) => l.code === currentLanguage) || LANGUAGES[0];

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    };
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setIsOpen(false);
      }
    };

    if (isOpen) {
      document.addEventListener("mousedown", handleClickOutside);
      document.addEventListener("keydown", handleKeyDown);
    }
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [isOpen]);

  return (
    <div className={`relative inline-block ${className}`} ref={dropdownRef}>
      {/* Trigger Button */}
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center gap-2 px-3 py-1.5 bg-[var(--surface)] hover:bg-[var(--foam)] border border-[var(--border)] hover:border-[var(--current)]/40 rounded-full shadow-xs transition-all text-xs font-medium cursor-pointer select-none group"
        aria-haspopup="listbox"
        aria-expanded={isOpen}
        title="Select coastal language"
      >
        <Globe className="w-3.5 h-3.5 text-[var(--current)] transition-transform group-hover:rotate-12 duration-300" />
        <span className="font-semibold text-[var(--ink)] tracking-tight">
          {activeLang.native}
        </span>
        <span className="text-[var(--ink-muted)] hidden sm:inline text-[11px]">
          ({activeLang.label})
        </span>
        <ChevronDown
          className={`w-3.5 h-3.5 text-[var(--ink-muted)] transition-transform duration-200 ${
            isOpen ? "rotate-180 text-[var(--current)]" : ""
          }`}
        />

        {detectedBadge && (
          <span className="hidden md:inline-flex text-[10px] uppercase font-bold text-[var(--current)] bg-[var(--foam)] px-1.5 py-0.5 rounded-full border border-[var(--current)]/20 ml-0.5">
            Auto: {detectedBadge}
          </span>
        )}
      </button>

      {/* Floating Dropdown */}
      {isOpen && (
        <div
          role="listbox"
          className="absolute right-0 mt-2 w-72 sm:w-80 bg-[var(--surface)] border border-[var(--border)] rounded-2xl shadow-xl z-50 overflow-hidden backdrop-blur-md animate-in fade-in zoom-in-95 duration-150"
        >
          {/* Menu Header */}
          <div className="px-4 py-2.5 bg-[var(--foam)]/50 border-b border-[var(--border)] flex items-center justify-between">
            <div>
              <div className="text-xs font-semibold text-[var(--ink)]">
                Coastal Languages
              </div>
              <div className="text-[10px] text-[var(--ink-muted)]">
                9 Maritime & Coastal Regional Languages
              </div>
            </div>
            <span className="text-[10px] font-mono font-medium px-2 py-0.5 rounded-full bg-[var(--surface)] text-[var(--current)] border border-[var(--border)]">
              {LANGUAGES.length} Languages
            </span>
          </div>

          {/* Language Options Grid */}
          <div className="p-1.5 max-h-[340px] overflow-y-auto divide-y divide-[var(--border)]/30">
            {LANGUAGES.map((lang) => {
              const isSelected = lang.code === currentLanguage;
              return (
                <button
                  key={lang.code}
                  type="button"
                  role="option"
                  aria-selected={isSelected}
                  onClick={() => {
                    onSelectLanguage(lang.code);
                    setIsOpen(false);
                  }}
                  className={`w-full flex items-center justify-between px-3 py-2 text-left rounded-xl transition-colors cursor-pointer group ${
                    isSelected
                      ? "bg-[var(--current)] text-white shadow-xs font-semibold"
                      : "hover:bg-[var(--foam)] text-[var(--ink)]"
                  }`}
                >
                  <div className="flex flex-col min-w-0 pr-2">
                    <div className="flex items-center gap-2">
                      <span
                        className={`text-sm ${
                          isSelected ? "font-bold text-white" : "font-semibold text-[var(--ink)]"
                        }`}
                      >
                        {lang.native}
                      </span>
                      <span
                        className={`text-xs ${
                          isSelected ? "text-white/80" : "text-[var(--ink-muted)]"
                        }`}
                      >
                        • {lang.label}
                      </span>
                    </div>
                    <span
                      className={`text-[10px] truncate ${
                        isSelected ? "text-white/90 font-medium" : "text-[var(--ink-subtle)]"
                      }`}
                    >
                      {lang.region}
                    </span>
                  </div>

                  <div className="flex items-center gap-1 shrink-0">
                    <span
                      className={`text-[10px] font-mono px-1.5 py-0.5 rounded ${
                        isSelected
                          ? "bg-white/20 text-white"
                          : "bg-[var(--surface)] border border-[var(--border)] text-[var(--ink-muted)] group-hover:border-[var(--current)]/40"
                      }`}
                    >
                      {lang.short}
                    </span>
                    {isSelected && <Check className="w-4 h-4 text-white ml-1" />}
                  </div>
                </button>
              );
            })}
          </div>

          {/* Footer note */}
          <div className="px-3 py-1.5 bg-[var(--surface)] border-t border-[var(--border)] text-[10px] text-[var(--ink-subtle)] text-center">
            Automatic voice speech synthesis available in all languages
          </div>
        </div>
      )}
    </div>
  );
};
