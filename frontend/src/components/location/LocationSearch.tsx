"use client";

import React, { useState, useEffect, useRef } from "react";
import { Search, X, Loader2, Clock, Anchor, MapPin } from "lucide-react";
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
    <div className="w-full flex flex-col gap-4">
      {/* Search Input */}
      <div className="relative">
        <input
          ref={inputRef}
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search Indian port, coastal town, or city..."
          className="w-full bg-[var(--surface)] border border-[var(--border)] rounded-xl px-10 py-2.5 text-sm text-[var(--ink)] placeholder-[var(--ink-subtle)] focus:outline-none focus:border-[var(--current)] focus:ring-1 focus:ring-[var(--current)] transition-all shadow-2xs"
        />
        <Search className="absolute left-3.5 top-3 w-4 h-4 text-[var(--ink-subtle)]" />
        {query && (
          <button
            type="button"
            onClick={() => setQuery("")}
            className="absolute right-3 top-2.5 text-[var(--ink-muted)] hover:text-[var(--ink)] p-0.5 rounded cursor-pointer"
          >
            <X className="w-4 h-4" />
          </button>
        )}
      </div>

      {/* Searching State */}
      {searching && (
        <div className="p-3 text-center text-xs text-[var(--ink-muted)] flex items-center justify-center gap-2">
          <Loader2 className="w-3.5 h-3.5 text-[var(--current)] animate-spin" />
          <span>Searching ports & locations...</span>
        </div>
      )}

      {/* Autocomplete Results */}
      {results.length > 0 && (
        <div className="max-h-60 overflow-y-auto rounded-xl border border-[var(--border)] bg-[var(--surface)] divide-y divide-[var(--border)] shadow-md">
          {results.map((r, idx) => (
            <button
              key={`${r.name}-${r.lat}-${idx}`}
              type="button"
              onClick={() => handleSelect(r)}
              className="w-full text-left px-4 py-2.5 hover:bg-[var(--foam)]/50 transition-colors flex items-center justify-between group cursor-pointer"
            >
              <div>
                <div className="text-sm font-medium text-[var(--ink)] group-hover:text-[var(--current)] transition-colors">
                  {r.name}
                </div>
                <div className="text-xs text-[var(--ink-muted)] truncate max-w-xs">{r.display_name}</div>
              </div>
              <div className="text-[11px] text-[var(--ink-subtle)] font-mono-data">
                {r.lat.toFixed(2)}°, {r.lon.toFixed(2)}°
              </div>
            </button>
          ))}
        </div>
      )}

      {/* No Results Message */}
      {query && !searching && results.length === 0 && (
        <div className="p-3.5 text-center text-xs text-[var(--ink-muted)] bg-[var(--surface-muted)] rounded-xl border border-[var(--border)]">
          No matches found for &ldquo;{query}&rdquo;. Try picking coordinates on the map or searching a nearby harbor.
        </div>
      )}

      {/* Recent Locations */}
      {!query && recentLocations.length > 0 && (
        <div>
          <div className="text-[10px] font-mono-data font-medium text-[var(--ink-subtle)] uppercase tracking-wider mb-2 flex items-center gap-1.5">
            <Clock className="w-3 h-3 text-[var(--current)]" />
            <span>Recent Locations</span>
          </div>
          <div className="flex flex-wrap gap-1.5">
            {recentLocations.map((loc) => (
              <button
                key={`${loc.name}-${loc.lat}`}
                type="button"
                onClick={() => {
                  setLocation(loc);
                  if (onSelect) onSelect();
                }}
                className="px-3 py-1 text-xs rounded-full bg-[var(--surface)] border border-[var(--border)] hover:border-[var(--current)]/40 hover:bg-[var(--foam)] text-[var(--ink)] transition-all font-mono-data flex items-center gap-1.5 cursor-pointer shadow-2xs"
              >
                <MapPin className="w-3 h-3 text-[var(--current)]" />
                <span>{loc.name}</span>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Major Coastal Ports Quick Picks */}
      {!query && (
        <div>
          <div className="text-[10px] font-mono-data font-medium text-[var(--ink-subtle)] uppercase tracking-wider mb-2 flex items-center gap-1.5">
            <Anchor className="w-3 h-3 text-[var(--current)]" />
            <span>Major Indian Coastal Ports</span>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
            {POPULAR_PORTS.map((p) => (
              <button
                key={p.name}
                type="button"
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
                className="px-3 py-2 text-left rounded-xl bg-[var(--surface-muted)] border border-[var(--border)] hover:border-[var(--current)]/40 hover:bg-[var(--foam)]/50 transition-all cursor-pointer group shadow-2xs"
              >
                <div className="font-medium text-xs text-[var(--ink)] group-hover:text-[var(--current)] transition-colors">
                  {p.name}
                </div>
                <div className="text-[10px] text-[var(--ink-muted)] font-mono-data mt-0.5">{p.state}</div>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
