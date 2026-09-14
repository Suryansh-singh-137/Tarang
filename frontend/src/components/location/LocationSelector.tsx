"use client";

import React, { useState } from "react";
import { ChevronDown, X, MapPin, Compass, Search } from "lucide-react";
import { useLocation } from "@/lib/locationContext";
import { MarineContextBadge } from "./MarineContextBadge";
import { LocationSearch } from "./LocationSearch";
import { CurrentLocationButton } from "./CurrentLocationButton";
import { LocationMapPicker } from "./LocationMapPicker";

interface LocationSelectorProps {
  className?: string;
}

export function LocationSelector({ className = "" }: LocationSelectorProps) {
  const { selectedLocation, marineContext, isPickerOpen, setPickerOpen } = useLocation();
  const [activeTab, setActiveTab] = useState<"search" | "map">("search");

  return (
    <>
      {/* Header Location Pill (Styled to match Coastal Dawn editorial navigation) */}
      <button
        onClick={() => setPickerOpen(true)}
        type="button"
        className={`group inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-[var(--surface)] hover:bg-[var(--foam)]/80 text-[var(--ink)] font-medium transition-all border border-[var(--border)] hover:border-[var(--current)]/40 shadow-2xs font-mono-data text-[11px] cursor-pointer ${className}`}
        title={`Current Location: ${selectedLocation.display_name}. Tap to change.`}
      >
        <span className="w-2 h-2 rounded-full bg-[var(--current)] animate-pulse" />
        <span className="font-semibold text-[var(--ink)] max-w-[120px] sm:max-w-[160px] truncate">
          {selectedLocation.name}
        </span>
        <MarineContextBadge type={marineContext.type} size="sm" />
        <ChevronDown className="w-3.5 h-3.5 text-[var(--ink-muted)] group-hover:text-[var(--current)] transition-colors" />
      </button>

      {/* Location Selection Modal */}
      {isPickerOpen && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-4 bg-[var(--ink)]/40 backdrop-blur-xs animate-in fade-in duration-150"
          onClick={() => setPickerOpen(false)}
        >
          <div
            className="relative w-full max-w-2xl bg-[var(--surface)] border border-[var(--border)] rounded-2xl shadow-xl overflow-hidden flex flex-col max-h-[90vh]"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Modal Header */}
            <div className="p-4 sm:p-5 border-b border-[var(--border)] flex items-center justify-between bg-[var(--surface)]">
              <div>
                <h2 className="text-xl sm:text-2xl font-serif-display text-[var(--ink)] font-normal">
                  Select Location
                </h2>
                <p className="font-mono-data text-[11px] text-[var(--ink-muted)] uppercase tracking-wider mt-0.5">
                  Dynamic Geocoding & Marine Baseline
                </p>
              </div>
              <button
                type="button"
                onClick={() => setPickerOpen(false)}
                className="w-8 h-8 rounded-full hover:bg-[var(--surface-muted)] text-[var(--ink-muted)] hover:text-[var(--ink)] flex items-center justify-center transition-colors border border-[var(--border)] cursor-pointer"
                aria-label="Close location modal"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Subheader / Mode Switcher */}
            <div className="px-4 py-2.5 bg-[var(--surface-muted)] border-b border-[var(--border)] flex flex-wrap items-center justify-between gap-2">
              <div className="flex items-center gap-1 bg-[var(--surface)] p-1 rounded-full border border-[var(--border)] shadow-2xs">
                <button
                  type="button"
                  onClick={() => setActiveTab("search")}
                  className={`inline-flex items-center gap-1.5 px-3.5 py-1 rounded-full text-xs font-sans transition-all cursor-pointer ${
                    activeTab === "search"
                      ? "bg-[var(--current)] text-white font-medium shadow-xs"
                      : "text-[var(--ink-muted)] hover:text-[var(--ink)] hover:bg-[var(--foam)]"
                  }`}
                >
                  <Search className="w-3 h-3" />
                  <span>Search & Presets</span>
                </button>
                <button
                  type="button"
                  onClick={() => setActiveTab("map")}
                  className={`inline-flex items-center gap-1.5 px-3.5 py-1 rounded-full text-xs font-sans transition-all cursor-pointer ${
                    activeTab === "map"
                      ? "bg-[var(--current)] text-white font-medium shadow-xs"
                      : "text-[var(--ink-muted)] hover:text-[var(--ink)] hover:bg-[var(--foam)]"
                  }`}
                >
                  <Compass className="w-3 h-3" />
                  <span>Pick on Map</span>
                </button>
              </div>

              {/* GPS Button */}
              <CurrentLocationButton onSuccess={() => setPickerOpen(false)} />
            </div>

            {/* Modal Body */}
            <div className="flex-1 overflow-y-auto">
              {activeTab === "search" ? (
                <div className="p-4 sm:p-5 flex flex-col gap-4">
                  {/* Active Location Info Card */}
                  <div className="p-3.5 rounded-xl bg-[var(--surface-muted)] border border-[var(--border)] flex items-start justify-between gap-3 shadow-2xs">
                    <div>
                      <div className="font-mono-data text-[10px] text-[var(--ink-subtle)] uppercase tracking-wider mb-1">
                        Active Operational Baseline
                      </div>
                      <div className="font-semibold text-[var(--ink)] text-sm flex items-center gap-2">
                        <span>{selectedLocation.name}</span>
                        <MarineContextBadge type={marineContext.type} size="sm" />
                      </div>
                      <div className="text-xs text-[var(--ink-muted)] mt-0.5">{selectedLocation.display_name}</div>
                      <div className="text-[11px] text-[var(--ink-subtle)] font-mono-data mt-1">
                        {selectedLocation.lat.toFixed(4)}° N, {selectedLocation.lon.toFixed(4)}° E
                      </div>
                    </div>

                    <div className="text-right text-xs shrink-0">
                      <div className="text-[10px] font-mono-data text-[var(--ink-subtle)] uppercase tracking-wider">
                        Nearest Port
                      </div>
                      <div className="font-medium text-[var(--current)] mt-0.5">
                        {marineContext.nearest_port || "—"}
                      </div>
                      <div className="text-[10px] font-mono-data text-[var(--ink-muted)] mt-1">
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
            <div className="p-3.5 bg-[var(--surface-muted)] border-t border-[var(--border)] flex items-center justify-between text-[11px] font-mono-data text-[var(--ink-muted)]">
              <span className="flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-[#1B8755]" />
                <span>Multi-Tier Geocoding (Gazetteer → OpenWeather → OSM)</span>
              </span>
              <button
                type="button"
                onClick={() => setPickerOpen(false)}
                className="text-[var(--ink-muted)] hover:text-[var(--ink)] px-3 py-1 rounded-full hover:bg-[var(--surface)] transition-colors border border-transparent hover:border-[var(--border)] cursor-pointer"
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
