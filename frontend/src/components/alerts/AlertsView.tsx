import React from "react";
import { AlertTriangle, ShieldCheck, PhoneCall, Radio, Wind, Compass, ExternalLink, Navigation } from "lucide-react";
import { LanguageCode } from "@/lib/types";
import { translations } from "@/lib/i18n";
import { LanguageToggle } from "../common/LanguageToggle";
import { GeofenceEvaluationResult } from "@/lib/api";

interface Props {
  language: LanguageCode;
  onSelectLanguage: (lang: LanguageCode) => void;
  activeCycloneAlert?: {
    name: string;
    level: string;
    distanceKm: number;
    windSpeedKmh: number;
  } | null;
  activeGeofenceBreach?: GeofenceEvaluationResult | null;
  className?: string;
}

export const AlertsView: React.FC<Props> = ({
  language,
  onSelectLanguage,
  activeCycloneAlert,
  activeGeofenceBreach,
  className = "",
}) => {
  const t = translations[language] || translations.en;

  return (
    <div className={`flex-1 flex flex-col p-4 sm:p-6 lg:p-8 max-w-4xl mx-auto w-full overflow-y-auto space-y-6 ${className}`}>
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-[var(--border)]">
        <div>
          <div className="font-mono-data text-[11px] text-[var(--ink-muted)] uppercase tracking-widest mb-1">
            HAZARD & SURVEILLANCE
          </div>
          <h1 className="font-serif-display text-2xl sm:text-3xl text-[var(--ink)] font-normal">
            Coastal Hazard Alerts
          </h1>
        </div>

        {/* Manual Language Toggle */}
        <div className="flex items-center gap-2">
          <span className="text-xs text-[var(--ink-muted)] hidden sm:inline">Language:</span>
          <LanguageToggle currentLanguage={language} onSelectLanguage={onSelectLanguage} />
        </div>
      </div>

      {/* Geofence Breach Card (High Priority) */}
      {activeGeofenceBreach && activeGeofenceBreach.is_breached && (
        <div className="bg-red-50 border-2 border-red-500 rounded-2xl p-5 sm:p-6 shadow-md space-y-4 animate-pulse">
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-2.5 text-red-800 font-bold text-sm sm:text-base uppercase tracking-wider">
              <AlertTriangle className="w-5 h-5 text-red-600 shrink-0" />
              <span>Critical: International Maritime Boundary Breach</span>
            </div>
            <span className="px-2 py-0.5 rounded text-[11px] font-bold bg-red-600 text-white uppercase">
              Foreign Waters
            </span>
          </div>

          <div className="space-y-1.5 text-red-950">
            <h2 className="text-lg sm:text-xl font-bold">
              Boundary Crossed: {activeGeofenceBreach.boundary_name}
            </h2>
            <p className="text-xs sm:text-sm leading-relaxed text-red-800">
              Vessel coordinates indicate you have crossed the international geofence into foreign territorial waters.
              Immediate foreign naval apprehension risk is elevated. Heave to or reverse course immediately.
            </p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 pt-2">
            <div className="p-3 bg-white/90 rounded-xl border border-red-200">
              <span className="text-[11px] text-red-700 block mb-0.5">Penetration Distance</span>
              <span className="text-base font-bold text-red-900 font-mono-data">
                {activeGeofenceBreach.distance_km.toFixed(1)} km
              </span>
            </div>

            <div className="p-3 bg-white/90 rounded-xl border border-red-200">
              <span className="text-[11px] text-red-700 block mb-0.5">Recommended Escape Course</span>
              <span className="text-base font-bold text-red-900 font-mono-data flex items-center gap-1">
                <Navigation className="w-4 h-4 text-red-600 inline" />
                Steer {activeGeofenceBreach.bearing_cardinal} ({Math.round(activeGeofenceBreach.bearing_to_safety)}°)
              </span>
            </div>

            <div className="p-3 bg-white/90 rounded-xl border border-red-200">
              <span className="text-[11px] text-red-700 block mb-0.5">Emergency S&R Call</span>
              <a
                href={`tel:${activeGeofenceBreach.coastguard_number}`}
                className="text-base font-bold text-red-700 hover:underline font-mono-data"
              >
                ICG Toll-Free {activeGeofenceBreach.coastguard_number}
              </a>
            </div>
          </div>
        </div>
      )}

      {/* Primary Alert Section */}
      {activeCycloneAlert ? (
        <div className="bg-[#FEF3C7] border-2 border-[#F59E0B] rounded-2xl p-5 sm:p-6 shadow-sm animate-pulse space-y-4">
          <div className="flex items-center gap-2.5 text-[#92400E] font-bold text-sm sm:text-base uppercase tracking-wider">
            <AlertTriangle className="w-5 h-5 text-[#D97706] shrink-0" />
            <span>Active Tropical Cyclone Advisory ({activeCycloneAlert.level} Alert)</span>
          </div>

          <div className="space-y-2 text-[#78350F]">
            <h2 className="text-lg sm:text-xl font-bold">
              Cyclone &ldquo;{activeCycloneAlert.name}&rdquo;
            </h2>
            <p className="text-xs sm:text-sm leading-relaxed text-[#92400E]">
              GDACS and IMD National Cyclone Warning Centre advisory active for your operational sector. Sea conditions may deteriorate rapidly with severe squally winds and high swell waves.
            </p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 pt-2">
            <div className="p-3 bg-white/70 rounded-xl border border-[#FDE68A]">
              <span className="text-[11px] text-[#92400E] block mb-0.5">Distance from Coast</span>
              <span className="text-base font-bold text-[#78350F] font-mono-data">
                {activeCycloneAlert.distanceKm.toFixed(0)} km
              </span>
            </div>

            <div className="p-3 bg-white/70 rounded-xl border border-[#FDE68A]">
              <span className="text-[11px] text-[#92400E] block mb-0.5">Max Wind Speed</span>
              <span className="text-base font-bold text-[#78350F] font-mono-data">
                {activeCycloneAlert.windSpeedKmh.toFixed(0)} km/h
              </span>
            </div>

            <div className="p-3 bg-white/70 rounded-xl border border-[#FDE68A]">
              <span className="text-[11px] text-[#92400E] block mb-0.5">Alert Level</span>
              <span className="text-base font-bold text-[#DC2626] font-mono-data uppercase">
                {activeCycloneAlert.level}
              </span>
            </div>
          </div>
        </div>
      ) : (
        <div className="bg-[var(--surface)] border border-[var(--border)] rounded-2xl p-6 sm:p-8 flex flex-col sm:flex-row items-center sm:items-start gap-4 text-center sm:text-left shadow-2xs">
          <div className="w-12 h-12 rounded-full bg-[#EBF7F0] border border-[#C3E8D2] flex items-center justify-center text-[#1B8755] shrink-0">
            <ShieldCheck className="w-6 h-6" />
          </div>
          <div className="space-y-1.5">
            <h2 className="text-base sm:text-lg font-semibold text-[var(--ink)]">
              No Active Cyclone Alerts Detected
            </h2>
            <p className="text-xs sm:text-sm text-[var(--ink-muted)] leading-relaxed max-w-xl">
              Global Disaster Alert and Coordination System (GDACS) and IMD regional surveillance report no active tropical cyclones, depressions, or storm surges threatening coastal sectors within 500km.
            </p>
            <div className="pt-2 font-mono-data text-[11px] text-[var(--ink-subtle)] flex items-center gap-2 justify-center sm:justify-start">
              <span>GDACS Real-Time Sync: ACTIVE</span>
              <span>·</span>
              <span>INCOIS Wave Watch: NOMINAL</span>
            </div>
          </div>
        </div>
      )}

      {/* Emergency Contacts & Coastal Services (Part 1C) */}
      <div className="space-y-4 pt-2">
        <h2 className="font-mono-data text-xs uppercase tracking-wider text-[var(--ink-muted)] flex items-center gap-2">
          <PhoneCall className="w-4 h-4 text-[#DC2626]" />
          <span>Coastal Emergency & Search and Rescue (S&R)</span>
        </h2>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {/* Coast Guard S&R */}
          <div className="p-4 bg-[var(--surface)] border border-[var(--border)] rounded-xl flex items-center justify-between shadow-2xs">
            <div>
              <span className="text-xs font-semibold text-[var(--ink)] block">
                Indian Coast Guard (Toll-Free)
              </span>
              <span className="text-[11px] text-[var(--ink-muted)]">
                National Maritime Distress & Search-and-Rescue
              </span>
            </div>
            <a
              href="tel:1554"
              className="px-4 py-2.5 rounded-full bg-[#FEE2E2] hover:bg-[#FECACA] text-[#991B1B] font-bold text-sm font-mono-data border border-[#FECACA] transition-all min-h-[48px] min-w-[48px] flex items-center justify-center cursor-pointer"
              aria-label="Call Coast Guard on 1554"
            >
              1554
            </a>
          </div>

          {/* INCOIS Ocean State Helpline */}
          <div className="p-4 bg-[var(--surface)] border border-[var(--border)] rounded-xl flex items-center justify-between shadow-2xs">
            <div>
              <span className="text-xs font-semibold text-[var(--ink)] block">
                INCOIS Ocean State Helpline
              </span>
              <span className="text-[11px] text-[var(--ink-muted)]">
                High Wave & Ocean Current Information
              </span>
            </div>
            <a
              href="tel:04023895011"
              className="px-3.5 py-2.5 rounded-full bg-[var(--surface-muted)] hover:bg-[var(--foam)] text-[var(--ink)] font-semibold text-xs font-mono-data border border-[var(--border)] transition-all min-h-[48px] flex items-center justify-center cursor-pointer"
              aria-label="Call INCOIS helpline"
            >
              040-23895011
            </a>
          </div>
        </div>
      </div>

      {/* Data Source Provenance Note */}
      <div className="p-4 bg-[var(--surface-muted)] border border-[var(--border)] rounded-xl text-xs text-[var(--ink-muted)] space-y-1">
        <span className="font-semibold text-[var(--ink)] block">Surveillance Mandate</span>
        <p className="leading-relaxed text-[11px]">
          Tarang automatically synthesizes Tier 1 authoritative alerts from India Meteorological Department (IMD) bulletins and United Nations GDACS satellite telemetry. In extreme weather, always prioritize official harbor siren warnings and local district collectorate orders.
        </p>
      </div>
    </div>
  );
};
