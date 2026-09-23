"use client";

/**
 * MarineScalarLayer.tsx
 * ─────────────────────
 * High-performance canvas color field renderer for:
 *  - Air Temperature (°C)
 *  - Sea Surface Temperature (SST, °C)
 *  - Satellite Chlorophyll-a (mg/m³)
 *
 * Employs Inverse Distance Weighting (IDW) interpolation on an offscreen buffer,
 * producing ultra-smooth oceanographic heatmaps matching INCOIS and NOAA standards.
 *
 * Click on ocean gives localized fisherman insights & biological advice.
 */

import React, { useEffect, useState, useRef } from "react";
import { fetchMarineLayerGrid, MarineScalarPoint } from "@/lib/api";

export type MarineScalarType = "temperature" | "sst" | "chlorophyll";

export interface MarineScalarClickInfo {
  lat: number;
  lon: number;
  value: number;
  unit: string;
  layerType: MarineScalarType;
  title: string;
  badgeText: string;
  badgeBg: string;
  badgeColor: string;
  fishermanTip: string;
  scienceNote: string;
  sx: number;
  sy: number;
}

interface MarineScalarLayerProps {
  mapRef: React.RefObject<any>;
  activeLayer: MarineScalarType | null;
  onLayerClick?: (info: MarineScalarClickInfo | null) => void;
}

// ─── Color Palettes ────────────────────────────────────────────────────────────

// Temperature (°C): 18°C -> 38°C
const TEMP_STOPS: [number, [number, number, number]][] = [
  [18, [20, 60, 160]],
  [23, [45, 145, 215]],
  [27, [55, 195, 165]],
  [30, [250, 204, 21]],
  [33, [249, 115, 22]],
  [38, [220, 38, 38]],
];

// SST (°C): 24°C -> 32°C (Optimal Pelagic corridor: 27.5°C - 29.5°C)
const SST_STOPS: [number, [number, number, number]][] = [
  [24, [30, 58, 138]],
  [26.5, [14, 165, 233]],
  [28.0, [16, 185, 129]],
  [29.5, [245, 158, 11]],
  [32, [239, 68, 68]],
];

// Chlorophyll (mg/m³): 0.1 -> 3.5+
const CHL_STOPS: [number, [number, number, number]][] = [
  [0.1, [15, 23, 42]],
  [0.6, [3, 105, 161]],
  [1.4, [13, 148, 136]],
  [2.4, [22, 163, 74]],
  [3.5, [234, 179, 8]],
];

function sampleRgb(val: number, stops: [number, [number, number, number]][]): [number, number, number] {
  const clamped = Math.max(stops[0][0], Math.min(val, stops[stops.length - 1][0]));
  for (let i = 0; i < stops.length - 1; i++) {
    const [v1, c1] = stops[i];
    const [v2, c2] = stops[i + 1];
    if (clamped <= v2) {
      const t = (clamped - v1) / (v2 - v1);
      return [
        (c1[0] + (c2[0] - c1[0]) * t) | 0,
        (c1[1] + (c2[1] - c1[1]) * t) | 0,
        (c1[2] + (c2[2] - c1[2]) * t) | 0,
      ];
    }
  }
  return stops[stops.length - 1][1];
}

function isPeninsularLandPoint(lat: number, lon: number): boolean {
  if (lat < 8.1 || lat > 26.0) return false;
  const westCoastLon = Math.max(72.5, 77.5 - (lat - 8.1) * 0.38);
  const eastCoastLon = Math.min(88.0, 77.8 + (lat - 8.1) * 0.65);
  return lon > (westCoastLon + 0.12) && lon < (eastCoastLon - 0.12);
}

// IDW interpolation
function idwScalar(lat: number, lon: number, pts: MarineScalarPoint[]): number | null {
  if (!pts || !pts.length) return null;
  let valSum = 0, weightSum = 0;
  for (const p of pts) {
    const d2 = (lat - p.lat) ** 2 + (lon - p.lon) ** 2;
    const w = d2 < 1e-8 ? 1e8 : 1 / d2;
    valSum += w * p.value;
    weightSum += w;
  }
  return weightSum > 0 ? valSum / weightSum : null;
}

// Fisherman Advice Generator
function getScalarAdvisory(
  layerType: MarineScalarType,
  value: number
): {
  title: string;
  badgeText: string;
  badgeBg: string;
  badgeColor: string;
  fishermanTip: string;
  scienceNote: string;
} {
  if (layerType === "temperature") {
    if (value > 33) {
      return {
        title: "Air Temperature: High Heat",
        badgeText: "High Heat • Spoilage Alert",
        badgeBg: "#fee2e2",
        badgeColor: "#991b1b",
        fishermanTip: "High ambient heat risks rapid fish spoilage. Maintain 1:1 ice-to-catch ratio and cover holds with wet tarps. Risk of localized squalls.",
        scienceNote: "Open-Meteo ERA5 2m ambient air temperature. Convective thermal currents active.",
      };
    } else if (value >= 27) {
      return {
        title: "Air Temperature: Warm Marine Weather",
        badgeText: "Warm & Humid • Normal Sailing",
        badgeBg: "#fef3c7",
        badgeColor: "#92400e",
        fishermanTip: "Standard coastal fishing temperatures. Keep drinking water on board for crew hydration. Maintain regular icing.",
        scienceNote: "Typical tropical marine boundary layer surface temperature.",
      };
    } else {
      return {
        title: "Air Temperature: Pleasant / Mild",
        badgeText: "Pleasant • Low Heat Strain",
        badgeBg: "#dbeafe",
        badgeColor: "#1e40af",
        fishermanTip: "Favorable working temperature for long hauls. Minimal ice melting rate.",
        scienceNote: "Early morning or offshore sea breeze thermal cooling.",
      };
    }
  } else if (layerType === "sst") {
    if (value >= 27.5 && value <= 29.5) {
      return {
        title: "SST: Optimal Pelagic Fishing Zone",
        badgeText: "Optimal Fish Zone (27.5–29.5°C)",
        badgeBg: "#dcfce7",
        badgeColor: "#166534",
        fishermanTip: "Prime sea surface temperature! Sardines, Indian Mackerel, and Skipjack Tuna congregate heavily along these thermal edges.",
        scienceNote: "Open-Meteo Marine / INCOIS SST. Strong chlorophyll-thermal front coupling.",
      };
    } else if (value < 27.5) {
      return {
        title: "SST: Cold Water Upwelling",
        badgeText: "Cold Upwelling Pulse",
        badgeBg: "#e0f2fe",
        badgeColor: "#0369a1",
        fishermanTip: "Cool nutrient-rich water upwelling from deep shelf. Baitfish and squids follow upwelling currents to feed on plankton.",
        scienceNote: "Sub-surface coastal upwelling bringing colder, nutrient-dense water to the photic zone.",
      };
    } else {
      return {
        title: "SST: Warm Surface Waters",
        badgeText: "Warm Sea Surface (> 29.5°C)",
        badgeBg: "#ffedd5",
        badgeColor: "#9a3412",
        fishermanTip: "Warmer surface waters prompt deep-sea pelagics (tuna, kingfish) to dive into cooler thermocline depths (20–40m). Use deeper lines.",
        scienceNote: "Tropical surface heating. Thermocline deepening observed.",
      };
    }
  } else {
    // Chlorophyll
    if (value >= 1.8) {
      return {
        title: "Chlorophyll: High Biological Productivity",
        badgeText: "Rich Plankton Bloom (> 1.8 mg/m³)",
        badgeBg: "#dcfce7",
        badgeColor: "#15803d",
        fishermanTip: "Dense phytoplankton bloom! High attraction zone for baitfish (anchovies/sardines) which draw mackerel, seer fish, and trevally.",
        scienceNote: "INCOIS Oceansat-2 satellite chlorophyll proxy. Prime primary productivity signature.",
      };
    } else if (value >= 0.8) {
      return {
        title: "Chlorophyll: Moderate Productivity",
        badgeText: "Moderate Plankton (0.8–1.8 mg/m³)",
        badgeBg: "#fef9c3",
        badgeColor: "#854d0e",
        fishermanTip: "Healthy marine feeding ground. Regular schooling fish activity expected across coastal shelf waters.",
        scienceNote: "Standard Indian continental shelf bio-optical water classification.",
      };
    } else {
      return {
        title: "Chlorophyll: Open Deep Ocean",
        badgeText: "Clear Ocean Waters (< 0.8 mg/m³)",
        badgeBg: "#f1f5f9",
        badgeColor: "#334155",
        fishermanTip: "Clear oceanic waters. Favorable for deep-sea longlining and trolling for yellowfin tuna and billfish.",
        scienceNote: "Oligotrophic offshore pelagic water mass with high optical transparency.",
      };
    }
  }
}

export function MarineScalarLayer({
  mapRef,
  activeLayer,
  onLayerClick,
}: MarineScalarLayerProps) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const ptsRef = useRef<MarineScalarPoint[]>([]);

  useEffect(() => {
    if (!activeLayer) {
      ptsRef.current = [];
      return;
    }
    const map = mapRef.current;
    if (!map) return;

    let cancelled = false;
    const container = map.getContainer() as HTMLDivElement;

    const canvas = document.createElement("canvas");
    canvas.setAttribute("data-tarang", `scalar-${activeLayer}`);
    canvas.style.cssText =
      "position:absolute;top:0;left:0;width:100%;height:100%;pointer-events:none;z-index:400;";
    container.appendChild(canvas);

    function sizeCanvas() {
      canvas.width = container.clientWidth;
      canvas.height = container.clientHeight;
    }
    sizeCanvas();

    function renderCanvas() {
      const pts = ptsRef.current;
      if (!pts || !pts.length) return;
      const ctx = canvas.getContext("2d");
      if (!ctx) return;

      const W = canvas.width;
      const H = canvas.height;
      if (W === 0 || H === 0) return;

      const offW = 90;
      const offH = 65;
      const offC = document.createElement("canvas");
      offC.width = offW;
      offC.height = offH;
      const offCtx = offC.getContext("2d");
      if (!offCtx) return;

      const img = offCtx.createImageData(offW, offH);
      const d = img.data;

      const stops =
        activeLayer === "temperature"
          ? TEMP_STOPS
          : activeLayer === "sst"
          ? SST_STOPS
          : CHL_STOPS;

      for (let row = 0; row < offH; row++) {
        for (let col = 0; col < offW; col++) {
          const cssX = (col / (offW - 1)) * W;
          const cssY = (row / (offH - 1)) * H;
          const ll = map.containerPointToLatLng([cssX, cssY]);

          // Mask out land for ocean-only variables (Chlorophyll & SST)
          if ((activeLayer === "chlorophyll" || activeLayer === "sst") && isPeninsularLandPoint(ll.lat, ll.lng)) {
            continue;
          }

          const val = idwScalar(ll.lat, ll.lng, pts);
          if (val === null) continue;

          const [r, g, b] = sampleRgb(val, stops);
          const i = (row * offW + col) * 4;
          d[i]     = r;
          d[i + 1] = g;
          d[i + 2] = b;
          d[i + 3] = 135; // Alpha opacity
        }
      }

      offCtx.putImageData(img, 0, 0);
      ctx.clearRect(0, 0, W, H);
      ctx.imageSmoothingEnabled = true;
      ctx.imageSmoothingQuality = "high";
      ctx.drawImage(offC, 0, 0, W, H);
    }

    async function loadData() {
      if (cancelled || !map) return;
      setLoading(true);
      setError(null);

      const b = map.getBounds();
      const cLat = (b.getSouth() + b.getNorth()) / 2;
      const cLon = (b.getWest() + b.getEast()) / 2;

      let s = b.getSouth();
      let n = b.getNorth();
      let w = b.getWest();
      let e = b.getEast();

      if ((n - s) > 30) { s = cLat - 15; n = cLat + 15; }
      if ((e - w) > 30) { w = cLon - 15; e = cLon + 15; }

      s = Math.max(-85, s - 0.5);
      n = Math.min(85, n + 0.5);
      w = Math.max(-180, w - 0.5);
      e = Math.min(180, e + 0.5);

      try {
        const res = await fetchMarineLayerGrid(s, n, w, e, activeLayer as any, 4);
        if (cancelled) return;
        if (res && res.points && res.points.length > 0) {
          ptsRef.current = res.points;
          renderCanvas();
        } else {
          setError(`No live ${activeLayer} data for this region`);
        }
      } catch {
        if (!cancelled) setError("Marine data temporarily unavailable");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    loadData();

    const onMoveEnd = () => {
      loadData();
    };
    const onZoomEnd = () => {
      sizeCanvas();
      loadData();
    };

    const onClick = (e: any) => {
      if (!onLayerClick || !ptsRef.current.length) return;

      // Check if clicking on inland landmass for oceanographic layers
      if ((activeLayer === "chlorophyll" || activeLayer === "sst") && isPeninsularLandPoint(e.latlng.lat, e.latlng.lng)) {
        onLayerClick({
          lat: e.latlng.lat,
          lon: e.latlng.lng,
          value: 0,
          unit: "N/A",
          layerType: activeLayer,
          title: activeLayer === "chlorophyll" ? "Chlorophyll-a (Inland Landmass)" : "SST (Inland Landmass)",
          badgeText: "Inland • Marine Waters Only",
          badgeBg: "#f1f5f9",
          badgeColor: "#475569",
          fishermanTip: `${activeLayer === "chlorophyll" ? "Chlorophyll-a" : "Sea Surface Temperature"} is an oceanographic marine indicator measured exclusively in seawater. To view data, click on the sea or switch to Air Temperature for inland conditions.`,
          scienceNote: "Satellite ocean color monitors (ISRO Oceansat-2 / NASA MODIS) apply landmasks; marine algorithms are invalid over terrestrial surfaces.",
          sx: e.containerPoint.x,
          sy: e.containerPoint.y,
        });
        return;
      }

      const val = idwScalar(e.latlng.lat, e.latlng.lng, ptsRef.current);
      if (val === null) {
        onLayerClick(null);
        return;
      }

      const adv = getScalarAdvisory(activeLayer, val);
      const unit = activeLayer === "chlorophyll" ? "mg/m³" : "°C";

      onLayerClick({
        lat: e.latlng.lat,
        lon: e.latlng.lng,
        value: Math.round(val * 10) / 10,
        unit,
        layerType: activeLayer,
        title: adv.title,
        badgeText: adv.badgeText,
        badgeBg: adv.badgeBg,
        badgeColor: adv.badgeColor,
        fishermanTip: adv.fishermanTip,
        scienceNote: adv.scienceNote,
        sx: e.containerPoint.x,
        sy: e.containerPoint.y,
      });
    };

    map.on("moveend", onMoveEnd);
    map.on("zoomend", onZoomEnd);
    map.on("click", onClick);

    return () => {
      cancelled = true;
      map.off("moveend", onMoveEnd);
      map.off("zoomend", onZoomEnd);
      map.off("click", onClick);
      canvas.remove();
    };
  }, [activeLayer, mapRef]);

  if (!activeLayer) return null;

  return (
    <>
      {loading && (
        <div
          style={{
            position: "absolute", bottom: 52, left: 12, zIndex: 1001,
            background: "rgba(255,255,255,0.95)", backdropFilter: "blur(6px)",
            border: "1px solid #bae6fd", borderRadius: 8,
            padding: "5px 12px", fontSize: 11, color: "#0369a1",
            fontWeight: 600, display: "flex", alignItems: "center",
            gap: 7, pointerEvents: "none", boxShadow: "0 2px 8px rgba(0,0,0,0.08)",
          }}
        >
          <span style={{ display: "inline-block", animation: "spin 1.2s linear infinite" }}>⟳</span>
          Loading {activeLayer === "sst" ? "SST ocean temperature" : activeLayer} data…
        </div>
      )}
      {error && !loading && (
        <div
          style={{
            position: "absolute", bottom: 52, left: 12, zIndex: 1001,
            background: "rgba(255,255,255,0.95)", backdropFilter: "blur(6px)",
            border: "1px solid #fde68a", borderRadius: 8,
            padding: "6px 12px", fontSize: 11, color: "#92400e",
            fontWeight: 500, pointerEvents: "none",
            boxShadow: "0 2px 8px rgba(0,0,0,0.08)",
          }}
        >
          ⚠ {error}
        </div>
      )}
    </>
  );
}
