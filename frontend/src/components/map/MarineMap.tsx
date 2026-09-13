"use client";

import React, { useEffect, useRef, useState } from "react";
import { Layers, Fish, AlertTriangle, Maximize2, HelpCircle } from "lucide-react";
import { ShorelineCompass } from "../illustrations/ShorelineCompass";
import { MapGeoJSON, RiskLabel } from "@/lib/types";

interface Props {
  geoJson?: MapGeoJSON | null;
  riskLabel?: RiskLabel;
  locationName?: string;
  className?: string;
}

export const MarineMap: React.FC<Props> = ({
  geoJson,
  riskLabel = "LOW",
  locationName = "Coastal Waters",
  className = "w-full h-full min-h-[350px]",
}) => {
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapInstanceRef = useRef<any>(null);
  const geoLayerGroupRef = useRef<any>(null);
  const [isMounted, setIsMounted] = useState(false);
  const [isLegendOpen, setIsLegendOpen] = useState(false);
  const [featuresCount, setFeaturesCount] = useState({ pfz: 0, imbl: false, query: false });

  const hasGeoData = Boolean(geoJson && geoJson.features && geoJson.features.length > 0);

  // Guard SSR
  useEffect(() => {
    setIsMounted(true);
  }, []);

  useEffect(() => {
    if (!isMounted || !mapContainerRef.current) return;

    let L: any;

    const initMap = async () => {
      L = (await import("leaflet")).default;

      if (!mapInstanceRef.current && mapContainerRef.current) {
        const map = L.map(mapContainerRef.current, {
          center: [10.5, 78.5],
          zoom: 6,
          zoomControl: true,
          attributionControl: false,
        });

        // Standard OpenStreetMap tiles (Reliable, keyless, zero watermarks)
        L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
          maxZoom: 18,
          subdomains: ["a", "b", "c"],
          attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
        }).addTo(map);

        L.control
          .attribution({
            position: "bottomright",
            prefix: '<span class="text-[9px] text-gray-500">Tarang Marine • INCOIS • OSM</span>',
          })
          .addTo(map);

        const layerGroup = L.layerGroup().addTo(map);
        mapInstanceRef.current = map;
        geoLayerGroupRef.current = layerGroup;
      }

      if (hasGeoData) {
        renderFeatures(L);
      }
    };

    initMap();

    return () => {
      if (mapInstanceRef.current) {
        mapInstanceRef.current.remove();
        mapInstanceRef.current = null;
      }
    };
  }, [isMounted]);

  // Update features whenever geoJson or riskLabel changes
  useEffect(() => {
    if (!mapInstanceRef.current) return;
    import("leaflet").then((leafletModule) => {
      renderFeatures(leafletModule.default);
    });
  }, [geoJson, riskLabel]);

  const renderFeatures = (L: any) => {
    if (!mapInstanceRef.current || !geoLayerGroupRef.current) return;

    const group = geoLayerGroupRef.current;
    group.clearLayers();

    const bounds = L.latLngBounds([]);
    let pfzCount = 0;
    let hasImbl = false;
    let hasQuery = false;

    const riskStroke =
      riskLabel === "HIGH" || riskLabel === "EXTREME"
        ? "#DC2626"
        : riskLabel === "MODERATE"
        ? "#D97706"
        : "#1B8755";

    if (geoJson && geoJson.features && geoJson.features.length > 0) {
      geoJson.features.forEach((feature) => {
        const geom = feature.geometry;
        const props = feature.properties || {};
        const featType = props.feature_type;

        // 1. Query Location Point
        if (featType === "query_point" || props.name === "Query Location") {
          const [lon, lat] = geom.coordinates;
          hasQuery = true;
          bounds.extend([lat, lon]);

          // Coastal safety perimeter circle (20km radius zone)
          L.circle([lat, lon], {
            radius: 20000,
            color: riskStroke,
            weight: 1.5,
            fillColor: riskStroke,
            fillOpacity: 0.08,
            dashArray: "4 4",
          }).addTo(group);

          const pinHtml = `
            <div style="position: relative; display: flex; align-items: center; justify-content: center;">
              <div style="position: absolute; width: 34px; height: 34px; border-radius: 9999px; background: rgba(46, 143, 160, 0.25); animation: ping 2s cubic-bezier(0, 0, 0.2, 1) infinite;"></div>
              <div style="width: 22px; height: 22px; border-radius: 9999px; background: #16242B; border: 2.5px solid #FFFFFF; box-shadow: 0 2px 6px rgba(0,0,0,0.3); display: flex; align-items: center; justify-content: center;">
                <div style="width: 8px; height: 8px; border-radius: 9999px; background: #2E8FA0;"></div>
              </div>
            </div>
          `;
          const queryIcon = L.divIcon({
            html: pinHtml,
            className: "custom-query-pin",
            iconSize: [34, 34],
            iconAnchor: [17, 17],
          });

          L.marker([lat, lon], { icon: queryIcon })
            .bindPopup(`
              <div style="font-family: sans-serif; font-size: 12px; color: #16242B; padding: 2px;">
                <strong style="color: #2E8FA0; font-size: 13px;">📍 ${props.label || locationName}</strong><br/>
                <span style="color: #6B7280; font-size: 11px;">Lat: ${lat.toFixed(4)}°, Lon: ${lon.toFixed(4)}°</span><br/>
                <span style="display: inline-block; margin-top: 4px; padding: 2px 6px; border-radius: 4px; background: #F3F4F6; font-size: 10px; font-weight: 600;">
                  Safety Verdict: ${riskLabel}
                </span>
              </div>
            `)
            .addTo(group);
        }

        // 2. Potential Fishing Zone (PFZ) indicator beacons
        else if (featType === "pfz_zone" || props.type === "pfz") {
          const [lon, lat] = geom.coordinates;
          pfzCount++;
          bounds.extend([lat, lon]);

          const chl = props.chlorophyll_mg_m3 || props.chl || "1.2";
          const dist = props.distance_km != null ? `${Math.round(props.distance_km)} km` : "Nearby";

          const pfzHtml = `
            <div style="display: flex; align-items: center; justify-content: center; width: 24px; height: 24px; background-color: #1B8755; color: white; border: 2px solid white; border-radius: 50%; box-shadow: 0 2px 5px rgba(0,0,0,0.25); font-size: 12px;">
              🐟
            </div>
          `;
          const pfzIcon = L.divIcon({
            html: pfzHtml,
            className: "custom-pfz-pin",
            iconSize: [24, 24],
            iconAnchor: [12, 12],
          });

          L.marker([lat, lon], { icon: pfzIcon })
            .bindPopup(`
              <div style="font-family: sans-serif; font-size: 12px; color: #16242B;">
                <strong style="color: #1B8755;">🐟 PFZ Indicator Zone #${pfzCount}</strong><br/>
                <div style="margin-top: 4px; line-height: 1.4; color: #374151;">
                  • Distance: <b>${dist}</b><br/>
                  • Chlorophyll-a: <b>${typeof chl === "number" ? chl.toFixed(2) : chl} mg/m³</b><br/>
                  • Bearing: <b>${props.bearing_deg || props.bearing || "E"}°</b>
                </div>
                <div style="margin-top: 6px; font-size: 10px; color: #6B7280; border-top: 1px solid #E5E7EB; padding-top: 4px;">
                  Source: INCOIS Oceansat-2 (satellite chlorophyll proxy)
                </div>
              </div>
            `)
            .addTo(group);
        }

        // 3. International Maritime Boundary Line (IMBL)
        else if (featType === "imbl_boundary" || props.type === "boundary" || geom.type === "LineString") {
          hasImbl = true;
          const latLngs = geom.coordinates.map(([lon, lat]: [number, number]) => {
            bounds.extend([lat, lon]);
            return [lat, lon];
          });

          L.polyline(latLngs, {
            color: "#DC2626",
            weight: 2.5,
            dashArray: "6, 6",
            opacity: 0.9,
          })
            .bindPopup(`
              <div style="font-family: sans-serif; font-size: 12px;">
                <strong style="color: #DC2626;">⛔ ${props.name || "India-Sri Lanka IMBL"}</strong><br/>
                <p style="margin-top: 4px; font-size: 11px; color: #4B5563;">
                  International Maritime Boundary Line. Indian fishermen must NOT cross this demarcation line under any circumstances.
                </p>
              </div>
            `)
            .addTo(group);
        }
      });
    }

    setFeaturesCount({ pfz: pfzCount, imbl: hasImbl, query: hasQuery });

    if (bounds.isValid()) {
      mapInstanceRef.current.fitBounds(bounds, { padding: [40, 40], maxZoom: 10 });
    }
  };

  const handleRecenter = async () => {
    if (!mapInstanceRef.current || !geoLayerGroupRef.current) return;
    const L = (await import("leaflet")).default;
    const bounds = L.latLngBounds([]);
    geoLayerGroupRef.current.eachLayer((layer: any) => {
      if (layer.getBounds) bounds.extend(layer.getBounds());
      else if (layer.getLatLng) bounds.extend(layer.getLatLng());
    });
    if (bounds.isValid()) {
      mapInstanceRef.current.fitBounds(bounds, { padding: [40, 40] });
    }
  };

  // ── Active chart state ──
  return (
    <div className={`relative bg-[#E2ECEE] rounded-xl overflow-hidden border border-[var(--border)] shadow-xs flex flex-col ${className}`}>
      {/* Map Control Toolbar */}
      <div className="absolute top-3 left-3 z-[1000] bg-white/90 backdrop-blur-xs border border-[var(--border)] rounded-lg p-2 shadow-xs flex items-center gap-3 text-xs text-[var(--ink)]">
        <div className="flex items-center gap-1.5 font-semibold text-[var(--current)]">
          <Layers className="w-4 h-4" />
          <span>Marine Chart</span>
        </div>

        <div className="h-3.5 w-px bg-[var(--border)]" />

        {/* Dynamic badges */}
        {!hasGeoData ? (
          <span className="text-[11px] text-[var(--ink-muted)]">
            📍 Coastal Waters Overview
          </span>
        ) : (
          <div className="flex items-center gap-2 text-[11px] text-[var(--ink-muted)]">
            {featuresCount.query && (
              <span className="flex items-center gap-1">
                <span className="w-2 h-2 rounded-full bg-[var(--current)]" /> Query Point
              </span>
            )}
            {featuresCount.pfz > 0 && (
              <span className="flex items-center gap-1 font-medium text-[#1B8755]">
                <Fish className="w-3 h-3" /> {featuresCount.pfz} PFZ
              </span>
            )}
            {featuresCount.imbl && (
              <span className="flex items-center gap-1 font-medium text-[#DC2626]">
                <AlertTriangle className="w-3 h-3" /> IMBL Line
              </span>
            )}
          </div>
        )}
      </div>

      {/* Action buttons: Info / Legend Toggle + Recenter (Part 1C.1) */}
      <div className="absolute top-3 right-3 z-[1000] flex items-center gap-1.5">
        <button
          type="button"
          onClick={() => setIsLegendOpen(!isLegendOpen)}
          className={`p-2 bg-white/90 backdrop-blur-xs hover:bg-white text-[var(--ink)] border border-[var(--border)] rounded-lg shadow-xs transition-colors cursor-pointer ${
            isLegendOpen ? "ring-2 ring-[var(--current)]" : ""
          }`}
          title="Toggle map symbols legend"
          aria-label="Toggle map symbols legend"
        >
          <HelpCircle className="w-4 h-4 text-[var(--ink-muted)]" />
        </button>

        <button
          type="button"
          onClick={handleRecenter}
          className="p-2 bg-white/90 backdrop-blur-xs hover:bg-white text-[var(--ink)] border border-[var(--border)] rounded-lg shadow-xs transition-colors cursor-pointer"
          title="Recenter map on active features"
          aria-label="Recenter map"
        >
          <Maximize2 className="w-4 h-4" />
        </button>
      </div>

      {/* Map DOM target */}
      <div ref={mapContainerRef} className="w-full h-full min-h-[350px] z-10" />

      {/* Map Legend Overlay — tucked behind info toggle button */}
      {isLegendOpen && (
        <div className="absolute bottom-3 left-3 z-[1000] bg-white/95 backdrop-blur-xs border border-[var(--border)] rounded-lg p-2.5 shadow-md text-[11px] text-[var(--ink-muted)] space-y-1.5 pointer-events-auto animate-in fade-in duration-150">
          <div className="flex items-center justify-between font-semibold text-[var(--ink)] text-xs mb-1">
            <span>Map Symbols</span>
            <button
              type="button"
              onClick={() => setIsLegendOpen(false)}
              className="text-[var(--ink-subtle)] hover:text-[var(--ink)] text-xs px-1 cursor-pointer"
            >
              ✕
            </button>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-2.5 h-2.5 rounded-full bg-[var(--ink)] border border-white" />
            <span>Target Query Point</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-2.5 h-2.5 rounded-full bg-[#1B8755] border border-white" />
            <span>Potential Fishing Zone (PFZ)</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-5 h-0.5 border-t-2 border-dashed border-[#DC2626]" />
            <span>IMBL Maritime Boundary</span>
          </div>
        </div>
      )}
    </div>
  );
};
