"use client";

import React, { useEffect, useRef, useState } from "react";
import { useLocation } from "@/lib/locationContext";
import { MarineContextBadge } from "./MarineContextBadge";
import { MarineContextType } from "@/lib/types";

interface LocationMapPickerProps {
  onClose: () => void;
}

export function LocationMapPicker({ onClose }: LocationMapPickerProps) {
  const { selectedLocation, selectCoordinates, isLoading } = useLocation();
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapInstanceRef = useRef<any>(null);
  const markerRef = useRef<any>(null);

  const [pin, setPin] = useState<{ lat: number; lon: number }>({
    lat: selectedLocation?.lat || 9.9312,
    lon: selectedLocation?.lon || 76.2673,
  });
  const [pinContextType, setPinContextType] = useState<MarineContextType>("coastal");
  const [manualLat, setManualLat] = useState(String(selectedLocation?.lat || "9.9312"));
  const [manualLon, setManualLon] = useState(String(selectedLocation?.lon || "76.2673"));
  const [pinName, setPinName] = useState<string>(selectedLocation?.name || "Selected Position");

  // Dynamic Leaflet initialization
  useEffect(() => {
    let isCancelled = false;
    let map: any;

    async function setupMap() {
      if (!mapContainerRef.current) return;
      const L = (await import("leaflet")).default;
      if (isCancelled) return;

      const initialLat = selectedLocation?.lat || 9.9312;
      const initialLon = selectedLocation?.lon || 76.2673;

      map = L.map(mapContainerRef.current, {
        center: [initialLat, initialLon],
        zoom: 7,
        zoomControl: true,
      });

      L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: 18,
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
      }).addTo(map);

      // Custom icon
      const pinIcon = L.divIcon({
        className: "custom-map-pin",
        html: `<div style="transform: translate(-50%, -100%); display: flex; flex-direction: column; align-items: center;">
          <div style="background-color: #f59e0b; color: #1c1917; width: 26px; height: 26px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: bold; border: 2px solid white; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.5);">📍</div>
          <div style="width: 2px; height: 8px; background-color: #f59e0b;"></div>
        </div>`,
        iconSize: [26, 34],
        iconAnchor: [13, 34],
      });

      const marker = L.marker([initialLat, initialLon], { icon: pinIcon }).addTo(map);
      markerRef.current = marker;
      mapInstanceRef.current = map;

      // Handle map clicks
      map.on("click", (e: any) => {
        const { lat, lng } = e.latlng;
        const boundedLat = Number(lat.toFixed(4));
        const boundedLon = Number(lng.toFixed(4));

        marker.setLatLng([boundedLat, boundedLon]);
        setPin({ lat: boundedLat, lon: boundedLon });
        setManualLat(String(boundedLat));
        setManualLon(String(boundedLon));

        // Approximate local marine context for responsive instant feedback
        if (boundedLat > 24.5) {
          setPinContextType("inland");
          setPinName(`Coordinates (${boundedLat}°, ${boundedLon}°)`);
        } else if (
          (boundedLon > 80.3 && boundedLat < 22) ||
          (boundedLon < 73.0 && boundedLat < 21) ||
          boundedLat < 8.1
        ) {
          setPinContextType("offshore");
          setPinName(`${boundedLat.toFixed(2)}°N, ${boundedLon.toFixed(2)}°E`);
        } else {
          setPinContextType("coastal");
          setPinName(`Position (${boundedLat}°, ${boundedLon}°)`);
        }
      });
    }

    setupMap();

    return () => {
      isCancelled = true;
      if (map) {
        map.remove();
      }
    };
  }, []);

  const handleManualCoordSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const lat = parseFloat(manualLat);
    const lon = parseFloat(manualLon);
    if (isNaN(lat) || isNaN(lon)) return;

    setPin({ lat, lon });
    if (markerRef.current && mapInstanceRef.current) {
      markerRef.current.setLatLng([lat, lon]);
      mapInstanceRef.current.setView([lat, lon], 8);
    }
  };

  const handleConfirmLocation = async () => {
    await selectCoordinates(pin.lat, pin.lon, undefined, "map");
    onClose();
  };

  return (
    <div className="flex flex-col h-full w-full">
      {/* Top instruction bar */}
      <div className="p-3 bg-stone-900 border-b border-stone-800 flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold text-stone-100">Click anywhere on the map or enter coordinates</span>
          <MarineContextBadge type={pinContextType} size="sm" />
        </div>

        {/* Direct coordinate input */}
        <form onSubmit={handleManualCoordSubmit} className="flex items-center gap-1.5 text-xs">
          <input
            type="text"
            value={manualLat}
            onChange={(e) => setManualLat(e.target.value)}
            placeholder="Lat"
            className="w-16 px-2 py-1 bg-stone-800 border border-stone-700 rounded text-stone-200 font-mono text-center focus:border-amber-400 focus:outline-none"
          />
          <span className="text-stone-400">,</span>
          <input
            type="text"
            value={manualLon}
            onChange={(e) => setManualLon(e.target.value)}
            placeholder="Lon"
            className="w-16 px-2 py-1 bg-stone-800 border border-stone-700 rounded text-stone-200 font-mono text-center focus:border-amber-400 focus:outline-none"
          />
          <button
            type="submit"
            className="px-2 py-1 bg-stone-700 hover:bg-stone-600 rounded text-stone-200 text-xs transition-colors"
          >
            Go
          </button>
        </form>
      </div>

      {/* Map container */}
      <div className="relative flex-1 min-h-[380px] w-full bg-stone-950">
        <div ref={mapContainerRef} className="w-full h-full" />
      </div>

      {/* Footer with confirmation */}
      <div className="p-3 bg-stone-900 border-t border-stone-800 flex items-center justify-between gap-3">
        <div className="flex flex-col text-xs">
          <span className="font-semibold text-stone-200">{pinName}</span>
          <span className="text-stone-400 font-mono text-[11px]">
            {pin.lat.toFixed(4)}° N, {pin.lon.toFixed(4)}° E
          </span>
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={onClose}
            className="px-3 py-1.5 rounded-lg border border-stone-700 text-stone-300 hover:bg-stone-800 text-xs transition-colors"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={handleConfirmLocation}
            disabled={isLoading}
            className="px-4 py-1.5 rounded-lg bg-amber-400 hover:bg-amber-300 text-stone-950 font-semibold text-xs transition-colors flex items-center gap-1.5 shadow-md"
          >
            {isLoading ? "Resolving..." : "Select this location"}
          </button>
        </div>
      </div>
    </div>
  );
}
