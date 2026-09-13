"use client";

import React from "react";
import { Fish, MapPin, Compass, ExternalLink, AlertCircle, Info } from "lucide-react";
import { MapGeoJSON, LocationStatus, LanguageCode } from "@/lib/types";

interface Props {
  geoJson?: MapGeoJSON | null;
  locationName: string;
  locationStatus: LocationStatus;
  pfzData?: any;
  onSelectZoneOnMap?: (zoneId: string) => void;
  onNavigateToMap: () => void;
  language?: LanguageCode;
}

export const FishingZonesView: React.FC<Props> = ({
  geoJson,
  locationName,
  locationStatus,
  pfzData,
  onNavigateToMap,
}) => {
  // Extract PFZ features from geoJson or pfzData
  const rawZones = geoJson?.features?.filter(
    (f) => f.properties?.feature_type === "pfz_zone" || f.properties?.type === "pfz"
  ) || [];

  const zones = rawZones.map((f, idx) => {
    const p = f.properties || {};
    const coords = f.geometry?.coordinates || [0, 0];
    const chl = Number(p.chlorophyll_mg_m3 || p.chl || 1.2);
    const dist = p.distance_km != null ? Math.round(Number(p.distance_km)) : 15 + idx * 12;

    // Deterministic suitability classification based on chlorophyll-a
    let suitability = "Moderate";
    let suitabilityColor = "text-amber-700 bg-amber-50 border-amber-200";
    if (chl >= 1.5) {
      suitability = "High suitability";
      suitabilityColor = "text-emerald-800 bg-emerald-50 border-emerald-200";
    } else if (chl < 0.8) {
      suitability = "Low suitability";
      suitabilityColor = "text-slate-700 bg-slate-50 border-slate-200";
    } else {
      suitability = "Moderate suitability";
      suitabilityColor = "text-teal-800 bg-teal-50 border-teal-200";
    }

    return {
      id: p.zone_id || `Zone ${String.fromCharCode(65 + idx)}`,
      name: `Indicator Zone ${String.fromCharCode(65 + idx)}`,
      distanceKm: dist,
      lat: coords[1],
      lon: coords[0],
      chl: chl.toFixed(2),
      suitability,
      suitabilityColor,
      source: p.source || "INCOIS Oceansat-2 (Chlorophyll Indicator)",
    };
  });

  return (
    <div className="max-w-4xl mx-auto p-4 sm:p-6 space-y-6">
      {/* Header */}
      <div className="bg-[var(--surface)] border border-[var(--border)] rounded-2xl p-5 shadow-xs flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 text-xs font-mono-data uppercase tracking-wider text-[var(--ink-muted)] mb-1">
            <Fish className="w-4 h-4 text-[#1B8755]" />
            <span>Potential Fishing Zones (PFZ)</span>
          </div>
          <h1 className="text-xl sm:text-2xl font-serif-display text-[var(--ink)] flex items-center gap-2">
            <span>Fishing Zones</span>
            <span className="text-xs font-sans px-2.5 py-0.5 rounded-full bg-[var(--foam)] text-[var(--current)] font-medium border border-[var(--border)]">
              📍 {locationName}
            </span>
          </h1>
        </div>

        <button
          type="button"
          onClick={onNavigateToMap}
          className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-[var(--current)] hover:bg-[var(--current-hover)] text-white text-xs font-medium transition-all shadow-xs cursor-pointer shrink-0"
        >
          <span>View on Marine Map</span>
          <ExternalLink className="w-3.5 h-3.5" />
        </button>
      </div>

      {/* Case 1: Inland Location (PRD §53) */}
      {locationStatus === "inland" ? (
        <div className="bg-[var(--surface)] border border-amber-200 rounded-2xl p-8 text-center space-y-3">
          <div className="w-12 h-12 rounded-full bg-amber-50 text-amber-600 flex items-center justify-center mx-auto">
            <MapPin className="w-6 h-6" />
          </div>
          <h2 className="text-base font-semibold text-[var(--ink)]">
            Inland Location
          </h2>
          <p className="text-xs sm:text-sm text-[var(--ink-muted)] max-w-md mx-auto leading-relaxed">
            Marine fishing zone advisories are not applicable to your current inland location. Please specify or select a coastal harbour to view local fishing zones.
          </p>
        </div>
      ) : zones.length === 0 ? (
        /* Case 2: No Zones Found */
        <div className="bg-[var(--surface)] border border-[var(--border)] rounded-2xl p-8 text-center space-y-3">
          <div className="w-12 h-12 rounded-full bg-[var(--surface-muted)] text-[var(--ink-muted)] flex items-center justify-center mx-auto">
            <Fish className="w-6 h-6" />
          </div>
          <h2 className="text-base font-semibold text-[var(--ink)]">
            No Active Fishing Zones Detected
          </h2>
          <p className="text-xs sm:text-sm text-[var(--ink-muted)] max-w-md mx-auto leading-relaxed">
            No potential fishing zones are currently available for this coastal coordinate in the latest satellite pass.
          </p>
        </div>
      ) : (
        /* Case 3: Display PFZ Cards */
        <div className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {zones.map((zone) => (
              <div
                key={zone.id}
                className="bg-[var(--surface)] border border-[var(--border)] hover:border-[var(--current)]/40 rounded-2xl p-5 shadow-xs hover:shadow-md transition-all space-y-3"
              >
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <span className="text-xs font-mono-data text-[var(--ink-subtle)]">
                      {zone.id}
                    </span>
                    <h3 className="text-base font-semibold text-[var(--ink)]">
                      {zone.name}
                    </h3>
                  </div>
                  <span
                    className={`text-xs px-2.5 py-1 rounded-full border font-medium ${zone.suitabilityColor}`}
                  >
                    {zone.suitability}
                  </span>
                </div>

                <div className="grid grid-cols-2 gap-2 pt-2 border-t border-[var(--border)]/60 text-xs">
                  <div>
                    <span className="text-[var(--ink-subtle)]">Distance</span>
                    <p className="font-semibold text-[var(--ink)]">~{zone.distanceKm} km offshore</p>
                  </div>
                  <div>
                    <span className="text-[var(--ink-subtle)]">Chlorophyll-a</span>
                    <p className="font-semibold text-[var(--ink)]">{zone.chl} mg/m³</p>
                  </div>
                  <div>
                    <span className="text-[var(--ink-subtle)]">Coordinates</span>
                    <p className="font-mono-data text-[11px] text-[var(--ink-muted)]">
                      {zone.lat.toFixed(2)}°N, {zone.lon.toFixed(2)}°E
                    </p>
                  </div>
                  <div>
                    <span className="text-[var(--ink-subtle)]">Data Source</span>
                    <p className="text-[11px] text-[var(--ink-muted)] truncate">
                      INCOIS Oceansat-2
                    </p>
                  </div>
                </div>
              </div>
            ))}
          </div>

          {/* Scientific Proxy Disclosure (PRD §48) */}
          <div className="p-4 bg-[var(--surface-muted)] border border-[var(--border)] rounded-xl flex items-start gap-3 text-xs text-[var(--ink-muted)] leading-relaxed">
            <Info className="w-4 h-4 text-[var(--current)] shrink-0 mt-0.5" />
            <div>
              <p className="font-medium text-[var(--ink)]">PFZ Methodology & Limitation Note</p>
              <p className="mt-0.5">
                Fishing potential indicators shown above are derived from INCOIS Oceansat-2 chlorophyll-a satellite observations. This is a scientific proxy indicator and navigational aid, not a guarantee of catch. Consult official INCOIS advisories at incois.gov.in.
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
