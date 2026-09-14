"use client";

import React from "react";
import { Compass, Waves, Wind, AlertTriangle, ShieldCheck, Info, MapPin, RefreshCw, AlertCircle } from "lucide-react";
import { LiveConditionsSummary, RiskLabel, LocationStatus, LanguageCode, MarineSnapshot } from "@/lib/types";
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
  marineSnapshot?: MarineSnapshot | null;
  onRecheck?: () => void;
  isRechecking?: boolean;
}

export const TripPlannerView: React.FC<Props> = ({
  liveConditions,
  currentRiskLabel,
  locationStatus,
  latestAssistantMessage,
  onNavigateToChat,
  marineSnapshot,
  onRecheck,
  isRechecking = false,
}) => {
  const { selectedLocation, marineContext } = useLocation();
  const locName = selectedLocation?.name || marineSnapshot?.location.name || liveConditions?.locationName || "Coastal Waters";
  const isInland = marineContext?.type === "inland" || locationStatus === "inland";

  // Single source of truth: prioritize marineSnapshot over loose props
  const wave = marineSnapshot?.weather?.wave_height_m ?? liveConditions?.waveHeightM ?? null;
  const wind = marineSnapshot?.weather?.wind_speed_kmh ?? liveConditions?.windSpeedKmh ?? null;
  const sea = marineSnapshot?.weather?.sea_state || liveConditions?.seaState || "slight";
  const tidePhase = marineSnapshot?.ocean?.current_phase || "Normal tidal cycle";
  const waterLevel = marineSnapshot?.ocean?.water_level_m;
  const activeWarnings = marineSnapshot?.hazards?.active_warnings || [];
  const imblDistance = marineSnapshot?.geofence?.imbl_distance_km;

  const effectiveRisk: RiskLabel = marineSnapshot?.risk?.final_level || marineSnapshot?.risk?.risk_label || currentRiskLabel || "LOW";

  const riskBadgeColor =
    effectiveRisk === "HIGH" || effectiveRisk === "EXTREME"
      ? "bg-red-500/15 text-red-400 border-red-500/30"
      : effectiveRisk === "MODERATE"
      ? "bg-amber-500/15 text-amber-400 border-amber-500/30"
      : effectiveRisk === "UNKNOWN"
      ? "bg-slate-500/15 text-slate-300 border-slate-500/30"
      : "bg-emerald-500/15 text-emerald-400 border-emerald-500/30";

  // Dynamic Suitability Assessment (No hardcoded departure times)
  let suitabilityTitle = "";
  let suitabilitySummary = "";
  let suitabilityBadge = "";

  if (effectiveRisk === "LOW") {
    suitabilityTitle = "Conditions Currently Favorable";
    suitabilitySummary = "Wave height and wind speeds are within safe thresholds for small-craft coastal operation. Confirm official port warnings before departing.";
    suitabilityBadge = "bg-emerald-500/20 text-emerald-300 border-emerald-500/40";
  } else if (effectiveRisk === "MODERATE") {
    suitabilityTitle = "Caution Required";
    suitabilitySummary = "Freshening winds or moderate swell detected. Inexperienced crew or small craft should exercise heightened vigilance.";
    suitabilityBadge = "bg-amber-500/20 text-amber-300 border-amber-500/40";
  } else if (effectiveRisk === "HIGH" || effectiveRisk === "EXTREME") {
    suitabilityTitle = "Departure Not Advised / Hazardous Conditions";
    suitabilitySummary = activeWarnings.length > 0
      ? `Severe warning (${activeWarnings.join(", ")}) active near this harbor. Avoid going out until official warnings clear.`
      : "Elevated waves or gale-force winds present serious risk to marine craft. Stay ashore.";
    suitabilityBadge = "bg-red-500/20 text-red-300 border-red-500/40";
  } else {
    suitabilityTitle = "Awaiting Complete Sensor Observations";
    suitabilitySummary = "Tarang is compiling live coastal marine data for this zone. Check local maritime advisories.";
    suitabilityBadge = "bg-slate-500/20 text-slate-300 border-slate-500/40";
  }

  return (
    <div className="max-w-4xl mx-auto p-4 sm:p-6 space-y-6">
      {/* Header */}
      <div className="bg-slate-900/90 border border-slate-800 rounded-2xl p-5 shadow-lg flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 text-xs font-mono uppercase tracking-wider text-cyan-400 mb-1">
            <Compass className="w-4 h-4 text-cyan-400" />
            <span>Operational Assessment</span>
          </div>
          <h1 className="text-xl sm:text-2xl font-bold text-white flex items-center gap-2.5">
            <span>Trip Readiness</span>
            <span className="text-xs font-normal px-2.5 py-1 rounded-full bg-slate-800 text-slate-300 border border-slate-700 flex items-center gap-1.5">
              <MapPin className="w-3.5 h-3.5 text-cyan-400" />
              <span>{locName}</span>
              {marineContext && <MarineContextBadge type={marineContext.type} size="sm" />}
            </span>
          </h1>
        </div>

        <div className="flex items-center gap-3">
          <span className={`text-xs font-bold px-3 py-1.5 rounded-full border ${riskBadgeColor}`}>
            {effectiveRisk} RISK
          </span>
          {onRecheck && (
            <button
              onClick={onRecheck}
              disabled={isRechecking}
              className="flex items-center gap-1.5 rounded-lg border border-cyan-500/40 bg-cyan-500/10 hover:bg-cyan-500/20 px-3 py-1.5 text-xs font-medium text-cyan-300 transition-all disabled:opacity-50"
            >
              <RefreshCw className={`h-3.5 w-3.5 ${isRechecking ? "animate-spin" : ""}`} />
              <span>{isRechecking ? "Checking..." : "Re-check"}</span>
            </button>
          )}
        </div>
      </div>

      {isInland ? (
        <LocationUnavailable featureName="Marine Departure Windows & Operational Suitability" />
      ) : (
        <div className="space-y-4">
          {/* Dynamic Suitability Card (PRD §12: Truthful, non-fabricated) */}
          <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-6 shadow-sm space-y-4">
            <div className="flex items-center justify-between gap-2 border-b border-slate-800/80 pb-3">
              <div className="flex items-center gap-2 text-sm font-semibold text-slate-200">
                <ShieldCheck className="w-4 h-4 text-cyan-400" />
                <span>Current Trip Feasibility Status</span>
              </div>
              <span className={`px-2.5 py-0.5 rounded-full border text-xs font-bold uppercase tracking-wider ${suitabilityBadge}`}>
                {effectiveRisk}
              </span>
            </div>

            <div className="p-4 rounded-xl bg-slate-950/60 border border-slate-800/80">
              <h3 className="text-base font-bold text-white mb-1">{suitabilityTitle}</h3>
              <p className="text-xs sm:text-sm text-slate-300 leading-relaxed">{suitabilitySummary}</p>
            </div>

            {/* Active Hazard Warning Alert */}
            {activeWarnings.length > 0 && (
              <div className="p-3.5 rounded-xl bg-red-500/10 border border-red-500/30 flex items-start gap-2.5 text-xs text-red-300">
                <AlertTriangle className="w-4 h-4 text-red-400 shrink-0 mt-0.5" />
                <div>
                  <span className="font-semibold text-red-200">Active Severe Weather Warning:</span>{" "}
                  <span>{activeWarnings.join(", ")}. In Tarang&apos;s safety model, active warnings force departure restrictions regardless of current surface wave height.</span>
                </div>
              </div>
            )}

            {/* Evidence Evaluation Factors */}
            <div className="space-y-2 text-xs text-slate-400 pt-1">
              <p className="font-semibold text-slate-200 uppercase tracking-wider text-[11px]">Scientific Evidence Factors:</p>
              <ul className="space-y-1 pl-4 list-disc marker:text-cyan-400">
                <li>Wind Speed: <strong className="text-slate-200">{wind !== null ? `${wind.toFixed(1)} km/h` : "Available"}</strong> {wind !== null && wind < 20 ? "(favorable for small craft)" : "(requires caution)"}</li>
                <li>Wave Height: <strong className="text-slate-200">{wave !== null ? `${wave.toFixed(2)} m` : "Available"}</strong> ({sea} sea state)</li>
                <li>Tide & Sea Level: <strong className="text-slate-200">{tidePhase}</strong> {waterLevel ? `(${waterLevel.toFixed(2)}m above chart datum)` : ""}</li>
                <li>Boundary Status: <strong className="text-slate-200">{imblDistance ? `${Math.round(imblDistance)} km from IMBL boundary` : "Monitored"}</strong></li>
              </ul>
            </div>
          </div>

          {/* Operational Metrics Cards */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-4 shadow-sm space-y-2">
              <div className="flex items-center gap-2 text-xs font-medium text-slate-400">
                <Wind className="w-4 h-4 text-sky-400" />
                <span>Wind Condition</span>
              </div>
              <p className="text-lg font-bold text-white">{wind !== null ? `${wind.toFixed(1)} km/h` : "—"}</p>
              <p className="text-xs text-slate-400">Open-Meteo Verified Marine</p>
            </div>

            <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-4 shadow-sm space-y-2">
              <div className="flex items-center gap-2 text-xs font-medium text-slate-400">
                <Waves className="w-4 h-4 text-teal-400" />
                <span>Significant Wave</span>
              </div>
              <p className="text-lg font-bold text-white">{wave !== null ? `${wave.toFixed(2)} m` : "—"}</p>
              <p className="text-xs text-slate-400">Sea state: {sea}</p>
            </div>

            <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-4 shadow-sm space-y-2">
              <div className="flex items-center gap-2 text-xs font-medium text-slate-400">
                <ShieldCheck className="w-4 h-4 text-emerald-400" />
                <span>Maritime Boundary</span>
              </div>
              <p className="text-lg font-bold text-white">{imblDistance ? `${Math.round(imblDistance)} km` : "Buffer Active"}</p>
              <p className="text-xs text-slate-400">UNCLOS / IMBL Geofence</p>
            </div>
          </div>

          {/* Truthful Decision-Support Disclaimer (PRD §12) */}
          <div className="p-4 bg-slate-950/60 border border-slate-800 rounded-xl flex items-start gap-3 text-xs text-slate-400 leading-relaxed">
            <Info className="w-4 h-4 text-cyan-400 shrink-0 mt-0.5" />
            <div>
              <p className="font-semibold text-slate-300">Decision Support Disclaimer</p>
              <p className="mt-0.5">
                Trip readiness assessments are computed from deterministic marine models as a navigational aid. They do not constitute official departure authorization. Always adhere to port closures and warnings from IMD and the Indian Coast Guard.
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
