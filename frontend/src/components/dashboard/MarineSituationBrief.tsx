"use client";

import React from "react";
import { Shield, RefreshCw, MapPin, AlertTriangle, Compass, Waves, Wind, Clock, HelpCircle } from "lucide-react";
import { MarineSnapshot, RiskLabel } from "@/lib/types";

interface MarineSituationBriefProps {
  snapshot?: MarineSnapshot | null;
  onWhyThisResult?: () => void;
  onRecheck?: () => void;
  onLocationChange?: () => void;
  isRechecking?: boolean;
}

export function MarineSituationBrief({
  snapshot,
  onWhyThisResult,
  onRecheck,
  onLocationChange,
  isRechecking = false,
}: MarineSituationBriefProps) {
  if (!snapshot) return null;

  const loc = snapshot.location;
  const risk = snapshot.risk;
  const weather = snapshot.weather;
  const ocean = snapshot.ocean;
  const hazards = snapshot.hazards;

  const riskLabel: RiskLabel = risk.final_level || risk.risk_label || "LOW";

  const getRiskColor = (label: RiskLabel) => {
    switch (label) {
      case "LOW":
        return {
          bg: "bg-emerald-500/10 border-emerald-500/30 text-emerald-400",
          badge: "bg-emerald-500/20 text-emerald-300 border-emerald-500/40",
          dot: "bg-emerald-400 shadow-[0_0_8px_#34d399]",
        };
      case "MODERATE":
        return {
          bg: "bg-amber-500/10 border-amber-500/30 text-amber-400",
          badge: "bg-amber-500/20 text-amber-300 border-amber-500/40",
          dot: "bg-amber-400 shadow-[0_0_8px_#fbbf24]",
        };
      case "HIGH":
      case "EXTREME":
        return {
          bg: "bg-red-500/10 border-red-500/30 text-red-400",
          badge: "bg-red-500/20 text-red-300 border-red-500/40",
          dot: "bg-red-400 shadow-[0_0_8px_#f87171]",
        };
      default:
        return {
          bg: "bg-slate-500/10 border-slate-500/30 text-slate-300",
          badge: "bg-slate-500/20 text-slate-300 border-slate-500/40",
          dot: "bg-slate-400",
        };
    }
  };

  const style = getRiskColor(riskLabel);

  // Derive plain-language summary line
  const activeWarns = hazards?.active_warnings || [];
  let summaryLine = "";
  if (riskLabel === "LOW") {
    summaryLine = "Sea conditions are calm and rated low risk. Always check official port advisories before leaving shore.";
  } else if (riskLabel === "MODERATE") {
    summaryLine = "Caution advised: moderate waves or freshening breeze present. Review harbor advisory.";
  } else if (riskLabel === "HIGH" || riskLabel === "EXTREME") {
    summaryLine = activeWarns.length > 0 
      ? `High risk: active ${activeWarns.join(", ")} warning in effect. Avoid departure.`
      : "High risk: sea conditions are hazardous for small craft. Stay ashore.";
  } else {
    summaryLine = "Tarang is gathering live sensor data to assess marine conditions.";
  }

  // Format timestamp
  const timeStr = snapshot.generated_at
    ? new Date(snapshot.generated_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
    : "Live";

  return (
    <div className="relative overflow-hidden rounded-2xl border border-slate-800/90 bg-gradient-to-b from-slate-900/90 via-slate-900/80 to-slate-950/90 backdrop-blur-xl p-4 sm:p-5 shadow-2xl transition-all mb-4">
      {/* Subtle background glow */}
      <div className="absolute -right-20 -top-20 w-56 h-56 rounded-full bg-cyan-500/5 blur-3xl pointer-events-none" />

      {/* Top Header: Location, Status & Action Controls */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-800/60 pb-3.5 mb-3.5">
        <div className="flex items-center gap-2.5">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-cyan-500/10 border border-cyan-500/20 text-cyan-400">
            <MapPin className="h-4 w-4" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-base font-semibold text-slate-100 tracking-tight">
                {loc.name || "Coastal Waters"}
              </h2>
              {loc.coastal ? (
                <span className="rounded-full bg-cyan-950/60 border border-cyan-800/40 px-2 py-0.5 text-[10px] font-medium text-cyan-400">
                  Coastal Harbor
                </span>
              ) : (
                <span className="rounded-full bg-amber-950/60 border border-amber-800/40 px-2 py-0.5 text-[10px] font-medium text-amber-400">
                  Inland
                </span>
              )}
            </div>
            <p className="text-xs text-slate-400 flex items-center gap-1.5 mt-0.5">
              <span>{loc.lat ? `${loc.lat.toFixed(2)}°N, ${loc.lon.toFixed(2)}°E` : "Location identified"}</span>
              <span>•</span>
              <span className="flex items-center gap-1">
                <Clock className="h-3 w-3 text-slate-400" />
                Updated {timeStr}
              </span>
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {onLocationChange && (
            <button
              onClick={onLocationChange}
              className="rounded-lg border border-slate-700/60 bg-slate-800/60 hover:bg-slate-750 px-2.5 py-1.5 text-xs font-medium text-slate-300 transition-colors hover:text-white"
              title="Change harbor or coastal point"
            >
              Change Location
            </button>
          )}

          {onWhyThisResult && (
            <button
              onClick={onWhyThisResult}
              className="flex items-center gap-1.5 rounded-lg border border-indigo-500/30 bg-indigo-950/40 hover:bg-indigo-900/50 px-3 py-1.5 text-xs font-medium text-indigo-300 transition-colors hover:border-indigo-500/50"
              title="Explain how this verdict was calculated"
            >
              <HelpCircle className="h-3.5 w-3.5" />
              <span>Why this result?</span>
            </button>
          )}

          {onRecheck && (
            <button
              onClick={onRecheck}
              disabled={isRechecking}
              className="flex items-center gap-1.5 rounded-lg border border-cyan-500/40 bg-cyan-500/10 hover:bg-cyan-500/20 px-3 py-1.5 text-xs font-medium text-cyan-300 transition-all disabled:opacity-50"
              title="Check latest conditions again"
            >
              <RefreshCw className={`h-3.5 w-3.5 ${isRechecking ? "animate-spin" : ""}`} />
              <span>{isRechecking ? "Checking..." : "Re-check"}</span>
            </button>
          )}
        </div>
      </div>

      {/* Main Situation Row: Verdict & Vital Marine Stats */}
      <div className="grid grid-cols-1 md:grid-cols-12 gap-3.5 items-center">
        {/* Left Side: Badge + 1-Line Plain English Summary */}
        <div className="md:col-span-7 flex flex-col sm:flex-row sm:items-center gap-3">
          <div className={`inline-flex items-center gap-2 rounded-xl border px-3 py-2 shrink-0 ${style.badge}`}>
            <span className={`h-2.5 w-2.5 rounded-full ${style.dot}`} />
            <span className="text-xs font-bold uppercase tracking-wider">
              {riskLabel} RISK
            </span>
          </div>

          <div className="flex-1 min-w-0">
            <p className="text-xs sm:text-sm text-slate-200 leading-relaxed font-medium">
              {summaryLine}
            </p>
            {/* Top risk contributor if caution/risky */}
            {riskLabel !== "LOW" && risk.top_factor && (
              <p className="text-[11px] text-amber-300/90 flex items-center gap-1 mt-1 font-medium">
                <AlertTriangle className="h-3 w-3 shrink-0" />
                <span>Elevated by: {risk.top_factor}</span>
              </p>
            )}
          </div>
        </div>

        {/* Right Side: Key Marine Micro-Stats */}
        <div className="md:col-span-5 grid grid-cols-3 gap-2 bg-slate-950/50 rounded-xl p-2.5 border border-slate-800/60">
          <div className="flex flex-col items-center justify-center text-center p-1">
            <span className="text-[10px] text-slate-400 uppercase tracking-wider flex items-center gap-1 mb-0.5">
              <Waves className="h-3 w-3 text-cyan-400" /> Wave
            </span>
            <span className="text-xs sm:text-sm font-semibold text-slate-200">
              {weather.wave_height_m !== null && weather.wave_height_m !== undefined ? `${weather.wave_height_m}m` : "—"}
            </span>
          </div>

          <div className="flex flex-col items-center justify-center text-center p-1 border-x border-slate-800/80">
            <span className="text-[10px] text-slate-400 uppercase tracking-wider flex items-center gap-1 mb-0.5">
              <Wind className="h-3 w-3 text-cyan-400" /> Wind
            </span>
            <span className="text-xs sm:text-sm font-semibold text-slate-200">
              {weather.wind_speed_kmh !== null && weather.wind_speed_kmh !== undefined ? `${weather.wind_speed_kmh} km/h` : "—"}
            </span>
          </div>

          <div className="flex flex-col items-center justify-center text-center p-1">
            <span className="text-[10px] text-slate-400 uppercase tracking-wider flex items-center gap-1 mb-0.5">
              <Compass className="h-3 w-3 text-cyan-400" /> Tide
            </span>
            <span className="text-xs sm:text-sm font-semibold text-slate-200 truncate max-w-full">
              {ocean.current_phase || (ocean.water_level_m ? `${ocean.water_level_m}m` : "Predicted")}
            </span>
          </div>
        </div>
      </div>

      {/* Active Warning Banner (PRD §8) */}
      {activeWarns.length > 0 && (
        <div className="mt-3 flex items-center gap-2 rounded-lg bg-amber-500/10 border border-amber-500/30 px-3 py-1.5 text-xs text-amber-300">
          <AlertTriangle className="h-3.5 w-3.5 text-amber-400 shrink-0" />
          <span className="font-semibold">Active Harbor Advisory:</span>
          <span>{activeWarns.join(", ")}</span>
        </div>
      )}
    </div>
  );
}
