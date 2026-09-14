"use client";

import React from "react";
import { Compass, MapPin, Anchor, ArrowRight } from "lucide-react";
import { useLocation } from "@/lib/locationContext";

interface LocationUnavailableProps {
  featureName?: string;
  onOpenMapPicker?: () => void;
  className?: string;
}

const POPULAR_COASTAL_PORTS = [
  { name: "Kochi", state: "Kerala", lat: 9.9312, lon: 76.2673 },
  { name: "Mumbai", state: "Maharashtra", lat: 18.9388, lon: 72.8354 },
  { name: "Chennai", state: "Tamil Nadu", lat: 13.0827, lon: 80.2707 },
  { name: "Visakhapatnam", state: "Andhra Pradesh", lat: 17.6868, lon: 83.2185 },
];

export function LocationUnavailable({
  featureName = "Marine intelligence & fishing forecasts",
  onOpenMapPicker,
  className = "",
}: LocationUnavailableProps) {
  const { selectedLocation, marineContext, setPickerOpen, setLocation } = useLocation();

  const dist =
    typeof marineContext?.distance_to_coast_km === "number" && marineContext.distance_to_coast_km > 0
      ? `${Math.round(marineContext.distance_to_coast_km)} km`
      : "an inland distance";

  return (
    <div
      className={`bg-[var(--surface)] border border-[var(--border)] rounded-2xl p-6 sm:p-8 text-center max-w-xl mx-auto shadow-xs space-y-4 ${className}`}
    >
      {/* Icon Badge */}
      <div className="w-12 h-12 rounded-full bg-[#FEF3C7] text-[#D97706] border border-[#FDE68A] flex items-center justify-center mx-auto shadow-2xs">
        <Anchor className="w-5 h-5 text-[#D97706]" />
      </div>

      {/* Eyebrow */}
      <div className="font-mono-data text-[11px] text-[#B45309] uppercase tracking-widest font-medium">
        COASTAL SERVICE ADVISORY
      </div>

      {/* Heading in Fraunces / Instrument Serif */}
      <h3 className="font-serif-display text-xl sm:text-2xl text-[var(--ink)] font-normal leading-snug">
        Marine Intelligence Not Applicable for Inland Location
      </h3>

      {/* Body Copy */}
      <p className="text-xs sm:text-sm text-[var(--ink-muted)] leading-relaxed max-w-md mx-auto">
        <strong className="text-[var(--ink)] font-semibold">{selectedLocation?.name || "Selected location"}</strong> is situated approximately{" "}
        <span className="font-mono-data font-semibold text-[var(--ink)]">{dist}</span> from the nearest coastline.{" "}
        {featureName} (such as Potential Fishing Zones, tidal baselines, and swell warnings) are specifically modeled for coastal and open-sea waters.
      </p>

      {/* Action CTA Buttons */}
      <div className="flex flex-wrap items-center justify-center gap-2.5 pt-2">
        <button
          type="button"
          onClick={() => setPickerOpen(true)}
          className="inline-flex items-center gap-1.5 px-4 py-2 rounded-full bg-[var(--ink)] hover:bg-[var(--current)] text-white text-xs font-sans font-medium transition-all shadow-xs cursor-pointer"
        >
          <MapPin className="w-3.5 h-3.5" />
          <span>Choose coastal harbour</span>
        </button>

        <button
          type="button"
          onClick={() => {
            if (onOpenMapPicker) {
              onOpenMapPicker();
            } else {
              setPickerOpen(true);
            }
          }}
          className="inline-flex items-center gap-1.5 px-4 py-2 rounded-full bg-[var(--surface)] hover:bg-[var(--foam)] border border-[var(--border)] hover:border-[var(--current)]/40 text-[var(--ink)] text-xs font-sans font-medium transition-all cursor-pointer"
        >
          <Compass className="w-3.5 h-3.5 text-[var(--current)]" />
          <span>Pick offshore on map</span>
        </button>
      </div>

      {/* Quick Coastal Presets */}
      <div className="border-t border-[var(--border)] pt-4 mt-2">
        <span className="font-mono-data text-[10px] text-[var(--ink-subtle)] uppercase tracking-wider block mb-2.5">
          Or switch directly to a major coastal fishing hub:
        </span>
        <div className="flex flex-wrap items-center justify-center gap-2">
          {POPULAR_COASTAL_PORTS.map((port) => (
            <button
              key={port.name}
              type="button"
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
              className="px-3 py-1 text-xs rounded-full bg-[var(--surface-muted)] hover:bg-[var(--foam)] border border-[var(--border)] hover:border-[var(--current)]/40 text-[var(--ink)] transition-all font-mono-data cursor-pointer"
            >
              {port.name}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
