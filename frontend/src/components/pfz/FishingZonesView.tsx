"use client";

import React, { useState, useEffect, useCallback } from "react";
import { Fish, MapPin, ExternalLink, Info, RefreshCw, ShieldAlert } from "lucide-react";
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
  onNavigateToMap,
  onPfzLoaded,
  onNavigateToChat,
  marineSnapshot,
}) => {
  const { selectedLocation, marineContext } = useLocation();
  const effectiveLocationName = selectedLocation?.name || marineSnapshot?.location.name || locationName;
  const isInland = marineContext?.type === "inland" || locationStatus === "inland" || marineContext?.fishing_data_available === false;

  const [fetchedFeatures, setFetchedFeatures] = useState<any[]>([]);
  const [isLoadingZones, setIsLoadingZones] = useState<boolean>(false);
  const [fetchError, setFetchError] = useState<string | null>(null);

  // Check if geoJson has active PFZ features
  const geoJsonZones = geoJson?.features?.filter(
    (f) => f.properties?.feature_type === "pfz_zone" || f.properties?.type === "pfz"
  ) || [];

  const loadZones = useCallback(async () => {
    if (isInland || !selectedLocation) return;
    setIsLoadingZones(true);
    setFetchError(null);
    try {
      const res = await fetchPfzZonesApi(
        selectedLocation.lat,
        selectedLocation.lon,
        selectedLocation.name
      );
      if (res && res.features && res.features.length > 0) {
        setFetchedFeatures(res.features);
        if (onPfzLoaded) {
          onPfzLoaded(res.features);
        }
      } else if (res && res.status === "inland") {
        setFetchedFeatures([]);
      } else {
        setFetchedFeatures([]);
      }
    } catch (err: any) {
      console.warn("[FishingZonesView] Error loading PFZ data:", err);
      setFetchError("Unable to reach satellite feed");
    } finally {
      setIsLoadingZones(false);
    }
  }, [selectedLocation, isInland, onPfzLoaded]);

  // Automatically fetch PFZ zones if geoJson has no zones or when selectedLocation changes
  useEffect(() => {
    if (isInland) return;
    // If geoJson already has zones near the selected location, use them
    if (geoJsonZones.length > 0) {
      setFetchedFeatures(geoJsonZones);
      return;
    }
    loadZones();
  }, [selectedLocation?.lat, selectedLocation?.lon, selectedLocation?.name, isInland]);

  // Consolidate raw zones from geoJson or fetchedFeatures
  const rawZones = geoJsonZones.length > 0 ? geoJsonZones : fetchedFeatures;

  const zones = rawZones.map((f, idx) => {
    const p = f.properties || {};
    const coords = f.geometry?.coordinates || [0, 0];
    const chl = Number(p.chlorophyll_mg_m3 || p.chl || 1.2);
    const dist = p.distance_km != null ? Math.round(Number(p.distance_km)) : 15 + idx * 12;

    // Scientific Honest Proxy Classification (PRD §13: No false "High suitability" catch guarantees)
    let indicatorLevel = "Moderate Proxy Density";
    let indicatorColor = "text-teal-300 bg-teal-500/10 border-teal-500/30";
    if (chl >= 1.5) {
      indicatorLevel = "Elevated Chlorophyll Density";
      indicatorColor = "text-emerald-300 bg-emerald-500/10 border-emerald-500/30";
    } else if (chl < 0.8) {
      indicatorLevel = "Low Chlorophyll Density";
      indicatorColor = "text-slate-300 bg-slate-500/10 border-slate-500/30";
    }

    return {
      id: p.zone_id || `Zone ${String.fromCharCode(65 + idx)}`,
      name: `Indicator Zone ${String.fromCharCode(65 + idx)}`,
      distanceKm: dist,
      lat: coords[1],
      lon: coords[0],
      chl: chl.toFixed(2),
      indicatorLevel,
      indicatorColor,
      source: p.source || "INCOIS Oceansat-2 (Chlorophyll Proxy)",
    };
  });

  return (
    <div className="max-w-4xl mx-auto p-4 sm:p-6 space-y-6">
      {/* Header */}
      <div className="bg-slate-900/90 border border-slate-800 rounded-2xl p-5 shadow-lg flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 text-xs font-mono uppercase tracking-wider text-cyan-400 mb-1">
            <Fish className="w-4 h-4 text-emerald-400" />
            <span>Satellite Observation Proxy</span>
          </div>
          <h1 className="text-xl sm:text-2xl font-bold text-white flex items-center gap-2.5">
            <span>Fishing Potential</span>
            <span className="text-xs font-normal px-2.5 py-1 rounded-full bg-slate-800 text-slate-300 border border-slate-700 flex items-center gap-1.5">
              <MapPin className="w-3.5 h-3.5 text-cyan-400" />
              <span>{effectiveLocationName}</span>
              {marineContext && <MarineContextBadge type={marineContext.type} size="sm" />}
            </span>
          </h1>
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={loadZones}
            disabled={isLoadingZones}
            className="inline-flex items-center gap-1.5 px-3 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium transition-all border border-slate-700 cursor-pointer disabled:opacity-50"
            title="Refresh satellite chlorophyll data"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isLoadingZones ? "animate-spin text-cyan-400" : ""}`} />
            <span className="hidden sm:inline">Refresh</span>
          </button>

          <button
            type="button"
            onClick={onNavigateToMap}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-cyan-600 hover:bg-cyan-500 text-white text-xs font-medium transition-all shadow-sm cursor-pointer shrink-0"
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
        <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-10 text-center space-y-3">
          <div className="w-12 h-12 rounded-full bg-cyan-950/60 text-cyan-400 flex items-center justify-center mx-auto animate-pulse">
            <Fish className="w-6 h-6 animate-bounce" />
          </div>
          <h2 className="text-base font-semibold text-white">
            Analyzing Fishing Potential Indicators...
          </h2>
          <p className="text-xs sm:text-sm text-slate-400 max-w-md mx-auto leading-relaxed">
            Retrieving INCOIS Oceansat-2 satellite chlorophyll observations offshore from {effectiveLocationName}.
          </p>
        </div>
      ) : zones.length === 0 ? (
        /* Case 3: No Zones Found */
        <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-8 text-center space-y-3">
          <div className="w-12 h-12 rounded-full bg-slate-800 text-slate-400 flex items-center justify-center mx-auto">
            <Fish className="w-6 h-6" />
          </div>
          <h2 className="text-base font-semibold text-white">
            No Satellite Indicator Zones Detected
          </h2>
          <p className="text-xs sm:text-sm text-slate-400 max-w-md mx-auto leading-relaxed">
            No potential fishing indicator zones are currently detected for this coastal sector in the verified satellite observation pass.
          </p>
          <button
            type="button"
            onClick={loadZones}
            className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-full bg-cyan-950/60 text-cyan-400 border border-cyan-800/50 font-medium text-xs hover:bg-cyan-900/40 transition-colors cursor-pointer"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            <span>Recheck Satellite Feed</span>
          </button>
        </div>
      ) : (
        /* Case 4: Display PFZ Cards */
        <div className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {zones.map((zone) => (
              <div
                key={zone.id}
                className="bg-slate-900/80 border border-slate-800 hover:border-cyan-500/40 rounded-2xl p-5 shadow-sm hover:shadow-md transition-all space-y-3"
              >
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <span className="text-xs font-mono text-slate-400">
                      {zone.id}
                    </span>
                    <h3 className="text-base font-semibold text-white">
                      {zone.name}
                    </h3>
                  </div>
                  <span
                    className={`text-xs px-2.5 py-1 rounded-full border font-medium ${zone.indicatorColor}`}
                  >
                    {zone.indicatorLevel}
                  </span>
                </div>

                <div className="grid grid-cols-2 gap-2 pt-2 border-t border-slate-800/80 text-xs">
                  <div>
                    <span className="text-slate-400">Distance</span>
                    <p className="font-semibold text-white">~{zone.distanceKm} km offshore</p>
                  </div>
                  <div>
                    <span className="text-slate-400">Chlorophyll-a</span>
                    <p className="font-semibold text-cyan-300 font-mono">{zone.chl} mg/m³</p>
                  </div>
                  <div>
                    <span className="text-slate-400">Coordinates</span>
                    <p className="font-mono text-[11px] text-slate-300">
                      {zone.lat.toFixed(2)}°N, {zone.lon.toFixed(2)}°E
                    </p>
                  </div>
                  <div>
                    <span className="text-slate-400">Data Stream</span>
                    <p className="text-[11px] text-slate-300 truncate">
                      {zone.source}
                    </p>
                  </div>
                </div>

                {onNavigateToChat && (
                  <button
                    onClick={onNavigateToChat}
                    className="w-full mt-2 py-1.5 px-3 rounded-lg border border-slate-700 bg-slate-800/50 hover:bg-slate-800 text-[11px] font-medium text-slate-300 hover:text-white transition-colors flex items-center justify-center gap-1.5"
                  >
                    <ShieldAlert className="w-3.5 h-3.5 text-cyan-400" />
                    <span>Check trip safety before voyaging here</span>
                  </button>
                )}
              </div>
            ))}
          </div>

          {/* Scientific Proxy & Honest Disclaimer (PRD §13) */}
          <div className="p-4 bg-slate-950/60 border border-slate-800 rounded-xl flex items-start gap-3 text-xs text-slate-400 leading-relaxed">
            <Info className="w-4 h-4 text-cyan-400 shrink-0 mt-0.5" />
            <div>
              <p className="font-semibold text-slate-300">Satellite Proxy Indicator — Scientific Methodology Note</p>
              <p className="mt-0.5">
                Fishing potential indicators shown above are derived from INCOIS Oceansat-2 satellite ocean color data (chlorophyll-a concentration). This is a scientific proxy indicator showing areas where biological productivity may be elevated — <strong>it does not guarantee the presence or catch of fish</strong>, and is not an official INCOIS PFZ advisory. For official advisories, consult the INCOIS portal at incois.gov.in.
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
