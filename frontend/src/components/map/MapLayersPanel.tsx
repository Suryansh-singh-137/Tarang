"use client";

/**
 * MapLayersPanel.tsx
 * ──────────────────
 * Floating right-side panel for marine weather and oceanographic layers:
 *  • Wind Direction (Animated flow particles)
 *  • Temperature (Air temperature at 2m, °C)
 *  • SST (Sea Surface Temperature, °C)
 *  • Chlorophyll (Satellite ocean color, mg/m³)
 *  • Fishing Zones (INCOIS PFZ advisory hotspots)
 *  • Marine Boundaries (UNCLOS IMBL treaty line)
 *
 * Fully interactive with live legends tailored for coastal fishermen.
 */

import React, { useState } from "react";
import { Wind, Thermometer, Waves, Leaf, Fish, Anchor, ChevronDown, ChevronUp } from "lucide-react";

// ─── Color Gradients ──────────────────────────────────────────────────────────
const WIND_GRADIENT =
  "linear-gradient(to right, rgb(20,80,180), rgb(40,140,195), rgb(55,185,185), rgb(80,205,130), rgb(185,225,75), rgb(250,180,40), rgb(235,75,35), rgb(170,0,10))";

const TEMP_GRADIENT =
  "linear-gradient(to right, rgb(20,60,160), rgb(45,145,215), rgb(55,195,165), rgb(250,204,21), rgb(249,115,22), rgb(220,38,38))";

const SST_GRADIENT =
  "linear-gradient(to right, rgb(30,58,138), rgb(14,165,233), rgb(16,185,129), rgb(245,158,11), rgb(239,68,68))";

const CHL_GRADIENT =
  "linear-gradient(to right, rgb(15,23,42), rgb(3,105,161), rgb(13,148,136), rgb(22,163,74), rgb(234,179,8))";

// ─── Layer row component ──────────────────────────────────────────────────────
interface LayerRowProps {
  icon: React.ReactNode;
  label: string;
  subLabel?: string;
  enabled: boolean;
  onToggle: () => void;
  accentColor?: string;
}

function LayerRow({ icon, label, subLabel, enabled, onToggle, accentColor = "bg-sky-500 border-sky-600" }: LayerRowProps) {
  return (
    <div className="flex items-center justify-between py-1.5 px-0 group">
      <div className="flex items-center gap-2.5 min-w-0">
        <span className={`shrink-0 transition-colors ${enabled ? "text-sky-600" : "text-[var(--ink-muted)]"}`}>{icon}</span>
        <div className="min-w-0">
          <div className="text-[12px] font-medium text-[var(--ink)] leading-tight">{label}</div>
          {subLabel && (
            <div className="text-[9.5px] text-[var(--ink-muted)] leading-tight truncate">{subLabel}</div>
          )}
        </div>
      </div>

      <button
        type="button"
        role="switch"
        aria-checked={enabled}
        aria-label={`Toggle ${label}`}
        onClick={onToggle}
        className={`relative w-9 h-5 rounded-full border-2 shrink-0 transition-all duration-200 cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-400 ${
          enabled ? accentColor : "bg-white border-gray-300"
        }`}
      >
        <span
          className={`absolute top-0.5 left-0.5 w-3.5 h-3.5 rounded-full shadow-xs transition-transform duration-200 ${
            enabled ? "translate-x-4 bg-white" : "translate-x-0 bg-gray-300"
          }`}
        />
      </button>
    </div>
  );
}

// ─── Main panel props ─────────────────────────────────────────────────────────
export interface MapLayersPanelProps {
  windEnabled: boolean;
  onWindToggle: () => void;
  tempEnabled: boolean;
  onTempToggle: () => void;
  sstEnabled: boolean;
  onSstToggle: () => void;
  chlEnabled: boolean;
  onChlToggle: () => void;
  pfzEnabled: boolean;
  onPfzToggle: () => void;
  imblEnabled: boolean;
  onImblToggle: () => void;
}

export function MapLayersPanel({
  windEnabled,
  onWindToggle,
  tempEnabled,
  onTempToggle,
  sstEnabled,
  onSstToggle,
  chlEnabled,
  onChlToggle,
  pfzEnabled,
  onPfzToggle,
  imblEnabled,
  onImblToggle,
}: MapLayersPanelProps) {
  const [collapsed, setCollapsed] = useState(false);
  const [legendOpen, setLegendOpen] = useState(true);

  // Determine which legend to show primarily
  const activeLegendType = sstEnabled
    ? "sst"
    : chlEnabled
    ? "chlorophyll"
    : tempEnabled
    ? "temperature"
    : pfzEnabled
    ? "pfz"
    : imblEnabled
    ? "imbl"
    : "wind";

  return (
    <div
      className="absolute right-3 z-[1000] pointer-events-auto select-none"
      style={{ top: "56px" }}
    >
      <div
        className="bg-white/97 backdrop-blur-md border border-[var(--border)] rounded-xl shadow-lg w-56 md:w-60 overflow-hidden"
        style={{ boxShadow: "0 4px 24px rgba(0,0,0,0.12)" }}
      >
        {/* Header row */}
        <div
          className="flex items-center justify-between px-3 py-2 border-b border-[var(--border)] cursor-pointer select-none bg-white/80"
          onClick={() => setCollapsed((v) => !v)}
          role="button"
          aria-expanded={!collapsed}
          aria-label="Toggle map layers panel"
        >
          <div className="flex items-center gap-1.5">
            <svg
              className="w-3.5 h-3.5 text-sky-600"
              viewBox="0 0 16 16"
              fill="none"
              xmlns="http://www.w3.org/2000/svg"
            >
              <rect x="1" y="11" width="14" height="2" rx="1" fill="currentColor" />
              <rect x="1" y="7" width="14" height="2" rx="1" fill="currentColor" opacity=".7" />
              <rect x="1" y="3" width="14" height="2" rx="1" fill="currentColor" opacity=".4" />
            </svg>
            <span className="text-[12px] font-bold text-[var(--ink)] tracking-tight">Marine Map Layers</span>
          </div>
          {collapsed ? (
            <ChevronDown className="w-3.5 h-3.5 text-[var(--ink-muted)]" />
          ) : (
            <ChevronUp className="w-3.5 h-3.5 text-[var(--ink-muted)]" />
          )}
        </div>

        {!collapsed && (
          <>
            {/* ── Layer list ────────────────────────────────────────────── */}
            <div className="px-3 pt-1.5 pb-1 divide-y divide-[var(--border)]">
              <LayerRow
                icon={<Wind className="w-3.5 h-3.5" />}
                label="Wind Direction"
                subLabel="Vector particle flow"
                enabled={windEnabled}
                onToggle={onWindToggle}
                accentColor="bg-sky-500 border-sky-600"
              />
              <LayerRow
                icon={<Thermometer className="w-3.5 h-3.5" />}
                label="Air Temperature"
                subLabel="2m coastal heat (°C)"
                enabled={tempEnabled}
                onToggle={onTempToggle}
                accentColor="bg-amber-500 border-amber-600"
              />
              <LayerRow
                icon={<Waves className="w-3.5 h-3.5" />}
                label="SST (Sea Surface Temp)"
                subLabel="Ocean thermal surface (°C)"
                enabled={sstEnabled}
                onToggle={onSstToggle}
                accentColor="bg-emerald-500 border-emerald-600"
              />
              <LayerRow
                icon={<Leaf className="w-3.5 h-3.5" />}
                label="Chlorophyll-a"
                subLabel="Satellite ocean color (mg/m³)"
                enabled={chlEnabled}
                onToggle={onChlToggle}
                accentColor="bg-teal-500 border-teal-600"
              />
              <LayerRow
                icon={<Fish className="w-3.5 h-3.5" />}
                label="Fishing Zones (PFZ)"
                subLabel="INCOIS satellite beacons"
                enabled={pfzEnabled}
                onToggle={onPfzToggle}
                accentColor="bg-green-600 border-green-700"
              />
              <LayerRow
                icon={<Anchor className="w-3.5 h-3.5" />}
                label="Marine Boundaries"
                subLabel="UNCLOS borders (7 countries)"
                enabled={imblEnabled}
                onToggle={onImblToggle}
                accentColor="bg-red-500 border-red-600"
              />
            </div>

            {/* ── Dynamic Legend Section ────────────────────────────────── */}
            <div className="border-t border-[var(--border)]">
              <div
                className="flex items-center justify-between px-3 py-1.5 cursor-pointer hover:bg-gray-50 transition-colors"
                onClick={() => setLegendOpen((v) => !v)}
                role="button"
                aria-expanded={legendOpen}
              >
                <span className="text-[11px] font-semibold text-[var(--ink)] flex items-center gap-1.5">
                  {activeLegendType === "sst" && <Waves className="w-3 h-3 text-emerald-600" />}
                  {activeLegendType === "chlorophyll" && <Leaf className="w-3 h-3 text-teal-600" />}
                  {activeLegendType === "temperature" && <Thermometer className="w-3 h-3 text-amber-500" />}
                  {activeLegendType === "pfz" && <Fish className="w-3 h-3 text-green-600" />}
                  {activeLegendType === "imbl" && <Anchor className="w-3 h-3 text-red-600" />}
                  {activeLegendType === "wind" && <Wind className="w-3 h-3 text-sky-500" />}
                  <span>
                    {activeLegendType === "sst" && "SST Ocean Temp (°C)"}
                    {activeLegendType === "chlorophyll" && "Chlorophyll-a (mg/m³)"}
                    {activeLegendType === "temperature" && "Air Temperature (°C)"}
                    {activeLegendType === "pfz" && "PFZ Advisory Beacons"}
                    {activeLegendType === "imbl" && "IMBL Boundary Alert"}
                    {activeLegendType === "wind" && "Wind Speed (km/h)"}
                  </span>
                </span>
                {legendOpen ? (
                  <ChevronUp className="w-3 h-3 text-[var(--ink-muted)]" />
                ) : (
                  <ChevronDown className="w-3 h-3 text-[var(--ink-muted)]" />
                )}
              </div>

              {legendOpen && (
                <div className="px-3 pb-3 space-y-2">
                  {/* 1. SST Legend */}
                  {activeLegendType === "sst" && (
                    <>
                      <div className="h-2.5 w-full rounded-full" style={{ background: SST_GRADIENT }} />
                      <div className="flex justify-between text-[10px] text-[var(--ink-muted)] font-medium px-0.5">
                        <span>24°C</span>
                        <span>27°C</span>
                        <span className="text-emerald-700 font-bold">28.5°</span>
                        <span>30°C</span>
                        <span>32°C</span>
                      </div>
                      <div className="bg-emerald-50 border border-emerald-200 rounded p-1.5 text-[9.5px] text-emerald-900 leading-tight">
                        <span className="font-bold">🟢 Pelagic Goldilocks Zone (27.5–29.5°C):</span> Tuna, Mackerel &amp; Sardines congregate along thermal edges. Tap sea for localized SST.
                      </div>
                    </>
                  )}

                  {/* 2. Chlorophyll Legend */}
                  {activeLegendType === "chlorophyll" && (
                    <>
                      <div className="h-2.5 w-full rounded-full" style={{ background: CHL_GRADIENT }} />
                      <div className="flex justify-between text-[10px] text-[var(--ink-muted)] font-medium px-0.5">
                        <span>0.1</span>
                        <span>0.8</span>
                        <span>1.5</span>
                        <span>2.5</span>
                        <span>3.5+</span>
                      </div>
                      <div className="bg-teal-50 border border-teal-200 rounded p-1.5 text-[9.5px] text-teal-900 leading-tight">
                        <span className="font-bold">🌱 High Plankton (&gt; 1.5 mg/m³):</span> Primary feeding ground for baitfish. Tap ocean to inspect biological productivity.
                      </div>
                    </>
                  )}

                  {/* 3. Temperature Legend */}
                  {activeLegendType === "temperature" && (
                    <>
                      <div className="h-2.5 w-full rounded-full" style={{ background: TEMP_GRADIENT }} />
                      <div className="flex justify-between text-[10px] text-[var(--ink-muted)] font-medium px-0.5">
                        <span>18°C</span>
                        <span>25°C</span>
                        <span>28°C</span>
                        <span>32°C</span>
                        <span>38°C</span>
                      </div>
                      <div className="bg-amber-50 border border-amber-200 rounded p-1.5 text-[9.5px] text-amber-900 leading-tight">
                        <span className="font-bold">🧊 Fish Preservation:</span> In temperatures &gt; 30°C, use 1:1 ice-to-fish ratio to prevent catch spoilage. Tap sea for ambient heat index.
                      </div>
                    </>
                  )}

                  {/* 4. PFZ Legend */}
                  {activeLegendType === "pfz" && (
                    <div className="space-y-1.5 text-[10px]">
                      <div className="flex items-center gap-1.5 text-emerald-800 bg-emerald-50 px-2 py-1 rounded border border-emerald-200">
                        <span className="text-xs">🐟</span>
                        <span className="font-semibold">INCOIS Satellite Beacons:</span>
                        <span className="text-emerald-950 truncate">Tuna, Mackerel, Sardine</span>
                      </div>
                      <p className="text-[9.5px] text-slate-600 leading-tight">
                        Generated by INCOIS Oceansat-2 ocean color &amp; thermal front convergence.
                      </p>
                    </div>
                  )}

                  {/* 5. IMBL Legend */}
                  {activeLegendType === "imbl" && (
                    <div className="space-y-1.5 text-[10px]">
                      <div className="flex items-center gap-1.5 text-red-800 bg-red-50 px-2 py-1 rounded border border-red-200">
                        <span className="font-bold">⛔</span>
                        <span className="font-semibold">UNCLOS Maritime Boundaries:</span>
                        <span className="text-red-950 font-bold truncate">Border Crossing Prohibited</span>
                      </div>
                      <p className="text-[9.5px] text-red-700 leading-tight">
                        Red dashed lines show demarcated borders with Sri Lanka, Pakistan, Bangladesh, Maldives, Myanmar, Indonesia &amp; Thailand. Maintain 5 km clearance.
                      </p>
                    </div>
                  )}

                  {/* 6. Wind Legend */}
                  {activeLegendType === "wind" && (
                    <>
                      <div className="h-2.5 w-full rounded-full" style={{ background: WIND_GRADIENT }} />
                      <div className="flex justify-between text-[10px] text-[var(--ink-muted)] font-medium px-0.5">
                        <span>0 km/h</span>
                        <span>15</span>
                        <span>28</span>
                        <span>42+</span>
                      </div>
                      <div className="border-t border-[var(--border)] pt-1.5 space-y-1 text-[9.5px]">
                        <div className="flex items-center gap-1.5 text-emerald-700 bg-emerald-50 px-1.5 py-0.5 rounded border border-emerald-200">
                          <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 shrink-0"></span>
                          <span className="font-semibold">&lt; 15:</span>
                          <span className="truncate">Safe for all boats</span>
                        </div>
                        <div className="flex items-center gap-1.5 text-amber-800 bg-amber-50 px-1.5 py-0.5 rounded border border-amber-200">
                          <span className="w-1.5 h-1.5 rounded-full bg-amber-500 shrink-0"></span>
                          <span className="font-semibold">16–28:</span>
                          <span className="truncate">Caution for small craft</span>
                        </div>
                        <div className="flex items-center gap-1.5 text-orange-800 bg-orange-50 px-1.5 py-0.5 rounded border border-orange-200">
                          <span className="w-1.5 h-1.5 rounded-full bg-orange-500 shrink-0"></span>
                          <span className="font-semibold">29–42:</span>
                          <span className="truncate">Rough • Stay inshore</span>
                        </div>
                        <div className="flex items-center gap-1.5 text-red-800 bg-red-50 px-1.5 py-0.5 rounded border border-red-200">
                          <span className="w-1.5 h-1.5 rounded-full bg-red-600 shrink-0"></span>
                          <span className="font-semibold">&gt; 42:</span>
                          <span className="font-bold truncate">Danger • Return to port</span>
                        </div>
                      </div>
                    </>
                  )}
                </div>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
