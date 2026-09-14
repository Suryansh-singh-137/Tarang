"use client";

import React, { useEffect, useRef, useState } from "react";
import { useLocation } from "@/lib/locationContext";
import { MarineContextBadge } from "./MarineContextBadge";
import { MarineContextType } from "@/lib/types";
import { Check, Loader2 } from "lucide-react";

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

      // Custom editorial pin matching Coastal Dawn
      const pinIcon = L.divIcon({
        className: "custom-map-pin",
        html: `<div style="transform: translate(-50%, -100%); display: flex; flex-direction: column; align-items: center;">
          <div style="background-color: #2E8FA0; color: white; width: 28px; height: 28px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 13px; border: 2.5px solid white; box-shadow: 0 4px 8px rgba(22, 36, 43, 0.25);">📍</div>
          <div style="width: 2px; height: 6px; background-color: #2E8FA0;"></div>
        </div>`,
        iconSize: [28, 34],
        iconAnchor: [14, 34],
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
    <div className="flex flex-col h-full w-full bg-[var(--surface)]">
      {/* Top instruction bar */}
      <div className="p-3.5 bg-[var(--surface-muted)] border-b border-[var(--border)] flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <span className="text-xs font-medium text-[var(--ink)]">
            Click anywhere on open sea or mainland to place pin
          </span>
          <MarineContextBadge type={pinContextType} size="sm" />
        </div>

        {/* Direct coordinate input */}
        <form onSubmit={handleManualCoordSubmit} className="flex items-center gap-1.5 text-xs">
          <input
            type="text"
            value={manualLat}
            onChange={(e) => setManualLat(e.target.value)}
            placeholder="Lat"
            className="w-16 px-2 py-1 bg-[var(--surface)] border border-[var(--border)] rounded text-[var(--ink)] font-mono-data text-center focus:border-[var(--current)] focus:outline-none"
          />
          <span className="text-[var(--ink-muted)]">,</span>
          <input
            type="text"
            value={manualLon}
            onChange={(e) => setManualLon(e.target.value)}
            placeholder="Lon"
            className="w-16 px-2 py-1 bg-[var(--surface)] border border-[var(--border)] rounded text-[var(--ink)] font-mono-data text-center focus:border-[var(--current)] focus:outline-none"
          />
          <button
            type="submit"
            className="px-2.5 py-1 bg-[var(--surface)] hover:bg-[var(--foam)] text-[var(--ink)] border border-[var(--border)] rounded text-xs font-mono-data transition-colors cursor-pointer"
          >
            Go
          </button>
        </form>
      </div>

      {/* Map container */}
      <div className="relative flex-1 min-h-[380px] w-full bg-[#E2ECEE]">
        <div ref={mapContainerRef} className="w-full h-full" />
      </div>

      {/* Footer with confirmation */}
      <div className="p-3.5 bg-[var(--surface)] border-t border-[var(--border)] flex items-center justify-between gap-3">
        <div className="flex flex-col text-xs">
          <span className="font-semibold text-[var(--ink)]">{pinName}</span>
          <span className="text-[var(--ink-muted)] font-mono-data text-[11px]">
            {pin.lat.toFixed(4)}° N, {pin.lon.toFixed(4)}° E
          </span>
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={onClose}
            className="px-3.5 py-1.5 rounded-full border border-[var(--border)] text-[var(--ink-muted)] hover:text-[var(--ink)] hover:bg-[var(--surface-muted)] text-xs font-sans font-medium transition-colors cursor-pointer"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={handleConfirmLocation}
            disabled={isLoading}
            className="px-4 py-1.5 rounded-full bg-[var(--ink)] hover:bg-[var(--current)] text-white font-sans font-medium text-xs transition-colors flex items-center gap-1.5 shadow-xs cursor-pointer"
          >
            {isLoading ? (
              <>
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
                <span>Resolving...</span>
              </>
            ) : (
              <>
                <Check className="w-3.5 h-3.5" />
                <span>Select this location</span>
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
