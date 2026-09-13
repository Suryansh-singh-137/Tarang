import React from "react";
import { ShieldCheck, AlertTriangle, AlertOctagon, HelpCircle, Flame } from "lucide-react";
import { RiskLabel } from "@/lib/types";

interface Props {
  label: RiskLabel | string;
  score?: number | null;
  size?: "sm" | "md" | "lg";
  className?: string;
  showScore?: boolean;
}

export const RiskBadge: React.FC<Props> = ({
  label,
  score,
  size = "md",
  className = "",
  showScore = true,
}) => {
  const norm = (typeof label === "string" ? label.toUpperCase() : "UNKNOWN") as RiskLabel;

  // Distinct shapes, colors, and iconography for accessibility & sunlight legibility
  switch (norm) {
    case "LOW":
      return (
        <span
          className={`inline-flex items-center gap-1.5 font-medium border transition-all ${
            size === "sm"
              ? "px-2.5 py-1 text-xs rounded-full"
              : size === "lg"
              ? "px-4 py-2 text-base rounded-full"
              : "px-3 py-1.5 text-sm rounded-full"
          } bg-[#EBF7F0] text-[#1B8755] border-[#A8DFBF] shadow-xs ${className}`}
          aria-label={`Low safety risk verdict${score != null ? `, score ${score} out of 100` : ""}`}
        >
          {/* Circular Shield icon indicates safe manageable sea */}
          <ShieldCheck className={size === "lg" ? "w-5 h-5" : size === "sm" ? "w-3.5 h-3.5" : "w-4 h-4"} />
          <span className="font-display font-semibold tracking-wide">LOW RISK</span>
          {showScore && score != null && (
            <span className="text-xs opacity-80 font-sans border-l border-[#1B8755]/30 pl-1.5 ml-0.5">
              {score.toFixed(1)}/100
            </span>
          )}
        </span>
      );

    case "MODERATE":
      return (
        <span
          className={`inline-flex items-center gap-1.5 font-medium border transition-all ${
            size === "sm"
              ? "px-2.5 py-1 text-xs rounded-md"
              : size === "lg"
              ? "px-4 py-2 text-base rounded-md"
              : "px-3 py-1.5 text-sm rounded-md"
          } bg-[#FEF3C7] text-[#B45309] border-[#FDE68A] shadow-xs ${className}`}
          aria-label={`Moderate safety risk verdict${score != null ? `, score ${score} out of 100` : ""}`}
        >
          {/* Triangular Caution icon */}
          <AlertTriangle className={size === "lg" ? "w-5 h-5" : size === "sm" ? "w-3.5 h-3.5" : "w-4 h-4"} />
          <span className="font-display font-semibold tracking-wide">MODERATE RISK</span>
          {showScore && score != null && (
            <span className="text-xs opacity-80 font-sans border-l border-[#B45309]/30 pl-1.5 ml-0.5">
              {score.toFixed(1)}/100
            </span>
          )}
        </span>
      );

    case "HIGH":
      return (
        <span
          className={`inline-flex items-center gap-1.5 font-semibold border-2 transition-all ${
            size === "sm"
              ? "px-2.5 py-1 text-xs rounded-lg"
              : size === "lg"
              ? "px-4 py-2 text-base rounded-lg"
              : "px-3 py-1.5 text-sm rounded-lg"
          } bg-[#FEE2E2] text-[#DC2626] border-[#FCA5A5] shadow-xs ${className}`}
          aria-label={`High safety risk verdict${score != null ? `, score ${score} out of 100` : ""}`}
        >
          {/* Octagonal Alert icon */}
          <AlertOctagon className={size === "lg" ? "w-5 h-5" : size === "sm" ? "w-3.5 h-3.5" : "w-4 h-4"} />
          <span className="font-display font-bold tracking-wide">HIGH RISK</span>
          {showScore && score != null && (
            <span className="text-xs opacity-90 font-sans border-l border-[#DC2626]/30 pl-1.5 ml-0.5">
              {score.toFixed(1)}/100
            </span>
          )}
        </span>
      );

    case "EXTREME":
      return (
        <span
          className={`inline-flex items-center gap-1.5 font-bold border-2 transition-all animate-pulse ${
            size === "sm"
              ? "px-2.5 py-1 text-xs rounded-lg"
              : size === "lg"
              ? "px-4 py-2 text-base rounded-lg"
              : "px-3 py-1.5 text-sm rounded-lg"
          } bg-[#7F1D1D] text-white border-[#DC2626] shadow-sm ${className}`}
          aria-label={`Extreme safety risk verdict${score != null ? `, score ${score} out of 100` : ""}`}
        >
          {/* Flame warning for severe danger / cyclone */}
          <Flame className={size === "lg" ? "w-5 h-5" : size === "sm" ? "w-3.5 h-3.5" : "w-4 h-4"} />
          <span className="font-display font-bold tracking-wide">EXTREME RISK</span>
          {showScore && score != null && (
            <span className="text-xs opacity-95 font-sans border-l border-white/40 pl-1.5 ml-0.5">
              {score.toFixed(1)}/100
            </span>
          )}
        </span>
      );

    case "UNKNOWN":
    default:
      return (
        <span
          className={`inline-flex items-center gap-1.5 font-medium border transition-all ${
            size === "sm"
              ? "px-2 py-0.5 text-xs rounded-full"
              : size === "lg"
              ? "px-3.5 py-1.5 text-base rounded-full"
              : "px-3 py-1 text-sm rounded-full"
          } bg-[#F3F4F6] text-[#4B5563] border-[#E5E7EB] ${className}`}
          aria-label="Safety risk verdict unknown due to missing or unverified data"
        >
          <HelpCircle className={size === "lg" ? "w-4.5 h-4.5" : size === "sm" ? "w-3.5 h-3.5" : "w-4 h-4"} />
          <span className="font-display font-medium tracking-wide">UNKNOWN</span>
        </span>
      );
  }
};
