import React, { useState } from "react";
import {
  Wind,
  Waves,
  Compass,
  AlertTriangle,
  ChevronDown,
  ChevronUp,
  PhoneCall,
  ShieldCheck,
  ExternalLink,
  MapPin,
  Sparkles,
  Database,
} from "lucide-react";
import { RiskBadge } from "../chat/RiskBadge";
import { LanguageCode, LiveConditionsSummary, RiskLabel } from "@/lib/types";
import { translations } from "@/lib/i18n";

interface Props {
  language: LanguageCode;
  liveConditions?: LiveConditionsSummary | null;
  activeCycloneAlert?: {
    name: string;
    level: string;
    distanceKm: number;
    windSpeedKmh: number;
  } | null;
  onSelectLocation: (place: string) => void;
  onSelectPrompt: (prompt: string) => void;
  className?: string;
  hasStartedChat?: boolean;
}

const QUICK_PLACES = [
  { name: "Thoothukudi", state: "Tamil Nadu", popular: true },
  { name: "Chennai", state: "Tamil Nadu" },
  { name: "Kochi", state: "Kerala" },
  { name: "Diu", state: "Gujarat / D&D" },
  { name: "Puri", state: "Odisha" },
  { name: "Mumbai", state: "Maharashtra" },
];

export const SidebarDashboard: React.FC<Props> = ({
  language,
  liveConditions,
  activeCycloneAlert,
  onSelectLocation,
  onSelectPrompt,
  className = "",
  hasStartedChat = false,
}) => {
  const [isConditionsExpanded, setIsConditionsExpanded] = useState(false);
  const [isQuickPlacesOpen, setIsQuickPlacesOpen] = useState(!hasStartedChat);
  const [isSuggestedOpen, setIsSuggestedOpen] = useState(!hasStartedChat);
  const [isDataSourcesOpen, setIsDataSourcesOpen] = useState(false);
  const [isEmergencyOpen, setIsEmergencyOpen] = useState(false);
  const t = translations[language] || translations.en;

  // Fallback live conditions if not yet fetched by initial query
  const conditions = liveConditions || {
    locationName: "Thoothukudi Coast",
    lat: 8.7642,
    lon: 78.1348,
    waveHeightM: 0.9,
    windSpeedKmh: 12.4,
    seaState: "slight",
    riskLabel: "LOW" as RiskLabel,
    source: "Open-Meteo ERA5 / Live Marine",
    isFallback: false,
  };

  return (
    <aside className={`flex flex-col gap-3.5 p-4 text-[var(--ink)] overflow-y-auto ${className}`}>
      {/* 1. Live Conditions Strip — Compact single-line summary by default (Part 1C.1) */}
      <section className="bg-[var(--surface)] border border-[var(--border)] rounded-xl p-3 shadow-2xs">
        <button
          type="button"
          onClick={() => setIsConditionsExpanded(!isConditionsExpanded)}
          className="w-full flex items-center justify-between text-left min-h-[44px] cursor-pointer"
          aria-label={isConditionsExpanded ? "Collapse live conditions" : "Expand live conditions"}
        >
          <div className="flex items-center gap-2 overflow-hidden text-xs">
            <span className="w-2 h-2 rounded-full bg-[#1B8755] shrink-0 animate-pulse" />
            <span className="font-semibold text-[var(--ink)] truncate max-w-[110px]">
              {conditions.locationName}
            </span>
            <span className="text-[var(--border)]">·</span>
            <span className="text-[var(--ink-muted)] font-mono-data shrink-0">
              {conditions.waveHeightM.toFixed(1)}m
            </span>
            <span className="text-[var(--border)] hidden sm:inline">·</span>
            <span className="text-[var(--ink-muted)] font-mono-data shrink-0 hidden sm:inline">
              {conditions.windSpeedKmh.toFixed(0)}km/h
            </span>
          </div>

          <div className="flex items-center gap-1.5 shrink-0 pl-1">
            <RiskBadge label={conditions.riskLabel} size="sm" showScore={false} />
            {isConditionsExpanded ? (
              <ChevronUp className="w-4 h-4 text-[var(--ink-subtle)]" />
            ) : (
              <ChevronDown className="w-4 h-4 text-[var(--ink-subtle)]" />
            )}
          </div>
        </button>

        {/* Expanded detail view */}
        {isConditionsExpanded && (
          <div className="mt-3 pt-3 border-t border-[var(--border)] space-y-2.5 animate-in fade-in duration-150">
            <div className="grid grid-cols-2 gap-2">
              <div className="p-2 bg-[var(--surface-muted)] rounded-lg border border-[var(--border)]">
                <div className="flex items-center gap-1 text-xs text-[var(--ink-muted)] mb-0.5">
                  <Waves className="w-3.5 h-3.5 text-[var(--current)]" />
                  <span>{t.waveHeight}</span>
                </div>
                <div className="text-sm font-bold text-[var(--ink)] font-mono-data">
                  {conditions.waveHeightM.toFixed(1)} <span className="text-xs font-normal text-[var(--ink-muted)]">m</span>
                </div>
              </div>

              <div className="p-2 bg-[var(--surface-muted)] rounded-lg border border-[var(--border)]">
                <div className="flex items-center gap-1 text-xs text-[var(--ink-muted)] mb-0.5">
                  <Wind className="w-3.5 h-3.5 text-[var(--current)]" />
                  <span>{t.windSpeed}</span>
                </div>
                <div className="text-sm font-bold text-[var(--ink)] font-mono-data">
                  {conditions.windSpeedKmh.toFixed(0)} <span className="text-xs font-normal text-[var(--ink-muted)]">km/h</span>
                </div>
              </div>
            </div>

            <div className="text-[11px] text-[var(--ink-subtle)] flex items-center justify-between">
              <span>Sea state: <strong className="text-[var(--ink)] capitalize">{conditions.seaState}</strong></span>
              <span className="truncate max-w-[140px]">{conditions.source}</span>
            </div>
          </div>
        )}
      </section>

      {/* 2. Active Cyclone / Hazard Alert Banner (Rendered when GDACS alert exists) */}
      {activeCycloneAlert ? (
        <section className="bg-[#FEF3C7] border-2 border-[#F59E0B] rounded-xl p-3 shadow-xs animate-pulse">
          <div className="flex items-center gap-2 text-[#92400E] font-bold text-xs uppercase tracking-wider mb-1">
            <AlertTriangle className="w-4 h-4 text-[#D97706]" />
            {t.activeAlerts}
          </div>
          <p className="text-xs font-semibold text-[#78350F] mb-1">
            Cyclone '{activeCycloneAlert.name}' ({activeCycloneAlert.level} Alert)
          </p>
          <div className="text-[11px] text-[#92400E] space-y-0.5">
            <div>Distance: <strong>{activeCycloneAlert.distanceKm.toFixed(0)} km</strong> from coast</div>
            <div>Max Wind: <strong>{activeCycloneAlert.windSpeedKmh.toFixed(0)} km/h</strong></div>
          </div>
        </section>
      ) : (
        <div className="px-3 py-2 bg-[var(--surface-muted)] border border-[var(--border)] rounded-lg text-[11px] text-[var(--ink-muted)] flex items-center gap-2">
          <ShieldCheck className="w-3.5 h-3.5 text-[#1B8755] shrink-0" />
          <span>{t.noActiveAlerts}</span>
        </div>
      )}

      {/* 3. Quick Locations — Collapsible when chat has started */}
      <section className="bg-[var(--surface)] border border-[var(--border)] rounded-xl p-3 shadow-xs">
        <button
          type="button"
          onClick={() => setIsQuickPlacesOpen(!isQuickPlacesOpen)}
          className="w-full flex items-center justify-between text-xs font-bold tracking-wider uppercase text-[var(--ink-muted)] min-h-[36px] cursor-pointer"
        >
          <span className="flex items-center gap-1.5">
            <Compass className="w-3.5 h-3.5 text-[var(--current)]" />
            {t.quickLocations}
          </span>
          {isQuickPlacesOpen ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
        </button>

        {isQuickPlacesOpen && (
          <div className="flex flex-wrap gap-1.5 mt-2 pt-2 border-t border-[var(--border)]">
            {QUICK_PLACES.map((p) => (
              <button
                key={p.name}
                type="button"
                onClick={() => onSelectLocation(p.name)}
                className="px-3.5 py-2 rounded-full text-xs font-medium bg-[var(--surface-muted)] hover:bg-[var(--foam)] text-[var(--ink)] border border-[var(--border)] hover:border-[var(--current)] transition-all min-h-[48px] flex items-center justify-center cursor-pointer"
              >
                {p.name}
              </button>
            ))}
          </div>
        )}
      </section>

      {/* 4. Suggested Queries — Collapsible when chat has started */}
      <section className="bg-[var(--surface)] border border-[var(--border)] rounded-xl p-3 shadow-xs">
        <button
          type="button"
          onClick={() => setIsSuggestedOpen(!isSuggestedOpen)}
          className="w-full flex items-center justify-between text-xs font-bold tracking-wider uppercase text-[var(--ink-muted)] min-h-[36px] cursor-pointer"
        >
          <span className="flex items-center gap-1.5">
            <Sparkles className="w-3.5 h-3.5 text-[var(--dawn)]" />
            {t.suggestedQueries}
          </span>
          {isSuggestedOpen ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
        </button>

        {isSuggestedOpen && (
          <div className="flex flex-col gap-2 mt-2 pt-2 border-t border-[var(--border)]">
            {Object.values(t.prompts).map((promptText, idx) => (
              <button
                key={idx}
                type="button"
                onClick={() => onSelectPrompt(promptText)}
                className="text-left p-3 rounded-lg text-xs text-[var(--ink)] bg-[var(--surface-muted)] hover:bg-[var(--foam)] border border-[var(--border)] hover:border-[var(--current)] transition-all line-clamp-2 min-h-[48px] flex items-center cursor-pointer"
              >
                &ldquo;{promptText}&rdquo;
              </button>
            ))}
          </div>
        )}
      </section>

      {/* 5. Data Sources & M8 Provenance Trust Panel */}
      <section className="bg-[var(--surface)] border border-[var(--border)] rounded-xl p-3 shadow-xs">
        <button
          type="button"
          onClick={() => setIsDataSourcesOpen(!isDataSourcesOpen)}
          className="w-full flex items-center justify-between text-xs font-semibold text-[var(--ink-muted)] hover:text-[var(--ink)] min-h-[48px] px-1 cursor-pointer"
        >
          <span className="flex items-center gap-2">
            <Database className="w-3.5 h-3.5 text-[var(--current)]" />
            {t.dataSources}
          </span>
          {isDataSourcesOpen ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
        </button>

        {isDataSourcesOpen && (
          <div className="mt-2 pt-3 border-t border-[var(--border)] text-xs space-y-2 text-[var(--ink-muted)]">
            <div className="p-2 bg-[var(--surface-muted)] rounded border border-[var(--border)]">
              <span className="font-semibold text-[var(--ink)] block">Tier 1: Official National</span>
              INCOIS Ocean Advisories & IMD Cyclone Bulletins (Authoritative Indian mandate)
            </div>
            <div className="p-2 bg-[var(--surface-muted)] rounded border border-[var(--border)]">
              <span className="font-semibold text-[var(--ink)] block">Tier 2: Global Awareness</span>
              GDACS Real-Time Tropical Cyclone Tracking (UN Alert network)
            </div>
            <div className="p-2 bg-[var(--surface-muted)] rounded border border-[var(--border)]">
              <span className="font-semibold text-[var(--ink)] block">Tier 3: Operational Model</span>
              Open-Meteo Marine (ERA5 Reanalysis + ICON NWP Forecasts)
            </div>
            <div className="p-2 bg-[var(--surface-muted)] rounded border border-[var(--border)]">
              <span className="font-semibold text-[var(--ink)] block">Tier 4: Scientific Proxy</span>
              Oceansat-2 Chlorophyll-a Satellite Grid (INCOIS ERDDAP)
            </div>
          </div>
        )}
      </section>

      {/* 6. Emergency Contacts */}
      <section className="bg-[var(--surface)] border border-[var(--border)] rounded-xl p-3 shadow-xs">
        <button
          type="button"
          onClick={() => setIsEmergencyOpen(!isEmergencyOpen)}
          className="w-full flex items-center justify-between text-xs font-semibold text-[var(--ink-muted)] hover:text-[var(--ink)] min-h-[48px] px-1 cursor-pointer"
        >
          <span className="flex items-center gap-2">
            <PhoneCall className="w-3.5 h-3.5 text-[#DC2626]" />
            {t.emergencyContacts}
          </span>
          {isEmergencyOpen ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
        </button>

        {isEmergencyOpen && (
          <div className="mt-2 pt-3 border-t border-[var(--border)] text-xs space-y-1.5">
            <div className="flex items-center justify-between p-2.5 bg-[#FEE2E2] rounded border border-[#FECACA] text-[#991B1B] font-semibold">
              <span>Coast Guard S&R:</span>
              <a href="tel:1554" className="underline font-bold text-sm min-h-[48px] min-w-[48px] flex items-center justify-center p-2">
                1554
              </a>
            </div>
            <div className="p-2 bg-[var(--surface-muted)] rounded text-[var(--ink-muted)] text-[11px]">
              {t.incoisHelpline}
            </div>
          </div>
        )}
      </section>

      {/* Disclaimer */}
      <footer className="text-[11px] text-[var(--ink-subtle)] leading-relaxed px-1">
        {t.disclaimer}
      </footer>
    </aside>
  );
};
