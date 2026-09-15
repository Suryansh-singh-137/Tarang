"use client";

import React, { createContext, useContext, useEffect, useState, useCallback, ReactNode } from "react";
import { SelectedLocation, MarineContext, LocationSearchResult } from "./types";
import {
  searchLocationsApi,
  resolveLocationApi,
  reverseGeocodeApi,
  setSessionLocationApi,
  getSessionLocationApi,
} from "./api";

const STORAGE_KEY_LOCATION = "tarang_selected_location";
const STORAGE_KEY_RECENT = "tarang_recent_locations";

// Representative coastal port default (Kochi, Kerala)
const DEFAULT_LOCATION: SelectedLocation = {
  name: "Kochi",
  display_name: "Kochi, Kerala, India",
  lat: 9.9312,
  lon: 76.2673,
  state: "Kerala",
  country: "India",
  source: "default",
};

const DEFAULT_MARINE_CONTEXT: MarineContext = {
  type: "coastal",
  is_coastal: true,
  nearest_port: "Kochi",
  distance_to_coast_km: 1.2,
  tide_available: true,
  fishing_data_available: true,
};

interface LocationContextValue {
  selectedLocation: SelectedLocation;
  marineContext: MarineContext;
  recentLocations: SelectedLocation[];
  isLoading: boolean;
  isPickerOpen: boolean;
  setPickerOpen: (open: boolean) => void;
  setLocation: (location: SelectedLocation, marineContext?: MarineContext) => Promise<void>;
  selectCoordinates: (lat: number, lon: number, name?: string, source?: "gps" | "map" | "search") => Promise<void>;
  searchLocations: (query: string) => Promise<LocationSearchResult[]>;
  updateFromQueryResult: (loc?: SelectedLocation, ctx?: MarineContext) => void;
  syncWithSession: (sessionId: string) => Promise<void>;
  clearRecentLocations: () => void;
}

const LocationContext = createContext<LocationContextValue | undefined>(undefined);

export function LocationProvider({ children }: { children: ReactNode }) {
  const [selectedLocation, setSelectedLocationState] = useState<SelectedLocation>(DEFAULT_LOCATION);
  const [marineContext, setMarineContextState] = useState<MarineContext>(DEFAULT_MARINE_CONTEXT);
  const [recentLocations, setRecentLocations] = useState<SelectedLocation[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [isPickerOpen, setPickerOpen] = useState<boolean>(false);
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null);

  // Load saved location and recent list from localStorage on mount
  useEffect(() => {
    try {
      const savedLoc = localStorage.getItem(STORAGE_KEY_LOCATION);
      if (savedLoc) {
        const parsed = JSON.parse(savedLoc) as SelectedLocation;
        if (parsed && typeof parsed.lat === "number" && typeof parsed.lon === "number") {
          setSelectedLocationState(parsed);
          // Resolve marine context for saved location in background
          resolveLocationApi(parsed.lat, parsed.lon, parsed.name, parsed.source || "search")
            .then((res) => {
              if (res && res.marine_context) {
                setMarineContextState(res.marine_context);
              }
            })
            .catch(() => {});
        }
      }

      const savedRecent = localStorage.getItem(STORAGE_KEY_RECENT);
      if (savedRecent) {
        const parsedRecent = JSON.parse(savedRecent);
        if (Array.isArray(parsedRecent)) {
          setRecentLocations(parsedRecent.slice(0, 5));
        }
      }
    } catch (e) {
      console.warn("Could not parse saved location from localStorage:", e);
    }
  }, []);

  const addToRecent = useCallback((loc: SelectedLocation) => {
    setRecentLocations((prev) => {
      // Remove duplicate by name or close coordinates
      const filtered = prev.filter(
        (p) =>
          p.name.toLowerCase() !== loc.name.toLowerCase() &&
          !(Math.abs(p.lat - loc.lat) < 0.01 && Math.abs(p.lon - loc.lon) < 0.01)
      );
      const next = [loc, ...filtered].slice(0, 5);
      try {
        localStorage.setItem(STORAGE_KEY_RECENT, JSON.stringify(next));
      } catch (e) {
        console.warn("Could not save recent locations:", e);
      }
      return next;
    });
  }, []);

  const setLocation = useCallback(
    async (location: SelectedLocation, context?: MarineContext) => {
      setIsLoading(true);
      try {
        setSelectedLocationState(location);
        try {
          localStorage.setItem(STORAGE_KEY_LOCATION, JSON.stringify(location));
        } catch (e) {
          console.warn("Could not save selected location:", e);
        }
        addToRecent(location);

        let finalContext = context;
        if (!finalContext) {
          const resolved = await resolveLocationApi(
            location.lat,
            location.lon,
            location.name,
            location.source || "search"
          );
          if (resolved) {
            finalContext = resolved.marine_context;
            if (resolved.location) {
              setSelectedLocationState((curr) => ({
                ...curr,
                name: resolved.location.name,
                display_name: resolved.location.display_name,
              }));
            }
          }
        }

        if (finalContext) {
          setMarineContextState(finalContext);
        }

        // Sync with backend session if active
        if (currentSessionId && finalContext) {
          await setSessionLocationApi(currentSessionId, location, finalContext);
        }
      } finally {
        setIsLoading(false);
      }
    },
    [addToRecent, currentSessionId]
  );

  const selectCoordinates = useCallback(
    async (lat: number, lon: number, name?: string, source: "gps" | "map" | "search" = "map") => {
      const initialName = name || `${lat.toFixed(2)}°N, ${lon.toFixed(2)}°E`;
      const optimisticLoc: SelectedLocation = {
        name: initialName,
        display_name: initialName,
        lat,
        lon,
        source,
      };
      
      // Immediate local state update for zero latency feedback
      setSelectedLocationState(optimisticLoc);
      try {
        localStorage.setItem(STORAGE_KEY_LOCATION, JSON.stringify(optimisticLoc));
      } catch (e) {}
      addToRecent(optimisticLoc);

      setIsLoading(true);
      try {
        const resolved = await resolveLocationApi(lat, lon, name, source);
        if (resolved) {
          await setLocation(resolved.location, resolved.marine_context);
        }
      } catch (err) {
        console.warn("Could not resolve location coordinates:", err);
      } finally {
        setIsLoading(false);
      }
    },
    [addToRecent, setLocation]
  );

  const searchLocations = useCallback(async (query: string): Promise<LocationSearchResult[]> => {
    return await searchLocationsApi(query, 6);
  }, []);

  const updateFromQueryResult = useCallback(
    (loc?: SelectedLocation, ctx?: MarineContext) => {
      if (!loc) return;
      setSelectedLocationState(loc);
      if (ctx) {
        setMarineContextState(ctx);
      }
      try {
        localStorage.setItem(STORAGE_KEY_LOCATION, JSON.stringify(loc));
      } catch (e) {}
      addToRecent(loc);
    },
    [addToRecent]
  );

  const syncWithSession = useCallback(
    async (sessionId: string) => {
      setCurrentSessionId(sessionId);
      try {
        const remote = await getSessionLocationApi(sessionId);
        if (remote && remote.selected_location) {
          setSelectedLocationState(remote.selected_location);
          if (remote.marine_context) {
            setMarineContextState(remote.marine_context);
          }
        } else if (selectedLocation && marineContext) {
          // Push client location to newly initialized session
          await setSessionLocationApi(sessionId, selectedLocation, marineContext);
        }
      } catch (e) {
        console.warn("Failed to sync location with session:", e);
      }
    },
    [selectedLocation, marineContext]
  );

  const clearRecentLocations = useCallback(() => {
    setRecentLocations([]);
    try {
      localStorage.removeItem(STORAGE_KEY_RECENT);
    } catch (e) {}
  }, []);

  return (
    <LocationContext.Provider
      value={{
        selectedLocation,
        marineContext,
        recentLocations,
        isLoading,
        isPickerOpen,
        setPickerOpen,
        setLocation,
        selectCoordinates,
        searchLocations,
        updateFromQueryResult,
        syncWithSession,
        clearRecentLocations,
      }}
    >
      {children}
    </LocationContext.Provider>
  );
}

export function useLocation(): LocationContextValue {
  const context = useContext(LocationContext);
  if (!context) {
    throw new Error("useLocation must be used within a LocationProvider");
  }
  return context;
}
