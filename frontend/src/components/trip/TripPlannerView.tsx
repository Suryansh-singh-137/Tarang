"use client";

import React from "react";
import {
  Compass,
  Waves,
  Wind,
  AlertTriangle,
  ShieldCheck,
  Info,
  MapPin,
  RefreshCw,
  ShieldAlert,
  CheckCircle2,
  Anchor,
  Radio,
  ArrowRight,
} from "lucide-react";
import {
  LiveConditionsSummary,
  RiskLabel,
  LocationStatus,
  LanguageCode,
  MarineSnapshot,
} from "@/lib/types";
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
  const locName =
    selectedLocation?.name ||
    marineSnapshot?.location.name ||
    liveConditions?.locationName ||
    "Coastal Waters";
  const isExplicitlyCoastal =
    marineContext?.type === "coastal" ||
    marineContext?.type === "offshore" ||
    marineContext?.is_coastal === true;
  const isInland = !isExplicitlyCoastal && (marineContext?.type === "inland" || locationStatus === "inland");

  // Data resolution prioritizing marineSnapshot
  const wave = marineSnapshot?.weather?.wave_height_m ?? liveConditions?.waveHeightM ?? null;
  const wind = marineSnapshot?.weather?.wind_speed_kmh ?? liveConditions?.windSpeedKmh ?? null;
  const sea = marineSnapshot?.weather?.sea_state || liveConditions?.seaState || "slight";
  const tidePhase = marineSnapshot?.ocean?.current_phase || "Normal tidal cycle";
  const waterLevel = marineSnapshot?.ocean?.water_level_m;
  const activeWarnings = marineSnapshot?.hazards?.active_warnings || [];
  const imblDistance = marineSnapshot?.geofence?.imbl_distance_km;

  const effectiveRisk: RiskLabel =
    marineSnapshot?.risk?.final_level ||
    marineSnapshot?.risk?.risk_label ||
    currentRiskLabel ||
    "LOW";

  // Semantic color styling based on Coastal Dawn / Tarang risk tokens
  const getRiskStyles = (risk: RiskLabel) => {
    switch (risk) {
      case "LOW":
        return {
          pill: "bg-[#EBF7F0] text-[#1B8755] border-[#C3E8D2]",
          card: "bg-[#F7FBF8] border-[#C3E8D2]",
          titleColor: "text-[#1B8755]",
          dot: "bg-[#1B8755]",
        };
      case "MODERATE":
        return {
          pill: "bg-[#FEF3C7] text-[#D97706] border-[#FDE68A]",
          card: "bg-[#FFFDF5] border-[#FDE68A]",
          titleColor: "text-[#B45309]",
          dot: "bg-[#D97706]",
        };
      case "HIGH":
      case "EXTREME":
        return {
          pill: "bg-[#FEE2E2] text-[#DC2626] border-[#FECACA]",
          card: "bg-[#FFF8F8] border-[#FECACA]",
          titleColor: "text-[#DC2626]",
          dot: "bg-[#DC2626]",
        };
      default:
        return {
          pill: "bg-[#F3F4F6] text-[#4B5563] border-[#E5E7EB]",
          card: "bg-[var(--surface-muted)] border-[var(--border)]",
          titleColor: "text-[var(--ink)]",
          dot: "bg-[#6B7280]",
        };
    }
  };

  const riskStyles = getRiskStyles(effectiveRisk);

  // Dynamic suitability guidance
  let suitabilityTitle = "";
  let suitabilitySummary = "";

  if (effectiveRisk === "LOW") {
    suitabilityTitle = "Conditions Currently Favorable for Departure";
    suitabilitySummary =
      "Wave heights and wind speeds are within safe thresholds for small-craft coastal operation. Always verify local harbor master flags and port warnings prior to setting sail.";
  } else if (effectiveRisk === "MODERATE") {
    suitabilityTitle = "Caution Required — Moderate Swell or Freshening Winds";
    suitabilitySummary =
      "Freshening wind speeds or choppy seas observed. Inexperienced crew or small non-motorized craft should exercise heightened vigilance and remain within sight of shore.";
  } else if (effectiveRisk === "HIGH" || effectiveRisk === "EXTREME") {
    suitabilityTitle = "Departure Not Advised — Hazardous Marine Conditions";
    suitabilitySummary =
      activeWarnings.length > 0
        ? `Severe marine warning active (${activeWarnings.join(", ")}). Tarang's safety protocol advises suspending departure until official advisories clear.`
        : "Elevated waves or near-gale winds present significant hazard to small fishing and recreational craft. Recommended action: stay ashore.";
  } else {
    suitabilityTitle = "Awaiting Live Sensor Observations";
    suitabilitySummary =
      "Tarang is gathering real-time telemetry from INCOIS and Open-Meteo marine sensors. Consult port authorities for local status.";
  }

  return (
    <div className="max-w-4xl mx-auto p-4 sm:p-6 space-y-6">
      {/* Editorial Header */}
      <div className="bg-[var(--surface)] border border-[var(--border)] rounded-2xl p-5 sm:p-6 shadow-xs flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 text-xs font-mono-data uppercase tracking-wider text-[var(--current)] mb-1.5 font-medium">
            <span className="flex h-2 w-2 rounded-full bg-[var(--current)]" />
            <Compass className="w-3.5 h-3.5 text-[var(--current)]" />
            <span>Operational Marine Assessment</span>
          </div>

          <h1 className="text-2xl sm:text-3xl font-serif-display text-[var(--ink)] font-normal tracking-tight flex flex-wrap items-center gap-2.5">
            <span>Trip Readiness & Marine Planner</span>
            <span className="text-xs font-sans font-normal px-2.5 py-1 rounded-full bg-[var(--surface-muted)] text-[var(--ink-muted)] border border-[var(--border)] inline-flex items-center gap-1.5">
              <MapPin className="w-3.5 h-3.5 text-[var(--current)]" />
              <span className="font-medium text-[var(--ink)]">{locName}</span>
              {marineContext && <MarineContextBadge type={marineContext.type} size="sm" />}
            </span>
          </h1>

          <p className="text-xs text-[var(--ink-muted)] mt-1 max-w-xl leading-relaxed">
            Real-time weather window evaluation, wave thresholds, and pre-departure navigational safety checks.
          </p>
        </div>

        {/* Risk Badge & Refresh */}
        <div className="flex items-center gap-2.5 shrink-0">
          <span
            className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full border text-xs font-bold tracking-wide ${riskStyles.pill}`}
          >
            <span className={`w-2 h-2 rounded-full ${riskStyles.dot}`} />
            <span>{effectiveRisk} RISK</span>
          </span>

          {onRecheck && (
            <button
              type="button"
              onClick={onRecheck}
              disabled={isRechecking}
              className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl bg-[var(--surface-muted)] hover:bg-[var(--foam)] text-[var(--ink)] text-xs font-medium transition-all border border-[var(--border)] cursor-pointer disabled:opacity-50 shadow-2xs"
            >
              <RefreshCw className={`w-3.5 h-3.5 text-[var(--current)] ${isRechecking ? "animate-spin" : ""}`} />
              <span>{isRechecking ? "Checking..." : "Recheck"}</span>
            </button>
          )}
        </div>
      </div>

      {isInland ? (
        <LocationUnavailable featureName="Marine Departure Windows & Operational Suitability" />
      ) : (
        <div className="space-y-6">
          {/* Dynamic Suitability Verdict Banner */}
          <div className={`rounded-2xl p-5 sm:p-6 border shadow-xs transition-all space-y-3 ${riskStyles.card}`}>
            <div className="flex items-start justify-between gap-3">
              <div className="flex items-center gap-2">
                <ShieldCheck className={`w-5 h-5 ${riskStyles.titleColor}`} />
                <span className="font-mono-data text-xs uppercase tracking-wider text-[var(--ink-subtle)] font-medium">
                  Departure Feasibility Status
                </span>
              </div>
              <span className={`px-2.5 py-0.5 rounded-full border text-[11px] font-bold uppercase tracking-wider ${riskStyles.pill}`}>
                {effectiveRisk} Verdict
              </span>
            </div>

            <h3 className={`text-lg sm:text-xl font-serif-display font-semibold ${riskStyles.titleColor}`}>
              {suitabilityTitle}
            </h3>

            <p className="text-xs sm:text-sm text-[var(--ink)] leading-relaxed max-w-3xl">
              {suitabilitySummary}
            </p>

            {/* Active Hazard Warning Notice if present */}
            {activeWarnings.length > 0 && (
              <div className="mt-3 p-3.5 rounded-xl bg-[#FEE2E2] border border-[#FECACA] flex items-start gap-2.5 text-xs text-[#991B1B]">
                <AlertTriangle className="w-4 h-4 text-[#DC2626] shrink-0 mt-0.5" />
                <div>
                  <span className="font-semibold">Active Severe Meteorological Advisory:</span>{" "}
                  <span>
                    {activeWarnings.join(", ")}. In accordance with coastal maritime protocols, official warnings take precedence over localized surface measurements.
                  </span>
                </div>
              </div>
            )}
          </div>

          {/* Core Marine Conditions Matrix (4 Editorial Cards) */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {/* Wave & Swell */}
            <div className="bg-[var(--surface)] border border-[var(--border)] hover:border-[var(--current)]/40 rounded-2xl p-4 shadow-xs hover:shadow-sm transition-all space-y-2">
              <div className="flex items-center justify-between text-xs text-[var(--ink-muted)]">
                <span className="font-medium">Significant Wave</span>
                <Waves className="w-4 h-4 text-[var(--current)]" />
              </div>
              <p className="text-2xl font-serif-display font-semibold text-[var(--ink)] font-mono-data">
                {wave !== null ? `${wave.toFixed(2)}` : "—"} <span className="text-xs font-sans font-normal text-[var(--ink-muted)]">m</span>
              </p>
              <div className="flex items-center justify-between text-[11px] pt-1 border-t border-[var(--border)]">
                <span className="text-[var(--ink-subtle)]">Sea state:</span>
                <span className="font-medium text-[var(--ink)] capitalize">{sea}</span>
              </div>
            </div>

            {/* Wind Speed */}
            <div className="bg-[var(--surface)] border border-[var(--border)] hover:border-[var(--current)]/40 rounded-2xl p-4 shadow-xs hover:shadow-sm transition-all space-y-2">
              <div className="flex items-center justify-between text-xs text-[var(--ink-muted)]">
                <span className="font-medium">Surface Wind</span>
                <Wind className="w-4 h-4 text-[var(--dawn)]" />
              </div>
              <p className="text-2xl font-serif-display font-semibold text-[var(--ink)] font-mono-data">
                {wind !== null ? `${wind.toFixed(1)}` : "—"} <span className="text-xs font-sans font-normal text-[var(--ink-muted)]">km/h</span>
              </p>
              <div className="flex items-center justify-between text-[11px] pt-1 border-t border-[var(--border)]">
                <span className="text-[var(--ink-subtle)]">Breeze category:</span>
                <span className="font-medium text-[var(--ink)]">
                  {wind !== null && wind < 20 ? "Gentle Breeze" : wind !== null && wind < 38 ? "Moderate Wind" : "Strong Wind"}
                </span>
              </div>
            </div>

            {/* Tide & Ocean Level */}
            <div className="bg-[var(--surface)] border border-[var(--border)] hover:border-[var(--current)]/40 rounded-2xl p-4 shadow-xs hover:shadow-sm transition-all space-y-2">
              <div className="flex items-center justify-between text-xs text-[var(--ink-muted)]">
                <span className="font-medium">Tidal Phase</span>
                <Anchor className="w-4 h-4 text-[var(--current)]" />
              </div>
              <p className="text-base font-semibold text-[var(--ink)] truncate pt-1">
                {tidePhase}
              </p>
              <div className="flex items-center justify-between text-[11px] pt-1 border-t border-[var(--border)]">
                <span className="text-[var(--ink-subtle)]">Water level:</span>
                <span className="font-mono-data font-medium text-[var(--ink)]">
                  {waterLevel ? `${waterLevel.toFixed(2)} m` : "Chart Datum"}
                </span>
              </div>
            </div>

            {/* Maritime Boundary / Geofence */}
            <div className="bg-[var(--surface)] border border-[var(--border)] hover:border-[var(--current)]/40 rounded-2xl p-4 shadow-xs hover:shadow-sm transition-all space-y-2">
              <div className="flex items-center justify-between text-xs text-[var(--ink-muted)]">
                <span className="font-medium">Boundary Geofence</span>
                <ShieldCheck className="w-4 h-4 text-emerald-600" />
              </div>
              <p className="text-2xl font-serif-display font-semibold text-[var(--ink)] font-mono-data">
                {imblDistance ? `${Math.round(imblDistance)}` : "Buffer"} <span className="text-xs font-sans font-normal text-[var(--ink-muted)]">km</span>
              </p>
              <div className="flex items-center justify-between text-[11px] pt-1 border-t border-[var(--border)]">
                <span className="text-[var(--ink-subtle)]">Status:</span>
                <span className="font-medium text-emerald-700">UNCLOS Compliant</span>
              </div>
            </div>
          </div>

          {/* Pre-Voyage Safety Checklist & Advisory Action */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {/* Checklist Card */}
            <div className="md:col-span-2 bg-[var(--surface)] border border-[var(--border)] rounded-2xl p-5 shadow-xs space-y-3">
              <div className="flex items-center justify-between border-b border-[var(--border)] pb-2.5">
                <div className="flex items-center gap-2">
                  <CheckCircle2 className="w-4 h-4 text-[var(--current)]" />
                  <h4 className="text-sm font-semibold text-[var(--ink)]">
                    Pre-Departure Standard Safety Protocol
                  </h4>
                </div>
                <span className="text-[11px] font-mono-data text-[var(--ink-subtle)]">
                  STANDARD CHECKLIST
                </span>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-1 text-xs">
                <div className="flex items-start gap-2 p-2.5 rounded-xl bg-[var(--surface-muted)] border border-[var(--border)]/60">
                  <Radio className="w-4 h-4 text-[var(--current)] shrink-0 mt-0.5" />
                  <div>
                    <span className="font-medium text-[var(--ink)]">VHF Marine Radio</span>
                    <p className="text-[11px] text-[var(--ink-muted)] mt-0.5">Maintain continuous monitoring on International Distress Channel 16.</p>
                  </div>
                </div>

                <div className="flex items-start gap-2 p-2.5 rounded-xl bg-[var(--surface-muted)] border border-[var(--border)]/60">
                  <ShieldCheck className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
                  <div>
                    <span className="font-medium text-[var(--ink)]">Personal Flotation Devices</span>
                    <p className="text-[11px] text-[var(--ink-muted)] mt-0.5">Ensure verified PFDs for all crew members before departure.</p>
                  </div>
                </div>

                <div className="flex items-start gap-2 p-2.5 rounded-xl bg-[var(--surface-muted)] border border-[var(--border)]/60">
                  <Compass className="w-4 h-4 text-[var(--dawn)] shrink-0 mt-0.5" />
                  <div>
                    <span className="font-medium text-[var(--ink)]">IMBL Geofence Awareness</span>
                    <p className="text-[11px] text-[var(--ink-muted)] mt-0.5">Remain well within maritime boundary buffer limits at all times.</p>
                  </div>
                </div>

                <div className="flex items-start gap-2 p-2.5 rounded-xl bg-[var(--surface-muted)] border border-[var(--border)]/60">
                  <Waves className="w-4 h-4 text-[var(--current)] shrink-0 mt-0.5" />
                  <div>
                    <span className="font-medium text-[var(--ink)]">Forecast Return Window</span>
                    <p className="text-[11px] text-[var(--ink-muted)] mt-0.5">Plan return voyage well before evening swell increases.</p>
                  </div>
                </div>
              </div>
            </div>

            {/* Ask Safety Advisor Card */}
            <div className="bg-[var(--surface-muted)] border border-[var(--border)] rounded-2xl p-5 shadow-xs flex flex-col justify-between space-y-4">
              <div className="space-y-2">
                <div className="w-9 h-9 rounded-xl bg-[var(--foam)] text-[var(--current)] flex items-center justify-center">
                  <ShieldAlert className="w-5 h-5" />
                </div>
                <h4 className="text-base font-serif-display font-semibold text-[var(--ink)]">
                  Need a Personalized Trip Consultation?
                </h4>
                <p className="text-xs text-[var(--ink-muted)] leading-relaxed">
                  Ask Tarang&apos;s AI Marine Safety Advisor for trip clearance, fuel estimates, and optimal voyage timing.
                </p>
              </div>

              <button
                type="button"
                onClick={onNavigateToChat}
                className="w-full py-2.5 px-4 rounded-xl bg-[var(--current)] hover:bg-[var(--current-hover)] text-white text-xs font-semibold transition-all flex items-center justify-center gap-2 shadow-xs cursor-pointer"
              >
                <span>Consult Safety Assistant</span>
                <ArrowRight className="w-4 h-4" />
              </button>
            </div>
          </div>

          {/* Decision Support Disclaimer (PRD §12) */}
          <div className="p-4 sm:p-5 bg-[var(--surface-muted)] border border-[var(--border)] rounded-2xl flex items-start gap-3.5 text-xs text-[var(--ink-muted)] leading-relaxed shadow-2xs">
            <Info className="w-4 h-4 text-[var(--current)] shrink-0 mt-0.5" />
            <div>
              <p className="font-semibold text-[var(--ink)]">
                Navigational Advisory & Decision-Support Notice
              </p>
              <p className="mt-1">
                Trip readiness assessments are computed from deterministic physical marine models and satellite observation telemetry. They serve as an operational decision-support tool and do not constitute official port departure clearance. Master and vessel operators remain solely responsible for vessel safety and must strictly comply with closures or directives issued by the Indian Coast Guard and the India Meteorological Department (IMD).
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
