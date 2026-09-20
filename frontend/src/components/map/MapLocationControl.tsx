"use client";

import React, { useState, useRef, useEffect } from "react";
import {
  MapPin,
  Search,
  Crosshair,
  Compass,
  Navigation,
  Check,
  X,
  ChevronDown,
  Anchor,
  Loader2,
  Sliders,
} from "lucide-react";
import { useLocation } from "@/lib/locationContext";
import { LocationSearchResult } from "@/lib/types";

interface Props {
  isPickingOnMap: boolean;
  onTogglePickOnMap: (active: boolean) => void;
  clickedPoint: { lat: number; lon: number } | null;
  onClearClickedPoint: () => void;
  onConfirmClickedPoint: (lat: number, lon: number) => void;
  className?: string;
}

const POPULAR_COASTAL_PORTS = [
  { name: "Kochi", state: "Kerala", lat: 9.9312, lon: 76.2673 },
  { name: "Mumbai", state: "Maharashtra", lat: 18.9388, lon: 72.8354 },
  { name: "Chennai", state: "Tamil Nadu", lat: 13.0827, lon: 80.2707 },
  { name: "Visakhapatnam", state: "Andhra Pradesh", lat: 17.6868, lon: 83.2185 },
  { name: "Rameswaram", state: "Tamil Nadu", lat: 9.2876, lon: 79.3129 },
  { name: "Mangalore", state: "Karnataka", lat: 12.9141, lon: 74.856 },
  { name: "Porbandar", state: "Gujarat", lat: 21.6417, lon: 69.6293 },
  { name: "Veraval", state: "Gujarat", lat: 20.9077, lon: 70.3676 },
  { name: "Paradip", state: "Odisha", lat: 20.2644, lon: 86.6083 },
  { name: "Tuticorin", state: "Tamil Nadu", lat: 8.7642, lon: 78.1348 },
];

export const MapLocationControl: React.FC<Props> = ({
  isPickingOnMap,
  onTogglePickOnMap,
  clickedPoint,
  onClearClickedPoint,
  onConfirmClickedPoint,
  className = "",
}) => {
  const { selectedLocation, setLocation, selectCoordinates, searchLocations, isLoading } = useLocation();

  const [isManualModalOpen, setIsManualModalOpen] = useState(false);
  const [activeTab, setActiveTab] = useState<"search" | "coords" | "gps">("search");

  // Search input state
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<LocationSearchResult[]>([]);
  const [isSearching, setIsSearching] = useState(false);

  // Manual Coordinates state
  const [inputLat, setInputLat] = useState(selectedLocation.lat.toFixed(4));
  const [inputLon, setInputLon] = useState(selectedLocation.lon.toFixed(4));
  const [coordError, setCoordError] = useState<string | null>(null);

  // GPS fetching state
  const [isLocatingGPS, setIsLocatingGPS] = useState(false);

  // Handle Search autocomplete
  useEffect(() => {
    const q = searchQuery.trim();
    if (!q) {
      setSearchResults([]);
      setIsSearching(false);
      return;
    }

    const timer = setTimeout(async () => {
      setIsSearching(true);
      try {
        const res = await searchLocations(q);
        setSearchResults(res || []);
      } catch (err) {
        console.error("Location search error:", err);
      } finally {
        setIsSearching(false);
      }
    }, 250);

    return () => clearTimeout(timer);
  }, [searchQuery, searchLocations]);

  // Handle Port Selection
  const handleSelectPort = async (port: { name: string; state?: string | null; lat: number; lon: number }) => {
    await setLocation({
      name: port.name,
      display_name: `${port.name}, ${port.state || "India"}`,
      lat: port.lat,
      lon: port.lon,
      state: port.state || null,
      country: "India",
      source: "search",
    });
    setIsManualModalOpen(false);
    setSearchQuery("");
  };

  // Handle Manual Coordinates Submit
  const handleApplyCoordinates = async (e: React.FormEvent) => {
    e.preventDefault();
    setCoordError(null);

    const lat = parseFloat(inputLat);
    const lon = parseFloat(inputLon);

    if (isNaN(lat) || lat < -90 || lat > 90) {
      setCoordError("Please enter a valid Latitude between -90 and 90.");
      return;
    }
    if (isNaN(lon) || lon < -180 || lon > 180) {
      setCoordError("Please enter a valid Longitude between -180 and 180.");
      return;
    }

    await selectCoordinates(lat, lon, undefined, "map");
    setIsManualModalOpen(false);
  };

  // Handle Device GPS Locating
  const handleGetDeviceLocation = () => {
    if (!navigator.geolocation) {
      alert("Geolocation is not supported by your browser.");
      return;
    }

    setIsLocatingGPS(true);
    navigator.geolocation.getCurrentPosition(
      async (pos) => {
        setIsLocatingGPS(false);
        const lat = pos.coords.latitude;
        const lon = pos.coords.longitude;
        await selectCoordinates(lat, lon, "Device GPS", "gps");
        setIsManualModalOpen(false);
      },
      (err) => {
        setIsLocatingGPS(false);
        alert(`Could not acquire GPS position: ${err.message}`);
      },
      { enableHighAccuracy: true, timeout: 10000 }
    );
  };

  return (
    <>
      {/* ── Toolbar Location Button Group ── */}
      <div className={`flex items-center gap-1.5 ${className}`}>
        {/* Active Location Pill Button */}
        <button
          type="button"
          onClick={() => setIsManualModalOpen(true)}
          className="px-2.5 py-1.5 bg-white/95 backdrop-blur-xs hover:bg-white text-[var(--ink)] border border-[var(--border)] rounded-lg shadow-xs flex items-center gap-1.5 text-xs font-semibold transition-all cursor-pointer hover:border-[var(--current)]/60"
          title={`Active Location: ${selectedLocation.name} (${selectedLocation.lat.toFixed(2)}°N, ${selectedLocation.lon.toFixed(2)}°E). Click for manual selection.`}
        >
          <span className="w-2 h-2 rounded-full bg-[var(--current)] animate-pulse" />
          <span className="max-w-[120px] sm:max-w-[170px] truncate">{selectedLocation.name}</span>
          <span className="text-[10px] text-[var(--ink-muted)] font-mono hidden sm:inline">
            ({selectedLocation.lat.toFixed(2)}°, {selectedLocation.lon.toFixed(2)}°)
          </span>
          <ChevronDown className="w-3.5 h-3.5 text-[var(--ink-muted)]" />
        </button>

        {/* Click-to-Pick on Map Toggle */}
        <button
          type="button"
          onClick={() => onTogglePickOnMap(!isPickingOnMap)}
          className={`px-2.5 py-1.5 rounded-lg border text-xs font-semibold flex items-center gap-1.5 transition-all cursor-pointer shadow-xs ${
            isPickingOnMap
              ? "bg-[#0284C7] text-white border-[#0284C7] ring-2 ring-[#0284C7]/30 animate-pulse"
              : "bg-white/95 backdrop-blur-xs text-[var(--ink)] border-[var(--border)] hover:bg-white hover:border-[var(--current)]/60"
          }`}
          title={isPickingOnMap ? "Click on map mode ACTIVE. Click anywhere on sea." : "Enable Click-to-Pick mode on map"}
        >
          <Crosshair className={`w-3.5 h-3.5 ${isPickingOnMap ? "text-white" : "text-[#0284C7]"}`} />
          <span className="hidden sm:inline">{isPickingOnMap ? "Picking..." : "Click Map"}</span>
        </button>
      </div>

      {/* ── Active "Pick on Map" Floating Guide Banner ── */}
      {isPickingOnMap && !clickedPoint && (
        <div className="absolute top-16 left-1/2 -translate-x-1/2 z-[1000] bg-[#0B151C]/95 backdrop-blur-md text-white px-4 py-2 rounded-full border border-[#38BDF8]/60 shadow-xl flex items-center gap-2.5 text-xs font-medium animate-in fade-in slide-in-from-top-2 duration-200 pointer-events-auto">
          <span className="flex h-2 w-2 relative">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-[#38BDF8] opacity-75"></span>
            <span className="relative inline-flex rounded-full h-2 w-2 bg-[#38BDF8]"></span>
          </span>
          <span>🎯 Tap or click anywhere on coastal waters to drop pin &amp; set location</span>
          <button
            type="button"
            onClick={() => onTogglePickOnMap(false)}
            className="ml-2 text-slate-400 hover:text-white p-0.5 rounded cursor-pointer"
            title="Cancel map picking"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      )}

      {/* ── Floating Selected Point Confirmation Card (When map is clicked) ── */}
      {clickedPoint && (
        <div className="absolute top-16 left-1/2 -translate-x-1/2 z-[1000] w-[90%] max-w-md bg-[#0B151C]/95 backdrop-blur-md text-white p-3.5 rounded-xl border border-[#38BDF8] shadow-2xl space-y-2.5 animate-in fade-in slide-in-from-top-2 duration-200 pointer-events-auto">
          <div className="flex items-start justify-between gap-2">
            <div className="flex items-center gap-2">
              <div className="p-1.5 rounded-lg bg-[#0284C7]/30 border border-[#0284C7]/60 text-[#38BDF8]">
                <MapPin className="w-4 h-4" />
              </div>
              <div>
                <div className="text-xs font-bold text-slate-100 flex items-center gap-1.5">
                  <span>Selected Marine Point</span>
                  <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-emerald-500/20 text-emerald-300 border border-emerald-500/40">
                    Active Pin
                  </span>
                </div>
                <div className="font-mono text-xs text-[#38BDF8] font-bold mt-0.5">
                  {clickedPoint.lat.toFixed(4)}°N, {clickedPoint.lon.toFixed(4)}°E
                </div>
              </div>
            </div>

            <button
              type="button"
              onClick={onClearClickedPoint}
              className="text-slate-400 hover:text-white p-1 rounded hover:bg-white/10 transition-colors cursor-pointer"
              title="Dismiss selection"
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          <div className="flex items-center gap-2 pt-1 border-t border-slate-700/80">
            <button
              type="button"
              onClick={() => onConfirmClickedPoint(clickedPoint.lat, clickedPoint.lon)}
              disabled={isLoading}
              className="flex-1 px-3 py-1.5 rounded-lg bg-[#0284C7] hover:bg-[#0369A1] text-white text-xs font-semibold flex items-center justify-center gap-1.5 transition-all shadow-xs cursor-pointer active:scale-95 disabled:opacity-50"
            >
              {isLoading ? (
                <>
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  <span>Resolving Marine Data...</span>
                </>
              ) : (
                <>
                  <Check className="w-3.5 h-3.5" />
                  <span>✅ Set as Active Location</span>
                </>
              )}
            </button>

            <button
              type="button"
              onClick={onClearClickedPoint}
              className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-medium transition-colors cursor-pointer"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* ── Manual Location Selection Modal ── */}
      {isManualModalOpen && (
        <div
          className="fixed inset-0 z-[2000] flex items-center justify-center p-3 sm:p-4 bg-slate-900/60 backdrop-blur-xs animate-in fade-in duration-150"
          onClick={() => setIsManualModalOpen(false)}
        >
          <div
            className="relative w-full max-w-lg bg-[var(--surface)] border border-[var(--border)] rounded-2xl shadow-2xl overflow-hidden flex flex-col max-h-[85vh] animate-in zoom-in-95 duration-150"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Modal Header */}
            <div className="p-4 border-b border-[var(--border)] flex items-center justify-between bg-white">
              <div className="flex items-center gap-2">
                <div className="p-2 rounded-xl bg-[var(--foam)] text-[var(--current)]">
                  <Compass className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="font-bold text-sm text-[var(--ink)]">Select Coastal Location</h3>
                  <p className="text-[11px] text-[var(--ink-muted)]">
                    Pick a port, enter GPS coordinates, or tap on map
                  </p>
                </div>
              </div>

              <button
                type="button"
                onClick={() => setIsManualModalOpen(false)}
                className="w-7 h-7 rounded-full hover:bg-[var(--surface-muted)] text-[var(--ink-muted)] hover:text-[var(--ink)] flex items-center justify-center transition-colors cursor-pointer"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Navigation Tabs */}
            <div className="flex items-center border-b border-[var(--border)] bg-[var(--surface-muted)] px-3 pt-2 gap-2 text-xs font-semibold">
              <button
                type="button"
                onClick={() => setActiveTab("search")}
                className={`pb-2 px-3 border-b-2 transition-all cursor-pointer flex items-center gap-1.5 ${
                  activeTab === "search"
                    ? "border-[var(--current)] text-[var(--current)]"
                    : "border-transparent text-[var(--ink-muted)] hover:text-[var(--ink)]"
                }`}
              >
                <Search className="w-3.5 h-3.5" />
                <span>Search Ports</span>
              </button>

              <button
                type="button"
                onClick={() => setActiveTab("coords")}
                className={`pb-2 px-3 border-b-2 transition-all cursor-pointer flex items-center gap-1.5 ${
                  activeTab === "coords"
                    ? "border-[var(--current)] text-[var(--current)]"
                    : "border-transparent text-[var(--ink-muted)] hover:text-[var(--ink)]"
                }`}
              >
                <Sliders className="w-3.5 h-3.5" />
                <span>GPS Coordinates</span>
              </button>

              <button
                type="button"
                onClick={() => setActiveTab("gps")}
                className={`pb-2 px-3 border-b-2 transition-all cursor-pointer flex items-center gap-1.5 ${
                  activeTab === "gps"
                    ? "border-[var(--current)] text-[var(--current)]"
                    : "border-transparent text-[var(--ink-muted)] hover:text-[var(--ink)]"
                }`}
              >
                <Navigation className="w-3.5 h-3.5" />
                <span>Current GPS</span>
              </button>
            </div>

            {/* Modal Body */}
            <div className="p-4 overflow-y-auto space-y-4">
              {/* TAB 1: Search and Popular Coastal Ports */}
              {activeTab === "search" && (
                <div className="space-y-3">
                  <div className="relative">
                    <Search className="absolute left-3 top-2.5 w-4 h-4 text-slate-400" />
                    <input
                      type="text"
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                      placeholder="Search port or coastal harbour (e.g. Kochi, Veraval, Chennai)..."
                      className="w-full bg-white border border-[var(--border)] rounded-xl pl-9 pr-8 py-2 text-xs text-[var(--ink)] placeholder-slate-400 focus:outline-none focus:border-[var(--current)] shadow-2xs"
                      autoFocus
                    />
                    {searchQuery && (
                      <button
                        type="button"
                        onClick={() => setSearchQuery("")}
                        className="absolute right-2.5 top-2.5 text-slate-400 hover:text-slate-600"
                      >
                        <X className="w-3.5 h-3.5" />
                      </button>
                    )}
                  </div>

                  {/* Autocomplete Results */}
                  {isSearching ? (
                    <div className="p-4 text-center text-xs text-slate-400 flex items-center justify-center gap-2">
                      <Loader2 className="w-4 h-4 animate-spin text-[var(--current)]" />
                      <span>Searching coastal gazetteer...</span>
                    </div>
                  ) : searchResults.length > 0 ? (
                    <div className="border border-[var(--border)] rounded-xl divide-y divide-[var(--border)] bg-white max-h-48 overflow-y-auto">
                      {searchResults.map((item, idx) => (
                        <button
                          key={idx}
                          type="button"
                          onClick={() => handleSelectPort(item)}
                          className="w-full text-left px-3 py-2 text-xs hover:bg-[var(--foam)]/40 flex items-center justify-between transition-colors cursor-pointer"
                        >
                          <div>
                            <span className="font-semibold text-slate-800">{item.name}</span>
                            <span className="text-[11px] text-slate-500 ml-1.5">{item.state}</span>
                          </div>
                          <span className="font-mono text-[10px] text-slate-400">
                            {item.lat.toFixed(2)}°, {item.lon.toFixed(2)}°
                          </span>
                        </button>
                      ))}
                    </div>
                  ) : null}

                  {/* Major Coastal Harbours Quick Pills */}
                  <div className="space-y-1.5 pt-1">
                    <span className="text-[10.5px] font-bold uppercase tracking-wider text-slate-400 block">
                      Major Indian Fishing Ports &amp; Landing Centers
                    </span>
                    <div className="flex flex-wrap gap-1.5">
                      {POPULAR_COASTAL_PORTS.map((port) => {
                        const isCurrent =
                          selectedLocation.name.toLowerCase() === port.name.toLowerCase();
                        return (
                          <button
                            key={port.name}
                            type="button"
                            onClick={() => handleSelectPort(port)}
                            className={`px-2.5 py-1 rounded-lg text-xs font-medium border transition-all cursor-pointer flex items-center gap-1 ${
                              isCurrent
                                ? "bg-[var(--current)] text-white border-[var(--current)] font-semibold shadow-2xs"
                                : "bg-white hover:bg-[var(--foam)] border-slate-200 text-slate-700"
                            }`}
                          >
                            <Anchor className="w-3 h-3 opacity-70" />
                            <span>{port.name}</span>
                          </button>
                        );
                      })}
                    </div>
                  </div>
                </div>
              )}

              {/* TAB 2: Direct GPS Lat / Lon Input */}
              {activeTab === "coords" && (
                <form onSubmit={handleApplyCoordinates} className="space-y-3">
                  <p className="text-xs text-slate-500">
                    Manually enter GPS coordinates (decimal degrees) to center the marine chart and calculate offshore conditions.
                  </p>

                  <div className="grid grid-cols-2 gap-3">
                    <div className="space-y-1">
                      <label className="text-[11px] font-bold text-slate-600 block">
                        Latitude (°N / °S)
                      </label>
                      <input
                        type="number"
                        step="any"
                        value={inputLat}
                        onChange={(e) => setInputLat(e.target.value)}
                        placeholder="e.g. 9.9312"
                        className="w-full bg-white border border-[var(--border)] rounded-xl px-3 py-2 text-xs font-mono text-slate-900 focus:outline-none focus:border-[var(--current)]"
                        required
                      />
                      <span className="text-[10px] text-slate-400 block">Between -90.0 and +90.0</span>
                    </div>

                    <div className="space-y-1">
                      <label className="text-[11px] font-bold text-slate-600 block">
                        Longitude (°E / °W)
                      </label>
                      <input
                        type="number"
                        step="any"
                        value={inputLon}
                        onChange={(e) => setInputLon(e.target.value)}
                        placeholder="e.g. 76.2673"
                        className="w-full bg-white border border-[var(--border)] rounded-xl px-3 py-2 text-xs font-mono text-slate-900 focus:outline-none focus:border-[var(--current)]"
                        required
                      />
                      <span className="text-[10px] text-slate-400 block">Between -180.0 and +180.0</span>
                    </div>
                  </div>

                  {coordError && (
                    <div className="p-2 rounded-lg bg-red-50 text-red-700 text-xs border border-red-200">
                      {coordError}
                    </div>
                  )}

                  <div className="pt-2 flex justify-end gap-2">
                    <button
                      type="button"
                      onClick={() => setIsManualModalOpen(false)}
                      className="px-3 py-1.5 rounded-lg border border-slate-200 text-slate-600 text-xs font-medium hover:bg-slate-50"
                    >
                      Cancel
                    </button>
                    <button
                      type="submit"
                      className="px-4 py-1.5 rounded-lg bg-[var(--current)] hover:bg-[#0369A1] text-white text-xs font-semibold flex items-center gap-1.5 shadow-2xs cursor-pointer"
                    >
                      <Check className="w-3.5 h-3.5" />
                      <span>Set Coordinates</span>
                    </button>
                  </div>
                </form>
              )}

              {/* TAB 3: Device Current GPS Position */}
              {activeTab === "gps" && (
                <div className="space-y-4 text-center py-2">
                  <div className="w-12 h-12 rounded-full bg-[var(--foam)] text-[var(--current)] flex items-center justify-center mx-auto shadow-inner">
                    <Navigation className="w-6 h-6" />
                  </div>
                  <div className="space-y-1">
                    <h4 className="font-bold text-sm text-slate-800">Use Real-Time Device Location</h4>
                    <p className="text-xs text-slate-500 max-w-sm mx-auto">
                      Acquires your vessel's high-precision GPS coordinates from your onboard device or smartphone.
                    </p>
                  </div>

                  <button
                    type="button"
                    onClick={handleGetDeviceLocation}
                    disabled={isLocatingGPS}
                    className="px-4 py-2 rounded-xl bg-[var(--current)] hover:bg-[#0369A1] text-white text-xs font-semibold inline-flex items-center gap-2 shadow-xs cursor-pointer active:scale-95 disabled:opacity-50"
                  >
                    {isLocatingGPS ? (
                      <>
                        <Loader2 className="w-4 h-4 animate-spin" />
                        <span>Acquiring GPS Signal...</span>
                      </>
                    ) : (
                      <>
                        <Navigation className="w-4 h-4" />
                        <span>Get Device Coordinates</span>
                      </>
                    )}
                  </button>
                </div>
              )}
            </div>

            {/* Modal Footer: Quick switch to map pick */}
            <div className="p-3 bg-[var(--surface-muted)] border-t border-[var(--border)] flex items-center justify-between text-xs text-slate-500">
              <span>Or pick directly on chart:</span>
              <button
                type="button"
                onClick={() => {
                  setIsManualModalOpen(false);
                  onTogglePickOnMap(true);
                }}
                className="text-[var(--current)] font-semibold hover:underline flex items-center gap-1 cursor-pointer"
              >
                <Crosshair className="w-3.5 h-3.5" />
                <span>Enable Map Click Mode</span>
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
};
