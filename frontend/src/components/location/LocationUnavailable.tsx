"use client";

import React from "react";
import { useLocation } from "@/lib/locationContext";

interface LocationUnavailableProps {
  featureName?: string;
  onOpenMapPicker?: () => void;
  className?: string;
}

export function LocationUnavailable({
  featureName = "Marine intelligence & fishing forecasts",
  onOpenMapPicker,
  className = "",
}: LocationUnavailableProps) {
  const { selectedLocation, marineContext, setPickerOpen, setLocation } = useLocation();

  const dist = marineContext?.distance_to_coast_km
    ? `${Math.round(marineContext.distance_to_coast_km)} km`
    : "several hundred km";

  const popularCoastalPorts = [
    { name: "Kochi", state: "Kerala", lat: 9.9312, lon: 76.2673 },
    { name: "Mumbai", state: "Maharashtra", lat: 18.9388, lon: 72.8354 },
    { name: "Chennai", state: "Tamil Nadu", lat: 13.0827, lon: 80.2707 },
    { name: "Visakhapatnam", state: "Andhra Pradesh", lat: 17.6868, lon: 83.2185 },
  ];

  return (
    <div
      className={`rounded-2xl border border-amber-500/30 bg-amber-950/20 p-6 text-center max-w-xl mx-auto shadow-lg backdrop-blur-sm ${className}`}
    >
      <div className="w-12 h-12 mx-auto mb-3 rounded-full bg-amber-500/10 border border-amber-500/30 flex items-center justify-center text-amber-400 text-2xl">
        ⚓
      </div>
      <h3 className="text-lg font-serif font-semibold text-amber-200 mb-1">
        Marine Data Not Applicable for Inland Location
      </h3>
      <p className="text-sm text-stone-300 mb-4 leading-relaxed">
        <span className="font-semibold text-white">{selectedLocation?.name || "Current place"}</span> is situated approximately{" "}
        <span className="font-semibold text-amber-300">{dist}</span> from the nearest coastline.{" "}
        {featureName} (such as Potential Fishing Zones, tidal baselines, and swell warnings) are specifically modeled for coastal and open-sea waters.
      </p>

      <div className="flex flex-wrap items-center justify-center gap-3 mb-5">
        <button
          onClick={() => setPickerOpen(true)}
          className="px-4 py-2 text-xs font-semibold text-stone-900 bg-amber-400 hover:bg-amber-300 rounded-lg transition-colors shadow-sm flex items-center gap-1.5"
        >
          <span>📍</span> Choose coastal location
        </button>
        {onOpenMapPicker ? (
          <button
            onClick={onOpenMapPicker}
            className="px-4 py-2 text-xs font-semibold text-amber-300 border border-amber-500/40 hover:bg-amber-500/10 rounded-lg transition-colors flex items-center gap-1.5"
          >
            <span>🗺️</span> Pick offshore on map
          </button>
        ) : (
          <button
            onClick={() => setPickerOpen(true)}
            className="px-4 py-2 text-xs font-semibold text-amber-300 border border-amber-500/40 hover:bg-amber-500/10 rounded-lg transition-colors flex items-center gap-1.5"
          >
            <span>🗺️</span> Pick on map
          </button>
        )}
      </div>

      <div className="border-t border-amber-500/20 pt-3">
        <p className="text-[11px] text-stone-400 mb-2">Or switch directly to a coastal fishing hub:</p>
        <div className="flex flex-wrap items-center justify-center gap-2">
          {popularCoastalPorts.map((port) => (
            <button
              key={port.name}
              onClick={() =>
                setLocation({
                  name: port.name,
                  display_name: `${port.name}, ${port.state}, India`,
                  lat: port.lat,
                  lon: port.lon,
                  state: port.state,
                  country: "India",
                  source: "search",
                })
              }
              className="px-2.5 py-1 text-[11px] rounded-md bg-stone-800/80 border border-stone-700 text-stone-200 hover:border-amber-400 hover:text-amber-200 transition-colors"
            >
              {port.name}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
