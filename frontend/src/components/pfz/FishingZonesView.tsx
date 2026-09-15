"use client";

import React, { useState, useEffect, useCallback } from "react";
import {
  Fish,
  MapPin,
  ExternalLink,
  Info,
  RefreshCw,
  ShieldAlert,
  Compass,
  Layers,
  Sparkles,
  ArrowUpRight,
  Thermometer,
} from "lucide-react";
import { MapGeoJSON, LocationStatus, LanguageCode, MarineSnapshot } from "@/lib/types";
import { useLocation } from "@/lib/locationContext";
import { LocationUnavailable } from "@/components/location/LocationUnavailable";
import { MarineContextBadge } from "@/components/location/MarineContextBadge";
import { fetchPfzZonesApi } from "@/lib/api";

interface Props {
  geoJson?: MapGeoJSON | null;
  locationName: string;
  locationStatus: LocationStatus;
  pfzData?: any;
  onSelectZoneOnMap?: (zoneId: string) => void;
  onNavigateToMap: () => void;
  onPfzLoaded?: (features: any[]) => void;
  onNavigateToChat?: () => void;
  language?: LanguageCode;
  marineSnapshot?: MarineSnapshot | null;
}

export const FishingZonesView: React.FC<Props> = ({
  geoJson,
  locationName,
  locationStatus,
  pfzData,
  onSelectZoneOnMap,
  onNavigateToMap,
  onPfzLoaded,
  onNavigateToChat,
  marineSnapshot,
}) => {
  const { selectedLocation, marineContext } = useLocation();
  const effectiveLocationName =
    selectedLocation?.name || marineSnapshot?.location.name || locationName || "Coastal Waters";
  const isExplicitlyCoastal =
    marineContext?.type === "coastal" ||
    marineContext?.type === "offshore" ||
    marineContext?.is_coastal === true;

  const [apiIsInland, setApiIsInland] = useState<boolean>(false);
  const isInland = !isExplicitlyCoastal && (marineContext?.type === "inland" || apiIsInland);

  const [fetchedFeatures, setFetchedFeatures] = useState<any[]>([]);
  const [isLoadingZones, setIsLoadingZones] = useState<boolean>(false);
  const [fetchError, setFetchError] = useState<string | null>(null);

  // Check if geoJson already contains active PFZ features
  const geoJsonZones =
    geoJson?.features?.filter(
      (f) => f.properties?.feature_type === "pfz_zone" || f.properties?.type === "pfz"
    ) || [];

  const loadZones = useCallback(async () => {
    if (!selectedLocation) return;
    if (marineContext?.type === "inland" && !isExplicitlyCoastal) {
      setApiIsInland(true);
      return;
    }
    setIsLoadingZones(true);
    setFetchError(null);
    try {
      const res = await fetchPfzZonesApi(
        selectedLocation.lat,
        selectedLocation.lon,
        selectedLocation.name
      );
      if (res && (res.status === "inland" || res.is_coastal === false)) {
        setApiIsInland(true);
        setFetchedFeatures([]);
      } else if (res && res.features && res.features.length > 0) {
        setApiIsInland(false);
        setFetchedFeatures(res.features);
        if (onPfzLoaded) {
          onPfzLoaded(res.features);
        }
      } else {
        setApiIsInland(false);
        setFetchedFeatures([]);
      }
    } catch (err: any) {
      console.warn("[FishingZonesView] Error loading PFZ data:", err);
      setFetchError("Unable to connect to satellite ocean color feed");
    } finally {
      setIsLoadingZones(false);
    }
  }, [selectedLocation, marineContext, isExplicitlyCoastal, onPfzLoaded]);

  // Automatically fetch PFZ zones if geoJson has no zones or when location changes
  useEffect(() => {
    setApiIsInland(false);
    if (!selectedLocation) return;
    if (marineContext?.type === "inland" && !isExplicitlyCoastal) return;
    if (geoJsonZones.length > 0) {
      setFetchedFeatures(geoJsonZones);
      return;
    }
    loadZones();
  }, [selectedLocation?.lat, selectedLocation?.lon, selectedLocation?.name, isExplicitlyCoastal]);

  const rawZones = geoJsonZones.length > 0 ? geoJsonZones : fetchedFeatures;

  const zones = rawZones.map((f, idx) => {
    const p = f.properties || {};
    const coords = f.geometry?.coordinates || [0, 0];
    const chl = Number(p.chlorophyll_mg_m3 || p.chl || 1.2);
    const dist = p.distance_km != null ? Math.round(Number(p.distance_km)) : 15 + idx * 12;

    let indicatorLevel = "Moderate Chlorophyll Density";
    let indicatorBadge = "bg-teal-50 text-teal-800 border-teal-200";
    let indicatorBarColor = "bg-teal-500";
    if (chl >= 1.5) {
      indicatorLevel = "Elevated Productivity Indicator";
      indicatorBadge = "bg-emerald-50 text-emerald-800 border-emerald-200";
      indicatorBarColor = "bg-emerald-500";
    } else if (chl < 0.8) {
      indicatorLevel = "Low Chlorophyll Signature";
      indicatorBadge = "bg-slate-50 text-slate-700 border-slate-200";
      indicatorBarColor = "bg-slate-400";
    }

    // Gauge percentage for 0.0 to 2.5 mg/m³
    const gaugePct = Math.min(100, Math.max(8, Math.round((chl / 2.5) * 100)));

    return {
      id: p.zone_id || `PFZ-ZON-${idx + 1}`,
      name: p.name || `Biological Indicator Zone ${String.fromCharCode(65 + idx)}`,
      distanceKm: dist,
      lat: coords[1],
      lon: coords[0],
      chl: chl.toFixed(2),
      chlNum: chl,
      gaugePct,
      indicatorLevel,
      indicatorBadge,
      indicatorBarColor,
      source: p.source || "INCOIS Oceansat-2 Climatology",
      description: p.description,
    };
  });

  // Calculate high-level summary metrics
  const nearestKm = zones.length > 0 ? Math.min(...zones.map((z) => z.distanceKm)) : null;
  const avgChl =
    zones.length > 0
      ? (zones.reduce((sum, z) => sum + z.chlNum, 0) / zones.length).toFixed(2)
      : null;

  return (
    <div className="max-w-4xl mx-auto p-4 sm:p-6 space-y-6">
      {/* Editorial Header */}
      <div className="bg-[var(--surface)] border border-[var(--border)] rounded-2xl p-5 sm:p-6 shadow-xs flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 text-xs font-mono-data uppercase tracking-wider text-[var(--current)] mb-1.5 font-medium">
            <span className="flex h-2 w-2 rounded-full bg-[var(--current)]" />
            <Fish className="w-3.5 h-3.5 text-[var(--current)]" />
            <span>INCOIS Oceansat-2 Observation Feed</span>
          </div>

          <h1 className="text-2xl sm:text-3xl font-serif-display text-[var(--ink)] font-normal tracking-tight flex flex-wrap items-center gap-2.5">
            <span>Potential Fishing Zones (PFZ)</span>
            <span className="text-xs font-sans font-normal px-2.5 py-1 rounded-full bg-[var(--surface-muted)] text-[var(--ink-muted)] border border-[var(--border)] inline-flex items-center gap-1.5">
              <MapPin className="w-3.5 h-3.5 text-[var(--current)]" />
              <span className="font-medium text-[var(--ink)]">{effectiveLocationName}</span>
              {marineContext && <MarineContextBadge type={marineContext.type} size="sm" />}
            </span>
          </h1>

          <p className="text-xs text-[var(--ink-muted)] mt-1 max-w-xl leading-relaxed">
            Satellite chlorophyll-a concentration indicators offshore to identify high-productivity ocean fronts.
          </p>
        </div>

        {/* Action Controls */}
        <div className="flex items-center gap-2 shrink-0">
          <button
            type="button"
            onClick={loadZones}
            disabled={isLoadingZones}
            className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-[var(--surface-muted)] hover:bg-[var(--foam)] text-[var(--ink)] text-xs font-medium transition-all border border-[var(--border)] cursor-pointer disabled:opacity-50 shadow-2xs"
            title="Refresh satellite chlorophyll data"
          >
            <RefreshCw className={`w-3.5 h-3.5 text-[var(--current)] ${isLoadingZones ? "animate-spin" : ""}`} />
            <span>{isLoadingZones ? "Updating..." : "Refresh"}</span>
          </button>

          <button
            type="button"
            onClick={onNavigateToMap}
            className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-[var(--current)] hover:bg-[var(--current-hover)] text-white text-xs font-medium transition-all shadow-xs cursor-pointer"
          >
            <span>View on Marine Map</span>
            <ExternalLink className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Case 1: Inland Location (PRD §11 & §53) */}
      {isInland ? (
        <LocationUnavailable
          featureName="Potential Fishing Zones (PFZ) & Chlorophyll Indicators"
          onOpenMapPicker={onNavigateToMap}
        />
      ) : isLoadingZones && zones.length === 0 ? (
        /* Case 2: Loading State */
        <div className="bg-[var(--surface)] border border-[var(--border)] rounded-2xl p-12 text-center space-y-4 shadow-xs">
          <div className="w-14 h-14 rounded-full bg-[var(--foam)] text-[var(--current)] border border-[var(--current)]/20 flex items-center justify-center mx-auto animate-pulse">
            <Fish className="w-7 h-7 animate-bounce" />
          </div>
          <div>
            <h2 className="text-lg font-serif-display text-[var(--ink)] font-semibold">
              Retrieving Satellite Ocean Color Observations...
            </h2>
            <p className="text-xs sm:text-sm text-[var(--ink-muted)] max-w-md mx-auto mt-1 leading-relaxed">
              Polling INCOIS Oceansat-2 ERDDAP chlorophyll-a optical sensors offshore from {effectiveLocationName}.
            </p>
          </div>
        </div>
      ) : zones.length === 0 ? (
        /* Case 3: No Zones Found */
        <div className="bg-[var(--surface)] border border-[var(--border)] rounded-2xl p-10 text-center space-y-4 shadow-xs">
          <div className="w-12 h-12 rounded-full bg-[var(--surface-muted)] text-[var(--ink-muted)] border border-[var(--border)] flex items-center justify-center mx-auto">
            <Fish className="w-6 h-6 text-[var(--ink-subtle)]" />
          </div>
          <div>
            <h2 className="text-lg font-serif-display text-[var(--ink)] font-semibold">
              No Satellite Indicator Zones Detected
            </h2>
            <p className="text-xs sm:text-sm text-[var(--ink-muted)] max-w-md mx-auto mt-1 leading-relaxed">
              No elevated chlorophyll biological convergence zones were detected for this coastal sector in the latest satellite pass.
            </p>
          </div>
          <button
            type="button"
            onClick={loadZones}
            className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-[var(--foam)] text-[var(--current)] hover:bg-[var(--foam)]/80 text-xs font-semibold transition-all border border-[var(--current)]/20 cursor-pointer"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            <span>Recheck Satellite Feed</span>
          </button>
        </div>
      ) : (
        /* Case 4: Display Summary Ribbon & Cards Grid */
        <div className="space-y-6">
          {/* Quick Metrics Ribbon */}
          <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-5 gap-3">
            <div className="bg-[var(--surface)] border border-[var(--border)] rounded-xl p-3.5 shadow-2xs">
              <div className="flex items-center gap-1.5 text-xs text-[var(--ink-muted)] mb-1">
                <Compass className="w-3.5 h-3.5 text-[var(--current)]" />
                <span>Nearest Zone</span>
              </div>
              <p className="text-base sm:text-lg font-semibold text-[var(--ink)] font-mono-data">
                ~{nearestKm} km
              </p>
              <p className="text-[11px] text-[var(--ink-subtle)]">Offshore distance</p>
            </div>

            <div className="bg-[var(--surface)] border border-[var(--border)] rounded-xl p-3.5 shadow-2xs">
              <div className="flex items-center gap-1.5 text-xs text-[var(--ink-muted)] mb-1">
                <Sparkles className="w-3.5 h-3.5 text-emerald-600" />
                <span>Avg Chlorophyll</span>
              </div>
              <p className="text-base sm:text-lg font-semibold text-emerald-700 font-mono-data">
                {avgChl} <span className="text-xs font-normal">mg/m³</span>
              </p>
              <p className="text-[11px] text-[var(--ink-subtle)]">Biological indicator</p>
            </div>

            <div className="bg-[var(--surface)] border border-[var(--border)] rounded-xl p-3.5 shadow-2xs">
              <div className="flex items-center gap-1.5 text-xs text-[var(--ink-muted)] mb-1">
                <Layers className="w-3.5 h-3.5 text-[var(--current)]" />
                <span>Detected Zones</span>
              </div>
              <p className="text-base sm:text-lg font-semibold text-[var(--ink)] font-mono-data">
                {zones.length}
              </p>
              <p className="text-[11px] text-[var(--ink-subtle)]">Active candidate zones</p>
            </div>

            {marineSnapshot?.sst?.sst_celsius != null ? (
              <div className="bg-sky-50/60 border border-sky-200 rounded-xl p-3.5 shadow-2xs">
                <div className="flex items-center gap-1.5 text-xs text-sky-800 mb-1">
                  <Thermometer className="w-3.5 h-3.5 text-sky-600" />
                  <span>Sea Temp (SST)</span>
                </div>
                <p className="text-base sm:text-lg font-semibold text-sky-900 font-mono-data">
                  {marineSnapshot.sst.sst_celsius.toFixed(1)}°C
                  {marineSnapshot.sst.sst_anomaly_c != null && (
                    <span className="text-xs ml-1 font-normal text-sky-700">
                      ({marineSnapshot.sst.sst_anomaly_c >= 0 ? "+" : ""}{marineSnapshot.sst.sst_anomaly_c.toFixed(1)}°)
                    </span>
                  )}
                </p>
                <p className="text-[11px] text-sky-700 truncate" title="INCOIS ERDDAP NOAA AVHRR/AMSR SST">
                  INCOIS ERDDAP
                </p>
              </div>
            ) : (
              <div className="bg-[var(--surface)] border border-[var(--border)] rounded-xl p-3.5 shadow-2xs">
                <div className="flex items-center gap-1.5 text-xs text-[var(--ink-muted)] mb-1">
                  <Fish className="w-3.5 h-3.5 text-[var(--dawn)]" />
                  <span>Satellite Source</span>
                </div>
                <p className="text-xs font-semibold text-[var(--ink)] truncate mt-1">
                  Oceansat-2
                </p>
                <p className="text-[11px] text-[var(--ink-subtle)] truncate">INCOIS ERDDAP Proxy</p>
              </div>
            )}

            {marineSnapshot?.sst?.sst_celsius != null && (
              <div className="bg-[var(--surface)] border border-[var(--border)] rounded-xl p-3.5 shadow-2xs">
                <div className="flex items-center gap-1.5 text-xs text-[var(--ink-muted)] mb-1">
                  <Fish className="w-3.5 h-3.5 text-[var(--dawn)]" />
                  <span>Satellite Source</span>
                </div>
                <p className="text-xs font-semibold text-[var(--ink)] truncate mt-1">
                  Oceansat-2 & SST
                </p>
                <p className="text-[11px] text-[var(--ink-subtle)] truncate">INCOIS ERDDAP</p>
              </div>
            )}
          </div>

          {/* PFZ Indicator Cards Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {zones.map((zone) => (
              <div
                key={zone.id}
                className="bg-[var(--surface)] border border-[var(--border)] hover:border-[var(--current)]/50 rounded-2xl p-5 shadow-xs hover:shadow-md transition-all space-y-4 group"
              >
                {/* Card Header */}
                <div className="flex items-start justify-between gap-2 border-b border-[var(--border)] pb-3">
                  <div>
                    <span className="text-[11px] font-mono-data text-[var(--ink-subtle)] tracking-wider">
                      {zone.id}
                    </span>
                    <h3 className="text-base font-semibold text-[var(--ink)] group-hover:text-[var(--current)] transition-colors">
                      {zone.name}
                    </h3>
                  </div>
                  <span
                    className={`text-[11px] px-2.5 py-1 rounded-full border font-medium whitespace-nowrap ${zone.indicatorBadge}`}
                  >
                    {zone.indicatorLevel}
                  </span>
                </div>

                {/* Chlorophyll Visual Spectrum Bar */}
                <div className="space-y-1.5 bg-[var(--surface-muted)] p-3 rounded-xl border border-[var(--border)]/70">
                  <div className="flex items-center justify-between text-xs">
                    <span className="text-[var(--ink-muted)] font-medium">Chlorophyll-a Concentration</span>
                    <span className="font-mono-data font-bold text-[var(--ink)]">
                      {zone.chl} mg/m³
                    </span>
                  </div>
                  <div className="w-full bg-[var(--border)] h-2 rounded-full overflow-hidden">
                    <div
                      className={`h-full ${zone.indicatorBarColor} transition-all duration-500 rounded-full`}
                      style={{ width: `${zone.gaugePct}%` }}
                    />
                  </div>
                  <div className="flex justify-between text-[10px] font-mono-data text-[var(--ink-subtle)]">
                    <span>0.2 (Low)</span>
                    <span>1.0 (Optimal)</span>
                    <span>2.5+ mg/m³ (High)</span>
                  </div>
                </div>

                {/* Detail Data Grid */}
                <div className="grid grid-cols-2 gap-3 text-xs">
                  <div>
                    <span className="text-[var(--ink-subtle)] block text-[11px]">Offshore Distance</span>
                    <p className="font-semibold text-[var(--ink)] flex items-center gap-1 mt-0.5">
                      <Compass className="w-3.5 h-3.5 text-[var(--current)]" />
                      <span>~{zone.distanceKm} km offshore</span>
                    </p>
                  </div>
                  <div>
                    <span className="text-[var(--ink-subtle)] block text-[11px]">Geo Coordinates</span>
                    <p className="font-mono-data text-[11px] text-[var(--ink)] font-medium mt-0.5">
                      {zone.lat.toFixed(2)}°N, {zone.lon.toFixed(2)}°E
                    </p>
                  </div>
                </div>

                {/* Action Buttons */}
                <div className="pt-2 border-t border-[var(--border)]/60 flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => {
                      if (onSelectZoneOnMap) {
                        onSelectZoneOnMap(zone.id);
                      }
                      onNavigateToMap();
                    }}
                    className="flex-1 py-1.5 px-3 rounded-xl border border-[var(--border)] bg-[var(--surface)] hover:bg-[var(--foam)] text-[11px] font-medium text-[var(--ink)] transition-colors flex items-center justify-center gap-1.5 cursor-pointer"
                  >
                    <span>View on Map</span>
                    <ArrowUpRight className="w-3.5 h-3.5 text-[var(--current)]" />
                  </button>

                  {onNavigateToChat && (
                    <button
                      type="button"
                      onClick={onNavigateToChat}
                      className="flex-1 py-1.5 px-3 rounded-xl border border-[var(--dawn)]/30 bg-[var(--dawn)]/10 hover:bg-[var(--dawn)]/20 text-[11px] font-medium text-[var(--dawn-hover)] transition-colors flex items-center justify-center gap-1.5 cursor-pointer"
                    >
                      <ShieldAlert className="w-3.5 h-3.5" />
                      <span>Check Trip Safety</span>
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>

          {/* Scientific Methodology & Honest Disclaimer (PRD §13) */}
          <div className="p-4 sm:p-5 bg-[var(--surface-muted)] border border-[var(--border)] rounded-2xl flex items-start gap-3.5 text-xs text-[var(--ink-muted)] leading-relaxed shadow-2xs">
            <Info className="w-4 h-4 text-[var(--current)] shrink-0 mt-0.5" />
            <div>
              <p className="font-semibold text-[var(--ink)]">
                Satellite Proxy Indicator — Scientific Methodology Note
              </p>
              <p className="mt-1">
                Fishing potential indicators shown above are derived from INCOIS Oceansat-2 satellite ocean color observations (chlorophyll-a concentration gradients). This serves as a scientific proxy indicating zones where biological productivity and plankton concentration may be elevated — <strong>it does not guarantee the presence or catch of fish</strong>, and is not an official INCOIS PFZ advisory. For official government advisories, consult the INCOIS portal at{" "}
                <a
                  href="https://incois.gov.in"
                  target="_blank"
                  rel="noreferrer"
                  className="text-[var(--current)] underline hover:text-[var(--current-hover)]"
                >
                  incois.gov.in
                </a>.
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
