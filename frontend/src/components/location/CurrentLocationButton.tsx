"use client";

import React, { useState } from "react";
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
          setErrorMsg("Location permission denied. Please allow access in browser settings.");
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
        className={`inline-flex items-center justify-center gap-2 px-3 py-2 rounded-xl text-xs font-semibold border transition-all ${
          locating
            ? "border-amber-500/50 bg-amber-500/10 text-amber-300 animate-pulse cursor-wait"
            : "border-stone-700 bg-stone-800/80 hover:bg-stone-700/80 text-stone-200 hover:text-white hover:border-amber-500/50"
        } ${className}`}
      >
        <svg
          className={`w-3.5 h-3.5 text-amber-400 ${locating ? "animate-spin" : ""}`}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          {locating ? (
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
            />
          ) : (
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z"
            />
          )}
        </svg>
        <span>{locating ? "Acquiring GPS..." : "Use Current Location (GPS)"}</span>
      </button>
      {errorMsg && <p className="text-[10px] text-rose-400 px-1">{errorMsg}</p>}
    </div>
  );
}
