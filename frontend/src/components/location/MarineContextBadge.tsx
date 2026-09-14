"use client";

import React from "react";
import { MarineContextType } from "@/lib/types";

interface MarineContextBadgeProps {
  type: MarineContextType;
  className?: string;
  size?: "sm" | "md";
}

export function MarineContextBadge({ type, className = "", size = "sm" }: MarineContextBadgeProps) {
  const sizeClasses = size === "sm" ? "px-1.5 py-0.5 text-[10px]" : "px-2 py-1 text-xs";

  switch (type) {
    case "coastal":
      return (
        <span
          className={`inline-flex items-center gap-1 font-semibold rounded-full border border-emerald-500/30 bg-emerald-500/10 text-emerald-400 uppercase tracking-wider ${sizeClasses} ${className}`}
          title="Coastal region: full marine, tidal, and fishing potential data available"
        >
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
          Coastal
        </span>
      );
    case "offshore":
      return (
        <span
          className={`inline-flex items-center gap-1 font-semibold rounded-full border border-cyan-500/30 bg-cyan-500/10 text-cyan-400 uppercase tracking-wider ${sizeClasses} ${className}`}
          title="Offshore marine coordinates: sea state, open-water risk, and fishing potential active"
        >
          <span className="w-1.5 h-1.5 rounded-full bg-cyan-400" />
          Offshore
        </span>
      );
    case "inland":
      return (
        <span
          className={`inline-flex items-center gap-1 font-semibold rounded-full border border-amber-500/30 bg-amber-500/10 text-amber-400 uppercase tracking-wider ${sizeClasses} ${className}`}
          title="Inland region: marine features (tides, PFZ) not applicable"
        >
          <span className="w-1.5 h-1.5 rounded-full bg-amber-400" />
          Inland
        </span>
      );
    default:
      return (
        <span
          className={`inline-flex items-center gap-1 font-semibold rounded-full border border-slate-600/40 bg-slate-700/20 text-slate-300 uppercase tracking-wider ${sizeClasses} ${className}`}
        >
          Location
        </span>
      );
  }
}
