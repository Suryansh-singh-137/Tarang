"use client";

import React, { useState } from "react";
import { Navigation, Loader2 } from "lucide-react";
import { useLocation } from "@/lib/locationContext";

interface CurrentLocationButtonProps {
  className?: string;
  onSuccess?: () => void;
}

export function CurrentLocationButton({ className = "", onSuccess }: CurrentLocationButtonProps) {
  const { selectCoordinates } = useLocation();
  const [locating, setLocating] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const handleGetLocation = () => {
    if (!navigator.geolocation) {
      setErrorMsg("Geolocation is not supported by your browser");
      return;
    }

    setLocating(true);
    setErrorMsg(null);

    navigator.geolocation.getCurrentPosition(
      async (pos) => {
        try {
          const lat = pos.coords.latitude;
          const lon = pos.coords.longitude;
          await selectCoordinates(lat, lon, undefined, "gps");
          if (onSuccess) onSuccess();
        } catch (e: any) {
          setErrorMsg(e?.message || "Failed to resolve coordinates");
        } finally {
          setLocating(false);
        }
      },
      (err) => {
        setLocating(false);
        if (err.code === err.PERMISSION_DENIED) {
          setErrorMsg("Location permission denied in browser settings.");
        } else if (err.code === err.POSITION_UNAVAILABLE) {
          setErrorMsg("Location unavailable. Try search or map picker.");
        } else {
          setErrorMsg("Location request timed out.");
        }
      },
      { enableHighAccuracy: true, timeout: 10000, maximumAge: 60000 }
    );
  };

  return (
    <div className="flex flex-col gap-1">
      <button
        onClick={handleGetLocation}
        disabled={locating}
        type="button"
        className={`inline-flex items-center justify-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-sans font-medium border transition-all cursor-pointer shadow-2xs ${
          locating
            ? "border-[var(--current)]/50 bg-[var(--foam)] text-[var(--current)] animate-pulse"
            : "border-[var(--border)] bg-[var(--surface)] hover:bg-[var(--foam)] text-[var(--ink)] hover:border-[var(--current)]/40 hover:text-[var(--current)]"
        } ${className}`}
      >
        {locating ? (
          <Loader2 className="w-3.5 h-3.5 animate-spin text-[var(--current)]" />
        ) : (
          <Navigation className="w-3.5 h-3.5 text-[var(--current)]" />
        )}
        <span>{locating ? "Acquiring GPS..." : "Current Location (GPS)"}</span>
      </button>
      {errorMsg && <p className="text-[10px] text-[#DC2626] font-mono-data px-1">{errorMsg}</p>}
    </div>
  );
}
