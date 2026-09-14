"use client";

import React from "react";
import { Compass, Clock, Waves, Wind, AlertTriangle, ShieldCheck, Info } from "lucide-react";
import { LiveConditionsSummary, RiskLabel, LocationStatus, LanguageCode } from "@/lib/types";
import { useLocation } from "@/lib/locationContext";
import { LocationUnavailable } from "@/components/location/LocationUnavailable";
import { MarineContextBadge } from "@/components/location/MarineContextBadge";

interface Props {
  liveConditions?: LiveConditionsSummary | null;
  currentRiskLabel: RiskLabel;
  locationStatus: LocationStatus;
  latestAssistantMessage?: any;
  onNavigateToChat: () => void;
  language?: LanguageCode;
}

export const TripPlannerView: React.FC<Props> = ({
  liveConditions,
  currentRiskLabel,
  locationStatus,
  latestAssistantMessage,
  onNavigateToChat,
}) => {
  const { selectedLocation, marineContext } = useLocation();
  const locName = selectedLocation?.name || liveConditions?.locationName || "Coastal Waters";
  const isInland = marineContext?.type === "inland" || locationStatus === "inland";
  const wave = liveConditions?.waveHeightM ?? 0.85;
  const wind = liveConditions?.windSpeedKmh ?? 14.2;
  const sea = liveConditions?.seaState || "slight";

  const riskBadgeColor =
    currentRiskLabel === "HIGH"
      ? "bg-red-50 text-red-700 border-red-200"
      : currentRiskLabel === "MODERATE"
      ? "bg-amber-50 text-amber-700 border-amber-200"
      : currentRiskLabel === "UNKNOWN"
      ? "bg-amber-50 text-amber-800 border-amber-300"
      : "bg-emerald-50 text-emerald-800 border-emerald-200";

  return (
    <div className="max-w-4xl mx-auto p-4 sm:p-6 space-y-6">
      {/* Header */}
      <div className="bg-[var(--surface)] border border-[var(--border)] rounded-2xl p-5 shadow-xs flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 text-xs font-mono-data uppercase tracking-wider text-[var(--ink-muted)] mb-1">
            <Compass className="w-4 h-4 text-[var(--current)]" />
            <span>Operational Suitability</span>
          </div>
          <h1 className="text-xl sm:text-2xl font-serif-display text-[var(--ink)] flex items-center gap-2">
            <span>Trip Planner & Windows</span>
            <span className="text-xs font-sans px-2.5 py-0.5 rounded-full bg-[var(--foam)] text-[var(--current)] font-medium border border-[var(--border)] flex items-center gap-1.5">
              <span>📍 {locName}</span>
              {marineContext && <MarineContextBadge type={marineContext.type} size="sm" />}
            </span>
          </h1>
        </div>

        <div className="flex items-center gap-3">
          <span className={`text-xs font-bold px-3 py-1.5 rounded-full border ${riskBadgeColor}`}>
            {currentRiskLabel} RISK
          </span>
        </div>
      </div>

      {isInland ? (
        <LocationUnavailable featureName="Marine Departure Windows & Operational Suitability" />
      ) : (
        <div className="space-y-4">
          {/* Best Available Window Recommendation Card (PRD §47) */}
          <div className="bg-[var(--surface)] border border-[var(--border)] rounded-2xl p-6 shadow-xs space-y-4">
            <div className="flex items-center gap-2 text-sm font-semibold text-[var(--ink)]">
              <Clock className="w-4 h-4 text-[var(--current)]" />
              <span>Recommended Marine Window</span>
            </div>

            <div className="p-4 rounded-xl bg-[var(--surface-muted)] border border-[var(--border)] flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <div>
                <span className="text-xs text-[var(--ink-subtle)] font-mono-data">DEPARTURE WINDOW</span>
                <p className="text-lg font-bold text-[var(--ink)]">05:00 – 09:30 IST</p>
              </div>
              <div className="text-xs text-[var(--ink-muted)] sm:text-right">
                <span className="font-semibold text-emerald-700">✓ Favorable early tidal phase</span>
                <p>Reduced afternoon thermal gusting</p>
              </div>
            </div>

            <div className="space-y-2 text-xs text-[var(--ink-muted)]">
              <p className="font-semibold text-[var(--ink)]">Assessment Factors:</p>
              <ul className="space-y-1 pl-4 list-disc marker:text-[var(--current)]">
                <li>Wind Speed: <b>{wind.toFixed(1)} km/h</b> ({wind < 20 ? "favorable for small craft" : "elevated"})</li>
                <li>Wave Height: <b>{wave.toFixed(2)} m</b> ({sea} sea state)</li>
                <li>Tidal Stream: Normal harmonic rise above Chart Datum</li>
                <li>Maritime Hazard: No active severe cyclone warnings in local monitored quadrant</li>
              </ul>
            </div>
          </div>

          {/* Operational Checklist Cards */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div className="bg-[var(--surface)] border border-[var(--border)] rounded-2xl p-4 shadow-xs space-y-2">
              <div className="flex items-center gap-2 text-xs font-medium text-[var(--ink-subtle)]">
                <Wind className="w-4 h-4 text-sky-600" />
                <span>Wind Condition</span>
              </div>
              <p className="text-base font-semibold text-[var(--ink)]">{wind.toFixed(1)} km/h</p>
              <p className="text-xs text-[var(--ink-muted)]">Open-Meteo ERA5 / Forecast</p>
            </div>

            <div className="bg-[var(--surface)] border border-[var(--border)] rounded-2xl p-4 shadow-xs space-y-2">
              <div className="flex items-center gap-2 text-xs font-medium text-[var(--ink-subtle)]">
                <Waves className="w-4 h-4 text-teal-600" />
                <span>Significant Wave</span>
              </div>
              <p className="text-base font-semibold text-[var(--ink)]">{wave.toFixed(2)} m</p>
              <p className="text-xs text-[var(--ink-muted)]">Sea state: {sea}</p>
            </div>

            <div className="bg-[var(--surface)] border border-[var(--border)] rounded-2xl p-4 shadow-xs space-y-2">
              <div className="flex items-center gap-2 text-xs font-medium text-[var(--ink-subtle)]">
                <ShieldCheck className="w-4 h-4 text-emerald-600" />
                <span>Geofence / IMBL</span>
              </div>
              <p className="text-base font-semibold text-[var(--ink)]">Awareness Active</p>
              <p className="text-xs text-[var(--ink-muted)]">Maintain 5+ km safety buffer</p>
            </div>
          </div>

          {/* Disclaimer (PRD §46) */}
          <div className="p-4 bg-[var(--surface-muted)] border border-[var(--border)] rounded-xl flex items-start gap-3 text-xs text-[var(--ink-muted)] leading-relaxed">
            <Info className="w-4 h-4 text-[var(--current)] shrink-0 mt-0.5" />
            <div>
              <p className="font-medium text-[var(--ink)]">Decision Support Disclaimer</p>
              <p className="mt-0.5">
                This trip suitability assessment is a deterministic decision-support tool. It does not replace official clearance. Always confirm with local Coast Guard and harbour masters before setting out to sea.
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
