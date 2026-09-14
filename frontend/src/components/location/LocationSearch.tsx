"use client";

import React, { useState, useEffect, useRef } from "react";
import { useLocation } from "@/lib/locationContext";
import { LocationSearchResult } from "@/lib/types";

interface LocationSearchProps {
  onSelect?: () => void;
  autoFocus?: boolean;
}

const POPULAR_PORTS = [
  { name: "Kochi", state: "Kerala", lat: 9.9312, lon: 76.2673 },
  { name: "Mumbai", state: "Maharashtra", lat: 18.9388, lon: 72.8354 },
  { name: "Chennai", state: "Tamil Nadu", lat: 13.0827, lon: 80.2707 },
  { name: "Visakhapatnam", state: "Andhra Pradesh", lat: 17.6868, lon: 83.2185 },
  { name: "Rameswaram", state: "Tamil Nadu", lat: 9.2876, lon: 79.3129 },
  { name: "Mangalore", state: "Karnataka", lat: 12.9141, lon: 74.8560 },
  { name: "Porbandar", state: "Gujarat", lat: 21.6417, lon: 69.6293 },
  { name: "Paradip", state: "Odisha", lat: 20.2644, lon: 86.6083 },
];

export function LocationSearch({ onSelect, autoFocus = false }: LocationSearchProps) {
  const { searchLocations, setLocation, recentLocations } = useLocation();
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<LocationSearchResult[]>([]);
  const [searching, setSearching] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (autoFocus && inputRef.current) {
      inputRef.current.focus();
    }
  }, [autoFocus]);

  useEffect(() => {
    const q = query.trim();
    if (!q) {
      setResults([]);
      setSearching(false);
      return;
    }

    const timer = setTimeout(async () => {
      setSearching(true);
      try {
        const res = await searchLocations(q);
        setResults(res);
      } catch (err) {
        console.error("Search error:", err);
      } finally {
        setSearching(false);
      }
    }, 250);

    return () => clearTimeout(timer);
  }, [query, searchLocations]);

  const handleSelect = async (item: LocationSearchResult) => {
    await setLocation({
      name: item.name,
      display_name: item.display_name,
      lat: item.lat,
      lon: item.lon,
      state: item.state,
      country: item.country || "India",
      source: "search",
    });
    setQuery("");
    setResults([]);
    if (onSelect) onSelect();
  };

  return (
    <div className="w-full flex flex-col gap-3">
      <div className="relative">
        <input
          ref={inputRef}
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search Indian port, coastal town, or city..."
          className="w-full bg-stone-900 border border-stone-700 rounded-xl px-10 py-2.5 text-sm text-stone-100 placeholder-stone-400 focus:outline-none focus:border-amber-400 focus:ring-1 focus:ring-amber-400 transition-all"
        />
        <svg
          className="absolute left-3.5 top-3 w-4 h-4 text-stone-400"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
          />
        </svg>
        {query && (
          <button
            onClick={() => setQuery("")}
            className="absolute right-3 top-2.5 text-stone-400 hover:text-stone-200 text-sm p-0.5"
          >
            ✕
          </button>
        )}
      </div>

      {/* Autocomplete Results */}
      {searching && (
        <div className="p-3 text-center text-xs text-stone-400 flex items-center justify-center gap-2">
          <span className="w-3.5 h-3.5 border-2 border-amber-400 border-t-transparent rounded-full animate-spin" />
          Searching ports & locations...
        </div>
      )}

      {results.length > 0 && (
        <div className="max-h-60 overflow-y-auto rounded-xl border border-stone-700/80 bg-stone-900/95 divide-y divide-stone-800 shadow-xl">
          {results.map((r, idx) => (
            <button
              key={`${r.name}-${r.lat}-${idx}`}
              onClick={() => handleSelect(r)}
              className="w-full text-left px-4 py-2.5 hover:bg-stone-800/90 transition-colors flex items-center justify-between group"
            >
              <div>
                <div className="text-sm font-medium text-stone-100 group-hover:text-amber-300 transition-colors">
                  {r.name}
                </div>
                <div className="text-xs text-stone-400 truncate max-w-xs">{r.display_name}</div>
              </div>
              <div className="text-[11px] text-stone-400 font-mono">
                {r.lat.toFixed(2)}°, {r.lon.toFixed(2)}°
              </div>
            </button>
          ))}
        </div>
      )}

      {query && !searching && results.length === 0 && (
        <div className="p-3 text-center text-xs text-stone-400 bg-stone-900/50 rounded-lg border border-stone-800">
          No matches found for &quot;{query}&quot;. Try selecting on map or searching a nearby harbor.
        </div>
      )}

      {/* Recent Locations */}
      {!query && recentLocations.length > 0 && (
        <div>
          <div className="text-[11px] font-semibold text-stone-400 uppercase tracking-wider mb-1.5 flex items-center gap-1">
            <span>🕒</span> Recent Locations
          </div>
          <div className="flex flex-wrap gap-1.5">
            {recentLocations.map((loc) => (
              <button
                key={`${loc.name}-${loc.lat}`}
                onClick={() => {
                  setLocation(loc);
                  if (onSelect) onSelect();
                }}
                className="px-2.5 py-1 text-xs rounded-lg bg-stone-800 border border-stone-700 hover:border-amber-400 hover:text-amber-200 text-stone-300 transition-all flex items-center gap-1"
              >
                <span>📍</span>
                <span>{loc.name}</span>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Popular Coastal Ports Quick Picks */}
      {!query && (
        <div>
          <div className="text-[11px] font-semibold text-stone-400 uppercase tracking-wider mb-1.5 flex items-center gap-1">
            <span>⚓</span> Major Coastal Ports
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-1.5">
            {POPULAR_PORTS.map((p) => (
              <button
                key={p.name}
                onClick={() => {
                  setLocation({
                    name: p.name,
                    display_name: `${p.name}, ${p.state}, India`,
                    lat: p.lat,
                    lon: p.lon,
                    state: p.state,
                    country: "India",
                    source: "search",
                  });
                  if (onSelect) onSelect();
                }}
                className="px-2.5 py-1.5 text-xs text-left rounded-lg bg-stone-900/70 border border-stone-800 hover:border-amber-400 hover:bg-stone-800/80 transition-all group"
              >
                <div className="font-medium text-stone-200 group-hover:text-amber-300">{p.name}</div>
                <div className="text-[10px] text-stone-400">{p.state}</div>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
