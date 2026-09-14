"use client";

import React, { useState } from "react";
import { useLocation } from "@/lib/locationContext";
import { MarineContextBadge } from "./MarineContextBadge";
import { LocationSearch } from "./LocationSearch";
import { CurrentLocationButton } from "./CurrentLocationButton";
import { LocationMapPicker } from "./LocationMapPicker";

interface LocationSelectorProps {
  className?: string;
}

export function LocationSelector({ className = "" }: LocationSelectorProps) {
  const { selectedLocation, marineContext, isPickerOpen, setPickerOpen, isLoading } = useLocation();
  const [activeTab, setActiveTab] = useState<"search" | "map">("search");

  return (
    <>
      {/* Header Location Pill */}
      <button
        onClick={() => setPickerOpen(true)}
        type="button"
        className={`group inline-flex items-center gap-2 px-3 py-1.5 rounded-full border border-stone-700/80 bg-stone-900/80 hover:bg-stone-800 hover:border-amber-400/60 transition-all text-xs font-medium text-stone-200 shadow-sm backdrop-blur-sm ${className}`}
        title={`Current Location: ${selectedLocation.display_name}. Click to change.`}
      >
        <span className="text-amber-400 text-sm group-hover:scale-110 transition-transform">📍</span>
        <span className="font-semibold text-white max-w-[130px] sm:max-w-[200px] truncate">
          {selectedLocation.name}
        </span>
        <MarineContextBadge type={marineContext.type} size="sm" />
        <svg
          className="w-3.5 h-3.5 text-stone-400 group-hover:text-amber-300 transition-colors"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {/* Location Modal */}
      {isPickerOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-4 bg-black/75 backdrop-blur-sm animate-in fade-in duration-150">
          <div
            className="relative w-full max-w-2xl bg-stone-900 border border-stone-700/80 rounded-2xl shadow-2xl overflow-hidden flex flex-col max-h-[90vh]"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Modal Header */}
            <div className="p-4 border-b border-stone-800 flex items-center justify-between bg-stone-900/90">
              <div className="flex items-center gap-2">
                <span className="text-lg">📍</span>
                <div>
                  <h2 className="text-base font-serif font-semibold text-stone-100">Select Location</h2>
                  <p className="text-[11px] text-stone-400">
                    Tarang adapts marine forecasts, tides, and fishing zones dynamically.
                  </p>
                </div>
              </div>
              <button
                onClick={() => setPickerOpen(false)}
                className="w-8 h-8 rounded-full hover:bg-stone-800 text-stone-400 hover:text-white flex items-center justify-center text-sm transition-colors"
              >
                ✕
              </button>
            </div>

            {/* Subheader / Tabs */}
            <div className="px-4 py-2.5 bg-stone-950/60 border-b border-stone-800 flex flex-wrap items-center justify-between gap-2">
              <div className="flex items-center gap-1 bg-stone-900 p-0.5 rounded-lg border border-stone-800">
                <button
                  type="button"
                  onClick={() => setActiveTab("search")}
                  className={`px-3 py-1 rounded-md text-xs font-medium transition-all ${
                    activeTab === "search"
                      ? "bg-amber-400 text-stone-950 font-semibold shadow"
                      : "text-stone-300 hover:text-white"
                  }`}
                >
                  🔍 Search & Presets
                </button>
                <button
                  type="button"
                  onClick={() => setActiveTab("map")}
                  className={`px-3 py-1 rounded-md text-xs font-medium transition-all ${
                    activeTab === "map"
                      ? "bg-amber-400 text-stone-950 font-semibold shadow"
                      : "text-stone-300 hover:text-white"
                  }`}
                >
                  🗺️ Pick on Map
                </button>
              </div>

              {/* GPS Button */}
              <CurrentLocationButton onSuccess={() => setPickerOpen(false)} />
            </div>

            {/* Modal Body */}
            <div className="flex-1 overflow-y-auto">
              {activeTab === "search" ? (
                <div className="p-4 flex flex-col gap-4">
                  {/* Current Active Location Info */}
                  <div className="p-3 rounded-xl bg-stone-950/70 border border-stone-800 flex items-start justify-between gap-3">
                    <div>
                      <div className="text-[11px] text-stone-400 uppercase tracking-wider mb-0.5">Active Location</div>
                      <div className="font-semibold text-white text-sm flex items-center gap-2">
                        <span>{selectedLocation.name}</span>
                        <MarineContextBadge type={marineContext.type} size="sm" />
                      </div>
                      <div className="text-xs text-stone-400 mt-0.5">{selectedLocation.display_name}</div>
                      <div className="text-[11px] text-stone-400 font-mono mt-1">
                        {selectedLocation.lat.toFixed(4)}° N, {selectedLocation.lon.toFixed(4)}° E
                      </div>
                    </div>

                    <div className="text-right text-xs">
                      <div className="text-stone-400 text-[11px]">Nearest Port</div>
                      <div className="font-medium text-amber-300">{marineContext.nearest_port || "—"}</div>
                      <div className="text-[10px] text-stone-400 mt-1">
                        {marineContext.tide_available ? "✓ Tides Active" : "✗ Tides Inactive"}
                      </div>
                    </div>
                  </div>

                  {/* Search and Autocomplete */}
                  <LocationSearch onSelect={() => setPickerOpen(false)} autoFocus />
                </div>
              ) : (
                <div className="h-[480px]">
                  <LocationMapPicker onClose={() => setPickerOpen(false)} />
                </div>
              )}
            </div>

            {/* Modal Footer */}
            <div className="p-3 bg-stone-950 border-t border-stone-800 flex items-center justify-between text-[11px] text-stone-400">
              <span className="flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-emerald-400" />
                Automatic Multi-Tier Geocoding (Gazetteer → OpenWeather → OpenStreetMap)
              </span>
              <button
                type="button"
                onClick={() => setPickerOpen(false)}
                className="text-stone-300 hover:text-white px-2 py-1 rounded hover:bg-stone-800 transition-colors"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
