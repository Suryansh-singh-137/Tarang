import React from "react";
import { Globe } from "lucide-react";
import { LanguageCode } from "@/lib/types";

interface Props {
  currentLanguage: LanguageCode;
  onSelectLanguage: (lang: LanguageCode) => void;
  className?: string;
  detectedBadge?: string | null;
}

const LANGUAGES: Array<{ code: LanguageCode; label: string; native: string }> = [
  { code: "en", label: "English", native: "EN" },
  { code: "hi", label: "Hindi", native: "हिं" },
  { code: "ta", label: "Tamil", native: "த" },
];

export const LanguageToggle: React.FC<Props> = ({
  currentLanguage,
  onSelectLanguage,
  className = "",
  detectedBadge,
}) => {
  return (
    <div className={`flex items-center gap-1.5 p-1 bg-[var(--surface)] border border-[var(--border)] rounded-full shadow-xs ${className}`}>
      <div className="pl-2 pr-1 text-[var(--ink-subtle)] flex items-center gap-1" title="Select interface language">
        <Globe className="w-3.5 h-3.5" />
      </div>

      <div className="flex items-center gap-1">
        {LANGUAGES.map((lang) => {
          const isActive = currentLanguage === lang.code;
          return (
            <button
              key={lang.code}
              type="button"
              onClick={() => onSelectLanguage(lang.code)}
              className={`min-w-[40px] h-8 px-2.5 rounded-full text-xs font-medium transition-all ${
                isActive
                  ? "bg-[var(--current)] text-white shadow-xs font-semibold"
                  : "text-[var(--ink-muted)] hover:bg-[var(--foam)] hover:text-[var(--ink)]"
              }`}
              title={lang.label}
              aria-pressed={isActive}
            >
              {lang.native}
            </button>
          );
        })}
      </div>

      {detectedBadge && (
        <span className="hidden sm:inline-block text-[11px] font-medium text-[var(--current)] bg-[var(--foam)] px-2 py-0.5 rounded-full mr-1">
          Auto: {detectedBadge}
        </span>
      )}
    </div>
  );
};
