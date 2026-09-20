"use client";

import React, { useEffect, useRef, useState } from "react";
import {
  MapPin,
  Compass,
  X,
  Check,
  Search,
  Navigation,
  Anchor,
  Sliders,
  ArrowRight,
} from "lucide-react";

export interface RoutePoint {
  name: string;
  display_name: string;
  lat: number;
  lon: number;
  state?: string | null;
}

interface Props {
  mode: "start" | "end";
  isOpen: boolean;
  onClose: () => void;
  onSelect: (point: RoutePoint) => void;
  currentPoint?: RoutePoint | null;
  otherPoint?: RoutePoint | null;
}

const POPULAR_PORTS = [
  { name: "Kochi Harbour", state: "Kerala", lat: 9.9312, lon: 76.2673 },
  { name: "Tuticorin (Thoothukudi)", state: "Tamil Nadu", lat: 8.7642, lon: 78.1348 },
  { name: "Rameswaram Port", state: "Tamil Nadu", lat: 9.2876, lon: 79.3129 },
  { name: "Kanyakumari / Wadge Bank", state: "Tamil Nadu", lat: 8.0883, lon: 77.5385 },
  { name: "Mangalore Harbour", state: "Karnataka", lat: 12.9141, lon: 74.856 },
  { name: "Mumbai Sassoon Docks", state: "Maharashtra", lat: 18.9388, lon: 72.8354 },
  { name: "Veraval Fishing Port", state: "Gujarat", lat: 20.9077, lon: 70.3676 },
  { name: "Porbandar Harbour", state: "Gujarat", lat: 21.6417, lon: 69.6293 },
  { name: "Chennai Fishing Harbour", state: "Tamil Nadu", lat: 13.0827, lon: 80.2707 },
  { name: "Visakhapatnam Port", state: "Andhra Pradesh", lat: 17.6868, lon: 83.2185 },
  { name: "Paradip Port", state: "Odisha", lat: 20.2644, lon: 86.6083 },
];

const OFFSHORE_PFZ_PRESETS = [
  { name: "Kochi Shelf Pelagic Grounds", state: "Offshore Shelf", lat: 9.65, lon: 75.85 },
  { name: "Wadge Bank Tuna Grounds", state: "Deep Pelagic", lat: 7.75, lon: 77.3 },
  { name: "Angria Bank Coral Atoll", state: "Offshore Bank", lat: 16.65, lon: 72.05 },
  { name: "Palk Bay Inshore Fairway", state: "Calm Channel", lat: 9.45, lon: 79.15 },
];

export const RouteLocationPickerModal: React.FC<Props> = ({
  mode,
  isOpen,
  onClose,
  onSelect,
  currentPoint,
  otherPoint,
}) => {
  const isStart = mode === "start";
  const title = isStart ? "Select Departure Harbor / Coast" : "Select Destination / Fishing Ground";
  const themeColor = isStart ? "#10B981" : "#EF4444"; // Green for start, Red for end

  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapInstanceRef = useRef<any>(null);
  const pickedMarkerRef = useRef<any>(null);
  const otherMarkerRef = useRef<any>(null);

  const [activeTab, setActiveTab] = useState<"map" | "search" | "coords">("map");

  // Selected point state
  const [selectedLat, setSelectedLat] = useState<number>(currentPoint?.lat || (isStart ? 9.9312 : 9.65));
  const [selectedLon, setSelectedLon] = useState<number>(currentPoint?.lon || (isStart ? 76.2673 : 75.85));
  const [pointName, setPointName] = useState<string>(currentPoint?.name || (isStart ? "Kochi Harbour" : "Target Marine Point"));

  // Manual inputs
  const [inputLat, setInputLat] = useState(String(selectedLat.toFixed(4)));
  const [inputLon, setInputLon] = useState(String(selectedLon.toFixed(4)));
  const [searchFilter, setSearchFilter] = useState("");

  // Sync state whenever modal opens or currentPoint changes
  useEffect(() => {
    if (isOpen) {
      const lat = currentPoint?.lat || (isStart ? 9.9312 : 9.65);
      const lon = currentPoint?.lon || (isStart ? 76.2673 : 75.85);
      const name = currentPoint?.name || (isStart ? "Kochi Harbour" : "Target Marine Point");
      setSelectedLat(lat);
      setSelectedLon(lon);
      setInputLat(String(lat.toFixed(4)));
      setInputLon(String(lon.toFixed(4)));
      setPointName(name);
    }
  }, [isOpen, currentPoint, isStart]);

  // Initialize and update Leaflet Map
  useEffect(() => {
    if (!isOpen) return;

    let map: any;
    let isMounted = true;

    const setupMap = async () => {
      if (!mapContainerRef.current) return;
      const L = (await import("leaflet")).default;
      if (!isMounted) return;

      const centerLat = selectedLat;
      const centerLon = selectedLon;

      map = L.map(mapContainerRef.current, {
        center: [centerLat, centerLon],
        zoom: 8,
        zoomControl: true,
      });

      L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: 18,
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
      }).addTo(map);

      // Active picked pin
      const pinIcon = L.divIcon({
        className: "route-pin-icon",
        html: `
          <div style="position: relative; display: flex; align-items: center; justify-content: center; transform: translate(-50%, -50%);">
            <div style="position: absolute; width: 36px; height: 36px; background: ${isStart ? "rgba(16, 185, 129, 0.35)" : "rgba(239, 68, 68, 0.35)"}; border-radius: 50%; animation: ping 1.5s cubic-bezier(0, 0, 0.2, 1) infinite;"></div>
            <div style="width: 22px; height: 22px; background: ${themeColor}; border: 3px solid white; border-radius: 50%; box-shadow: 0 3px 8px rgba(0,0,0,0.35); display: flex; align-items: center; justify-content: center; color: white; font-size: 10px; font-weight: 800;">
              ${isStart ? "A" : "B"}
            </div>
          </div>
        `,
        iconSize: [36, 36],
        iconAnchor: [0, 0],
      });

      pickedMarkerRef.current = L.marker([centerLat, centerLon], { icon: pinIcon }).addTo(map);

      // Show the other point if already set (e.g. show departure when picking destination)
      if (otherPoint) {
        const otherIcon = L.divIcon({
          className: "other-pin-icon",
          html: `
            <div style="display: flex; align-items: center; justify-content: center; transform: translate(-50%, -50%);">
              <div style="width: 18px; height: 18px; background: ${isStart ? "#EF4444" : "#10B981"}; border: 2px solid white; border-radius: 50%; box-shadow: 0 2px 6px rgba(0,0,0,0.3); display: flex; align-items: center; justify-content: center; color: white; font-size: 9px; font-weight: bold;">
                ${isStart ? "B" : "A"}
              </div>
            </div>
          `,
          iconSize: [24, 24],
          iconAnchor: [0, 0],
        });
        otherMarkerRef.current = L.marker([otherPoint.lat, otherPoint.lon], { icon: otherIcon })
          .bindTooltip(`${isStart ? "Destination" : "Departure"}: ${otherPoint.name}`, { permanent: false })
          .addTo(map);
      }

      // Click to pick location
      map.on("click", (e: any) => {
        const lat = Number(e.latlng.lat.toFixed(4));
        const lon = Number(e.latlng.lng.toFixed(4));

        setSelectedLat(lat);
        setSelectedLon(lon);
        setInputLat(String(lat));
        setInputLon(String(lon));
        setPointName(`${lat.toFixed(2)}°N, ${lon.toFixed(2)}°E`);

        if (pickedMarkerRef.current) {
          pickedMarkerRef.current.setLatLng([lat, lon]);
        }
      });

      mapInstanceRef.current = map;

      // Invalidate size after modal render animation completes
      setTimeout(() => {
        map.invalidateSize();
      }, 150);
    };

    setupMap();

    return () => {
      isMounted = false;
      if (map) {
        map.remove();
        mapInstanceRef.current = null;
      }
    };
  }, [isOpen, mode]);

  if (!isOpen) return null;

  // Confirm selection
  const handleConfirm = () => {
    onSelect({
      name: pointName,
      display_name: `${pointName} (${selectedLat.toFixed(2)}°N, ${selectedLon.toFixed(2)}°E)`,
      lat: selectedLat,
      lon: selectedLon,
    });
    onClose();
  };

  // Preset port selection
  const handleSelectPreset = (p: { name: string; state?: string; lat: number; lon: number }) => {
    setSelectedLat(p.lat);
    setSelectedLon(p.lon);
    setInputLat(String(p.lat));
    setInputLon(String(p.lon));
    setPointName(p.name);

    if (mapInstanceRef.current) {
      mapInstanceRef.current.setView([p.lat, p.lon], 9);
      if (pickedMarkerRef.current) {
        pickedMarkerRef.current.setLatLng([p.lat, p.lon]);
      }
    }
  };

  // Apply manual lat/lon
  const handleApplyManualCoords = (e: React.FormEvent) => {
    e.preventDefault();
    const lat = parseFloat(inputLat);
    const lon = parseFloat(inputLon);
    if (!isNaN(lat) && !isNaN(lon)) {
      setSelectedLat(lat);
      setSelectedLon(lon);
      setPointName(`${lat.toFixed(2)}°N, ${lon.toFixed(2)}°E`);
      if (mapInstanceRef.current) {
        mapInstanceRef.current.setView([lat, lon], 9);
        if (pickedMarkerRef.current) {
          pickedMarkerRef.current.setLatLng([lat, lon]);
        }
      }
    }
  };

  const filteredPorts = POPULAR_PORTS.filter(
    (p) =>
      p.name.toLowerCase().includes(searchFilter.toLowerCase()) ||
      (p.state && p.state.toLowerCase().includes(searchFilter.toLowerCase()))
  );

  // Do not render any modal DOM when closed to prevent SSR hydration mismatches
  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-[2000] flex items-center justify-center p-3 sm:p-4 bg-slate-900/65 backdrop-blur-xs animate-in fade-in duration-150"
      onClick={onClose}
    >
      <div
        className="relative w-full max-w-2xl bg-white border border-[var(--border)] rounded-2xl shadow-2xl overflow-hidden flex flex-col max-h-[90vh] animate-in zoom-in-95 duration-150"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="p-4 border-b border-[var(--border)] flex items-center justify-between bg-slate-50">
          <div className="flex items-center gap-2.5">
            <div
              className="w-8 h-8 rounded-xl flex items-center justify-center text-white font-bold text-xs shadow-xs"
              style={{ backgroundColor: themeColor }}
            >
              {isStart ? "A" : "B"}
            </div>
            <div>
              <h3 className="font-bold text-sm sm:text-base text-slate-900">{title}</h3>
              <p className="text-[11px] text-slate-500">
                {isStart
                  ? "Click on map or choose a harbor where your vessel will depart"
                  : "Click on coastal waters or fishing grounds to target safe route destination"}
              </p>
            </div>
          </div>

          <button
            type="button"
            onClick={onClose}
            className="w-7 h-7 rounded-full hover:bg-slate-200 text-slate-500 hover:text-slate-800 flex items-center justify-center transition-colors cursor-pointer"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Tab Switcher */}
        <div className="flex items-center border-b border-[var(--border)] bg-white px-3 pt-2 gap-2 text-xs font-semibold">
          <button
            type="button"
            onClick={() => setActiveTab("map")}
            className={`pb-2 px-3 border-b-2 transition-all cursor-pointer flex items-center gap-1.5 ${
              activeTab === "map"
                ? "border-[#0C6E8C] text-[#0C6E8C]"
                : "border-transparent text-slate-500 hover:text-slate-800"
            }`}
          >
            <Compass className="w-3.5 h-3.5" />
            <span>Click on Chart</span>
          </button>

          <button
            type="button"
            onClick={() => setActiveTab("search")}
            className={`pb-2 px-3 border-b-2 transition-all cursor-pointer flex items-center gap-1.5 ${
              activeTab === "search"
                ? "border-[#0C6E8C] text-[#0C6E8C]"
                : "border-transparent text-slate-500 hover:text-slate-800"
            }`}
          >
            <Anchor className="w-3.5 h-3.5" />
            <span>Popular Harbours</span>
          </button>

          <button
            type="button"
            onClick={() => setActiveTab("coords")}
            className={`pb-2 px-3 border-b-2 transition-all cursor-pointer flex items-center gap-1.5 ${
              activeTab === "coords"
                ? "border-[#0C6E8C] text-[#0C6E8C]"
                : "border-transparent text-slate-500 hover:text-slate-800"
            }`}
          >
            <Sliders className="w-3.5 h-3.5" />
            <span>Direct Lat / Lon</span>
          </button>
        </div>

        {/* Modal Body */}
        <div className="flex-1 overflow-hidden flex flex-col">
          {/* TAB 1: Map View */}
          <div className={`relative w-full h-[360px] sm:h-[400px] ${activeTab !== "map" ? "hidden" : "block"}`}>
            <div ref={mapContainerRef} className="w-full h-full cursor-crosshair" />

            {/* Instruction Overlay Tag */}
            <div className="absolute top-3 left-3 z-[1000] bg-slate-900/90 backdrop-blur-xs text-white px-3 py-1.5 rounded-lg text-xs font-medium border border-white/20 shadow-md flex items-center gap-1.5 pointer-events-none">
              <span className="w-2 h-2 rounded-full animate-ping" style={{ backgroundColor: themeColor }} />
              <span>🎯 Tap anywhere on water to place {isStart ? "Departure" : "Destination"} pin</span>
            </div>
          </div>

          {/* TAB 2: Search Ports & Offshore Grounds */}
          {activeTab === "search" && (
            <div className="p-4 overflow-y-auto space-y-4 max-h-[380px]">
              <div className="relative">
                <Search className="absolute left-3 top-2.5 w-4 h-4 text-slate-400" />
                <input
                  type="text"
                  value={searchFilter}
                  onChange={(e) => setSearchFilter(e.target.value)}
                  placeholder="Filter coastal harbours and ports..."
                  className="w-full bg-slate-50 border border-slate-200 rounded-xl pl-9 pr-3 py-2 text-xs text-slate-900 placeholder-slate-400 focus:outline-none focus:border-[#0C6E8C]"
                  autoFocus
                />
              </div>

              {/* Offshore Fishing Grounds Section */}
              {!isStart && (
                <div className="space-y-1.5">
                  <span className="text-[10.5px] font-bold text-cyan-700 uppercase tracking-wider block">
                    🐟 Target Offshore Fishing Grounds (PFZ)
                  </span>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-1.5">
                    {OFFSHORE_PFZ_PRESETS.map((zone) => (
                      <button
                        key={zone.name}
                        type="button"
                        onClick={() => {
                          handleSelectPreset(zone);
                          setActiveTab("map");
                        }}
                        className="p-2.5 rounded-xl border border-cyan-200 bg-cyan-50/50 hover:bg-cyan-100/70 text-left transition-all cursor-pointer flex items-center justify-between"
                      >
                        <div>
                          <div className="text-xs font-bold text-cyan-900">{zone.name}</div>
                          <div className="text-[10px] text-cyan-600">{zone.state}</div>
                        </div>
                        <span className="font-mono text-[10px] text-cyan-700">
                          {zone.lat.toFixed(2)}°, {zone.lon.toFixed(2)}°
                        </span>
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {/* Major Coastal Harbours */}
              <div className="space-y-1.5">
                <span className="text-[10.5px] font-bold text-slate-500 uppercase tracking-wider block">
                  Major Indian Coastal Harbours
                </span>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-1.5">
                  {filteredPorts.map((port) => {
                    const isSelected = selectedLat === port.lat && selectedLon === port.lon;
                    return (
                      <button
                        key={port.name}
                        type="button"
                        onClick={() => {
                          handleSelectPreset(port);
                          setActiveTab("map");
                        }}
                        className={`p-2.5 rounded-xl border text-left transition-all cursor-pointer flex items-center justify-between ${
                          isSelected
                            ? "border-[#0C6E8C] bg-[#0C6E8C]/10 ring-1 ring-[#0C6E8C]"
                            : "border-slate-200 bg-white hover:bg-slate-50"
                        }`}
                      >
                        <div>
                          <div className="text-xs font-semibold text-slate-800">{port.name}</div>
                          <div className="text-[10px] text-slate-400">{port.state}</div>
                        </div>
                        <span className="font-mono text-[10px] text-slate-400">
                          {port.lat.toFixed(2)}°, {port.lon.toFixed(2)}°
                        </span>
                      </button>
                    );
                  })}
                </div>
              </div>
            </div>
          )}

          {/* TAB 3: Direct Lat / Lon Input */}
          {activeTab === "coords" && (
            <div className="p-4 space-y-4 max-h-[380px]">
              <p className="text-xs text-slate-600">
                Type exact decimal GPS coordinates (e.g. from marine chart or GPS plotter) to set this waypoint.
              </p>

              <form onSubmit={handleApplyManualCoords} className="space-y-3">
                <div className="grid grid-cols-2 gap-3">
                  <div className="space-y-1">
                    <label className="text-[11px] font-bold text-slate-600 block">Latitude (°N / °S)</label>
                    <input
                      type="number"
                      step="any"
                      value={inputLat}
                      onChange={(e) => setInputLat(e.target.value)}
                      placeholder="e.g. 9.9312"
                      className="w-full bg-slate-50 border border-slate-200 rounded-xl px-3 py-2 text-xs font-mono text-slate-900 focus:outline-none focus:border-[#0C6E8C]"
                      required
                    />
                  </div>
                  <div className="space-y-1">
                    <label className="text-[11px] font-bold text-slate-600 block">Longitude (°E / °W)</label>
                    <input
                      type="number"
                      step="any"
                      value={inputLon}
                      onChange={(e) => setInputLon(e.target.value)}
                      placeholder="e.g. 76.2673"
                      className="w-full bg-slate-50 border border-slate-200 rounded-xl px-3 py-2 text-xs font-mono text-slate-900 focus:outline-none focus:border-[#0C6E8C]"
                      required
                    />
                  </div>
                </div>

                <button
                  type="submit"
                  className="w-full py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-white text-xs font-semibold flex items-center justify-center gap-1.5 transition-colors"
                >
                  <Check className="w-3.5 h-3.5" />
                  <span>Update Point on Chart</span>
                </button>
              </form>
            </div>
          )}
        </div>

        {/* Footer: Active Point Info & Confirm Action */}
        <div className="p-3.5 bg-slate-50 border-t border-[var(--border)] flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <div
              className="w-3 h-3 rounded-full shrink-0"
              style={{ backgroundColor: themeColor }}
            />
            <div>
              <div className="text-xs font-bold text-slate-900 flex items-center gap-1.5">
                <span>{pointName}</span>
              </div>
              <div className="font-mono text-[11px] text-slate-500">
                {selectedLat.toFixed(4)}°N, {selectedLon.toFixed(4)}°E
              </div>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={onClose}
              className="px-3 py-1.5 rounded-lg border border-slate-200 text-slate-600 text-xs font-medium hover:bg-slate-100"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={handleConfirm}
              className="px-4 py-1.5 rounded-lg text-white text-xs font-semibold flex items-center gap-1.5 shadow-xs cursor-pointer active:scale-95 transition-all"
              style={{ backgroundColor: themeColor }}
            >
              <Check className="w-3.5 h-3.5" />
              <span>Use as {isStart ? "Departure" : "Destination"}</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
