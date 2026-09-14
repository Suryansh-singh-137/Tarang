"use client";

import React from "react";
import { MarineContextType } from "@/lib/types";

interface MarineContextBadgeProps {
  type: MarineContextType;
  className?: string;
  size?: "sm" | "md";
}

export function MarineContextBadge({ type, className = "", size = "sm" }: MarineContextBadgeProps) {
  const sizeClasses = size === "sm" ? "px-2 py-0.5 text-[10px]" : "px-2.5 py-1 text-[11px]";

  switch (type) {
    case "coastal":
      return (
        <span
          className={`inline-flex items-center gap-1.5 font-mono-data font-medium rounded-full border border-[#C3E8D2] bg-[#EBF7F0] text-[#1B8755] uppercase tracking-wider ${sizeClasses} ${className}`}
          title="Coastal region: full marine, tidal, and fishing potential data available"
        >
          <span className="w-1.5 h-1.5 rounded-full bg-[#1B8755]" />
          Coastal
        </span>
      );
    case "offshore":
      return (
        <span
          className={`inline-flex items-center gap-1.5 font-mono-data font-medium rounded-full border border-[var(--current)]/30 bg-[var(--foam)] text-[var(--current)] uppercase tracking-wider ${sizeClasses} ${className}`}
          title="Offshore marine coordinates: sea state, open-water risk, and fishing potential active"
        >
          <span className="w-1.5 h-1.5 rounded-full bg-[var(--current)]" />
          Offshore
        </span>
      );
    case "inland":
      return (
        <span
          className={`inline-flex items-center gap-1.5 font-mono-data font-medium rounded-full border border-[#FDE68A] bg-[#FEF3C7] text-[#B45309] uppercase tracking-wider ${sizeClasses} ${className}`}
          title="Inland region: marine features (tides, PFZ) not applicable"
        >
          <span className="w-1.5 h-1.5 rounded-full bg-[#D97706]" />
          Inland
        </span>
      );
    default:
      return (
        <span
          className={`inline-flex items-center gap-1.5 font-mono-data font-medium rounded-full border border-[var(--border)] bg-[var(--surface-muted)] text-[var(--ink-muted)] uppercase tracking-wider ${sizeClasses} ${className}`}
        >
          Location
        </span>
      );
  }
}
