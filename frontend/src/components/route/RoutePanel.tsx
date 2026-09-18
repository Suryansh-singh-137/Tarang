"use client";

import React, { useState, useCallback, useRef, useEffect } from "react";
import {
  Navigation2,
  MapPin,
  Clock,
  Waves,
  Wind,
  ShieldCheck,
  ShieldAlert,
  AlertTriangle,
  Anchor,
  Fish,
  ArrowRight,
  Loader2,
  RotateCcw,
  ChevronDown,
  ChevronUp,
} from "lucide-react";
import { RouteResult, RouteLeg, RiskLabel, MapGeoJSON } from "@/lib/types";
import { planRoute, PlanRouteOptions } from "@/lib/api";
import { API_BASE_URL } from "@/lib/api";

interface Props {
  onRouteResult?: (geojson: MapGeoJSON) => void;
  onNavigateToMap?: () => void;
}

interface LocationSuggestion {
  name: string;
  display_name: string;
  lat: number;
  lon: number;
  state?: string | null;
}

export const RoutePanel: React.FC<Props> = ({ onRouteResult, onNavigateToMap }) => {
  // Form state
  const [startQuery, setStartQuery] = useState("");
  const [endQuery, setEndQuery] = useState("");
  const [startLocation, setStartLocation] = useState<LocationSuggestion | null>(null);
  const [endLocation, setEndLocation] = useState<LocationSuggestion | null>(null);
  const [departureTime, setDepartureTime] = useState("");
  const [includePfz, setIncludePfz] = useState(true);

  // Search suggestions
  const [startSuggestions, setStartSuggestions] = useState<LocationSuggestion[]>([]);
  const [endSuggestions, setEndSuggestions] = useState<LocationSuggestion[]>([]);
  const [showStartSuggestions, setShowStartSuggestions] = useState(false);
  const [showEndSuggestions, setShowEndSuggestions] = useState(false);

  // Result state
  const [result, setResult] = useState<RouteResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expandedLeg, setExpandedLeg] = useState<number | null>(null);

  const startRef = useRef<HTMLDivElement>(null);
  const endRef = useRef<HTMLDivElement>(null);
  const debounceRef = useRef<NodeJS.Timeout | null>(null);

  // Location search
  const searchLocation = useCallback(async (query: string, target: "start" | "end") => {
    if (query.length < 2) {
      if (target === "start") setStartSuggestions([]);
      else setEndSuggestions([]);
      return;
    }

    try {
      const res = await fetch(`${API_BASE_URL}/location/search?q=${encodeURIComponent(query)}&limit=5`);
      if (res.ok) {
        const data = await res.json();
        const suggestions = data.results || [];
        if (target === "start") {
          setStartSuggestions(suggestions);
          setShowStartSuggestions(true);
        } else {
          setEndSuggestions(suggestions);
          setShowEndSuggestions(true);
        }
      }
    } catch (err) {
      console.warn("Location search failed:", err);
    }
  }, []);

  const debouncedSearch = useCallback((query: string, target: "start" | "end") => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => searchLocation(query, target), 300);
  }, [searchLocation]);

  // Close suggestions on outside click
  useEffect(() => {
    const handleClick = (e: MouseEvent) => {
      if (startRef.current && !startRef.current.contains(e.target as Node)) {
        setShowStartSuggestions(false);
      }
      if (endRef.current && !endRef.current.contains(e.target as Node)) {
        setShowEndSuggestions(false);
      }
    };
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  // Submit route request
  const handlePlanRoute = useCallback(async () => {
    if (!startLocation || !endLocation) {
      setError("Please select both a start and destination location.");
      return;
    }

    setLoading(true);
    setError(null);
    setResult(null);

    const options: PlanRouteOptions = {
      start_lat: startLocation.lat,
      start_lon: startLocation.lon,
      end_lat: endLocation.lat,
      end_lon: endLocation.lon,
      start_name: startLocation.name,
      end_name: endLocation.name,
      departure_utc: departureTime ? new Date(departureTime).toISOString() : undefined,
      include_pfz: includePfz,
    };

    try {
      const routeResult = await planRoute(options);
      if (routeResult) {
        setResult(routeResult);
        if (routeResult.route_geojson && onRouteResult) {
          onRouteResult(routeResult.route_geojson);
        }
        if (routeResult.error) {
          setError(routeResult.error);
        }
      } else {
        setError("Route planning failed. Please try again.");
      }
    } catch (err) {
      setError("An unexpected error occurred while planning the route.");
    } finally {
      setLoading(false);
    }
  }, [startLocation, endLocation, departureTime, includePfz, onRouteResult]);

  const handleReset = () => {
    setStartQuery("");
    setEndQuery("");
    setStartLocation(null);
    setEndLocation(null);
    setDepartureTime("");
    setResult(null);
    setError(null);
    setExpandedLeg(null);
  };

  // Risk-based styling
  const getRiskColor = (risk: RiskLabel | string) => {
    switch (risk) {
      case "LOW": return { bg: "bg-emerald-50", text: "text-emerald-700", border: "border-emerald-200", dot: "bg-emerald-500" };
      case "MODERATE": return { bg: "bg-amber-50", text: "text-amber-700", border: "border-amber-200", dot: "bg-amber-500" };
      case "HIGH": return { bg: "bg-red-50", text: "text-red-700", border: "border-red-200", dot: "bg-red-500" };
      case "EXTREME": return { bg: "bg-red-100", text: "text-red-800", border: "border-red-300", dot: "bg-red-600" };
      default: return { bg: "bg-gray-50", text: "text-gray-600", border: "border-gray-200", dot: "bg-gray-400" };
    }
  };

  return (
    <div className="flex flex-col h-full overflow-y-auto pb-4 px-4 pt-4 gap-4">
      {/* Header */}
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-[#0C6E8C] to-[#0A4F6E] flex items-center justify-center shadow-sm">
          <Navigation2 className="w-5 h-5 text-white" />
        </div>
        <div>
          <h2 className="text-lg font-semibold text-[var(--ink)]">Safe Route Optimizer</h2>
          <p className="text-xs text-[var(--ink-muted)]">Deterministic A* pathfinding with hard safety constraints</p>
        </div>
      </div>

      {/* Input Form */}
      <div className="bg-[var(--surface)] border border-[var(--border)] rounded-2xl p-4 space-y-3">
        {/* Start Location */}
        <div ref={startRef} className="relative">
          <label className="text-xs font-medium text-[var(--ink-muted)] mb-1 block">From</label>
          <div className="relative">
            <MapPin className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-emerald-500" />
            <input
              type="text"
              value={startQuery}
              onChange={(e) => {
                setStartQuery(e.target.value);
                setStartLocation(null);
                debouncedSearch(e.target.value, "start");
              }}
              placeholder="Search departure port or coast..."
              className="w-full pl-9 pr-3 py-2.5 text-sm bg-[var(--surface-muted)] border border-[var(--border)] rounded-xl focus:outline-none focus:ring-2 focus:ring-[#0C6E8C]/30 focus:border-[#0C6E8C] text-[var(--ink)] placeholder:text-[var(--ink-muted)]"
            />
            {startLocation && (
              <span className="absolute right-3 top-1/2 -translate-y-1/2 text-[10px] bg-emerald-100 text-emerald-700 px-2 py-0.5 rounded-full font-medium">
                ✓ Set
              </span>
            )}
          </div>
          {showStartSuggestions && startSuggestions.length > 0 && (
            <div className="absolute z-50 w-full mt-1 bg-[var(--surface)] border border-[var(--border)] rounded-xl shadow-lg max-h-48 overflow-y-auto">
              {startSuggestions.map((s, i) => (
                <button
                  key={i}
                  className="w-full text-left px-3 py-2 text-sm hover:bg-[var(--surface-muted)] transition-colors first:rounded-t-xl last:rounded-b-xl text-[var(--ink)]"
                  onClick={() => {
                    setStartLocation(s);
                    setStartQuery(s.name);
                    setShowStartSuggestions(false);
                  }}
                >
                  <span className="font-medium">{s.name}</span>
                  {s.state && <span className="text-[var(--ink-muted)] ml-1 text-xs">({s.state})</span>}
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Direction Arrow */}
        <div className="flex justify-center">
          <div className="w-8 h-8 rounded-full bg-[var(--surface-muted)] flex items-center justify-center">
            <ArrowRight className="w-4 h-4 text-[var(--ink-muted)] rotate-90" />
          </div>
        </div>

        {/* End Location */}
        <div ref={endRef} className="relative">
          <label className="text-xs font-medium text-[var(--ink-muted)] mb-1 block">To</label>
          <div className="relative">
            <MapPin className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-red-500" />
            <input
              type="text"
              value={endQuery}
              onChange={(e) => {
                setEndQuery(e.target.value);
                setEndLocation(null);
                debouncedSearch(e.target.value, "end");
              }}
              placeholder="Search destination coast or port..."
              className="w-full pl-9 pr-3 py-2.5 text-sm bg-[var(--surface-muted)] border border-[var(--border)] rounded-xl focus:outline-none focus:ring-2 focus:ring-[#0C6E8C]/30 focus:border-[#0C6E8C] text-[var(--ink)] placeholder:text-[var(--ink-muted)]"
            />
            {endLocation && (
              <span className="absolute right-3 top-1/2 -translate-y-1/2 text-[10px] bg-red-100 text-red-700 px-2 py-0.5 rounded-full font-medium">
                ✓ Set
              </span>
            )}
          </div>
          {showEndSuggestions && endSuggestions.length > 0 && (
            <div className="absolute z-50 w-full mt-1 bg-[var(--surface)] border border-[var(--border)] rounded-xl shadow-lg max-h-48 overflow-y-auto">
              {endSuggestions.map((s, i) => (
                <button
                  key={i}
                  className="w-full text-left px-3 py-2 text-sm hover:bg-[var(--surface-muted)] transition-colors first:rounded-t-xl last:rounded-b-xl text-[var(--ink)]"
                  onClick={() => {
                    setEndLocation(s);
                    setEndQuery(s.name);
                    setShowEndSuggestions(false);
                  }}
                >
                  <span className="font-medium">{s.name}</span>
                  {s.state && <span className="text-[var(--ink-muted)] ml-1 text-xs">({s.state})</span>}
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Departure Time */}
        <div>
          <label className="text-xs font-medium text-[var(--ink-muted)] mb-1 block">Departure Time</label>
          <div className="relative">
            <Clock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--ink-muted)]" />
            <input
              type="datetime-local"
              value={departureTime}
              onChange={(e) => setDepartureTime(e.target.value)}
              className="w-full pl-9 pr-3 py-2.5 text-sm bg-[var(--surface-muted)] border border-[var(--border)] rounded-xl focus:outline-none focus:ring-2 focus:ring-[#0C6E8C]/30 focus:border-[#0C6E8C] text-[var(--ink)]"
            />
          </div>
        </div>

        {/* PFZ Toggle */}
        <label className="flex items-center gap-2 cursor-pointer py-1">
          <input
            type="checkbox"
            checked={includePfz}
            onChange={(e) => setIncludePfz(e.target.checked)}
            className="w-4 h-4 rounded border-[var(--border)] text-[#0C6E8C] focus:ring-[#0C6E8C]"
          />
          <Fish className="w-4 h-4 text-cyan-600" />
          <span className="text-sm text-[var(--ink)]">Prefer route near fishing zones (PFZ)</span>
        </label>

        {/* Action Buttons */}
        <div className="flex gap-2 pt-1">
          <button
            onClick={handlePlanRoute}
            disabled={loading || !startLocation || !endLocation}
            className="flex-1 flex items-center justify-center gap-2 py-2.5 px-4 rounded-xl font-medium text-sm transition-all disabled:opacity-50 disabled:cursor-not-allowed bg-gradient-to-r from-[#0C6E8C] to-[#0A4F6E] text-white hover:shadow-md active:scale-[0.98]"
          >
            {loading ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                Computing safe route...
              </>
            ) : (
              <>
                <Navigation2 className="w-4 h-4" />
                Find Safe Route
              </>
            )}
          </button>
          {(result || error) && (
            <button
              onClick={handleReset}
              className="w-10 h-10 rounded-xl border border-[var(--border)] flex items-center justify-center text-[var(--ink-muted)] hover:bg-[var(--surface-muted)] transition-colors"
              title="Reset"
            >
              <RotateCcw className="w-4 h-4" />
            </button>
          )}
        </div>
      </div>

      {/* Error */}
      {error && !result && (
        <div className="bg-red-50 border border-red-200 rounded-xl p-3 flex items-start gap-2">
          <AlertTriangle className="w-4 h-4 text-red-500 mt-0.5 shrink-0" />
          <p className="text-sm text-red-700">{error}</p>
        </div>
      )}

      {/* Results */}
      {result && result.status === "success" && (
        <div className="space-y-3">
          {/* Summary Card */}
          <div className={`rounded-2xl border p-4 space-y-3 ${getRiskColor(result.risk_label).bg} ${getRiskColor(result.risk_label).border}`}>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <div className={`w-3 h-3 rounded-full ${getRiskColor(result.risk_label).dot}`} />
                <span className={`text-sm font-bold ${getRiskColor(result.risk_label).text}`}>
                  {result.risk_label} RISK
                </span>
              </div>
              <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${getRiskColor(result.risk_label).bg} ${getRiskColor(result.risk_label).text} border ${getRiskColor(result.risk_label).border}`}>
                Score: {result.avg_risk_score}/100
              </span>
            </div>

            <div className="grid grid-cols-3 gap-3">
              <div className="text-center">
                <p className="text-xs text-[var(--ink-muted)]">Distance</p>
                <p className="text-lg font-bold text-[var(--ink)]">{result.total_distance_km}<span className="text-xs font-normal ml-0.5">km</span></p>
              </div>
              <div className="text-center">
                <p className="text-xs text-[var(--ink-muted)]">Duration</p>
                <p className="text-lg font-bold text-[var(--ink)]">{result.total_duration_h}<span className="text-xs font-normal ml-0.5">hrs</span></p>
              </div>
              <div className="text-center">
                <p className="text-xs text-[var(--ink-muted)]">Legs</p>
                <p className="text-lg font-bold text-[var(--ink)]">{result.legs.length}</p>
              </div>
            </div>

            {result.warnings.length > 0 && (
              <div className="space-y-1 pt-1 border-t border-[var(--border)]">
                {result.warnings.map((w, i) => (
                  <div key={i} className="flex items-start gap-1.5">
                    <AlertTriangle className="w-3.5 h-3.5 text-amber-600 mt-0.5 shrink-0" />
                    <span className="text-xs text-amber-800">{w}</span>
                  </div>
                ))}
              </div>
            )}

            {onNavigateToMap && (
              <button
                onClick={onNavigateToMap}
                className="w-full py-2 rounded-xl text-sm font-medium text-[#0C6E8C] bg-white/70 border border-[#0C6E8C]/20 hover:bg-white transition-colors flex items-center justify-center gap-2"
              >
                <MapPin className="w-4 h-4" />
                View Route on Map
              </button>
            )}
          </div>

          {/* Leg-by-Leg Breakdown */}
          <div className="bg-[var(--surface)] border border-[var(--border)] rounded-2xl overflow-hidden">
            <div className="px-4 py-3 border-b border-[var(--border)]">
              <h3 className="text-sm font-semibold text-[var(--ink)]">Route Breakdown</h3>
            </div>
            <div className="divide-y divide-[var(--border)]">
              {result.legs.map((leg, i) => {
                const colors = getRiskColor(leg.risk_label);
                const isExpanded = expandedLeg === i;

                return (
                  <div key={i} className="group">
                    <button
                      className="w-full flex items-center gap-3 px-4 py-3 text-left hover:bg-[var(--surface-muted)] transition-colors"
                      onClick={() => setExpandedLeg(isExpanded ? null : i)}
                    >
                      <div className={`w-7 h-7 rounded-lg ${colors.bg} border ${colors.border} flex items-center justify-center text-xs font-bold ${colors.text} shrink-0`}>
                        {i + 1}
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-1.5 text-sm">
                          <span className="text-[var(--ink)] font-medium">{leg.distance_km} km</span>
                          <span className="text-[var(--ink-muted)]">·</span>
                          <span className={`text-xs font-semibold ${colors.text}`}>{leg.risk_label}</span>
                          <span className="text-[var(--ink-muted)]">·</span>
                          <span className="text-xs text-[var(--ink-muted)]">~{(leg.estimated_time_h * 60).toFixed(0)} min</span>
                        </div>
                      </div>
                      {isExpanded ? (
                        <ChevronUp className="w-4 h-4 text-[var(--ink-muted)]" />
                      ) : (
                        <ChevronDown className="w-4 h-4 text-[var(--ink-muted)]" />
                      )}
                    </button>

                    {isExpanded && (
                      <div className="px-4 pb-3 grid grid-cols-2 gap-2">
                        <div className="flex items-center gap-2 bg-[var(--surface-muted)] rounded-lg px-3 py-2">
                          <Waves className="w-3.5 h-3.5 text-blue-500" />
                          <div>
                            <p className="text-[10px] text-[var(--ink-muted)]">Waves</p>
                            <p className="text-sm font-medium text-[var(--ink)]">{leg.wave_height_m}m</p>
                          </div>
                        </div>
                        <div className="flex items-center gap-2 bg-[var(--surface-muted)] rounded-lg px-3 py-2">
                          <Wind className="w-3.5 h-3.5 text-teal-500" />
                          <div>
                            <p className="text-[10px] text-[var(--ink-muted)]">Wind</p>
                            <p className="text-sm font-medium text-[var(--ink)]">{leg.wind_speed_kmh} km/h</p>
                          </div>
                        </div>
                        <div className="flex items-center gap-2 bg-[var(--surface-muted)] rounded-lg px-3 py-2">
                          <ShieldCheck className="w-3.5 h-3.5 text-purple-500" />
                          <div>
                            <p className="text-[10px] text-[var(--ink-muted)]">Border Dist.</p>
                            <p className="text-sm font-medium text-[var(--ink)]">{leg.boundary_dist_km} km</p>
                          </div>
                        </div>
                        <div className="flex items-center gap-2 bg-[var(--surface-muted)] rounded-lg px-3 py-2">
                          <AlertTriangle className="w-3.5 h-3.5 text-orange-500" />
                          <div>
                            <p className="text-[10px] text-[var(--ink-muted)]">Hazard</p>
                            <p className="text-sm font-medium text-[var(--ink)] capitalize">{leg.hazard_level}</p>
                          </div>
                        </div>
                        {leg.arrival_time_utc && (
                          <div className="col-span-2 flex items-center gap-2 bg-[var(--surface-muted)] rounded-lg px-3 py-2">
                            <Clock className="w-3.5 h-3.5 text-gray-500" />
                            <div>
                              <p className="text-[10px] text-[var(--ink-muted)]">ETA at waypoint</p>
                              <p className="text-sm font-medium text-[var(--ink)]">
                                {new Date(leg.arrival_time_utc).toLocaleString("en-IN", { timeZone: "Asia/Kolkata", hour: "2-digit", minute: "2-digit", day: "numeric", month: "short" })}
                              </p>
                            </div>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>

          {/* Methodology Note */}
          <div className="bg-[var(--surface-muted)] border border-[var(--border)] rounded-xl px-4 py-3">
            <p className="text-[10px] text-[var(--ink-muted)] leading-relaxed">
              <strong>How this route was computed:</strong> Tarang builds candidate marine paths over a navigable grid, 
              removes paths violating hard safety constraints (land, severe weather ≥4m waves / ≥90 km/h wind, 
              boundary violations), then uses deterministic A* optimization to select the lowest-risk route. 
              No LLM was involved in route selection. Weather data from Open-Meteo; boundary data from INCOIS geofence.
            </p>
          </div>
        </div>
      )}

      {/* No route found */}
      {result && result.status === "no_route" && (
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 space-y-2">
          <div className="flex items-center gap-2">
            <ShieldAlert className="w-5 h-5 text-amber-600" />
            <span className="text-sm font-semibold text-amber-800">No Safe Route Found</span>
          </div>
          <p className="text-xs text-amber-700">{result.summary || result.error}</p>
        </div>
      )}

      {/* Too far */}
      {result && result.status === "too_far" && (
        <div className="bg-blue-50 border border-blue-200 rounded-xl p-4 space-y-2">
          <div className="flex items-center gap-2">
            <Anchor className="w-5 h-5 text-blue-600" />
            <span className="text-sm font-semibold text-blue-800">Distance Exceeded</span>
          </div>
          <p className="text-xs text-blue-700">{result.error}</p>
        </div>
      )}

      {/* Empty state */}
      {!result && !error && !loading && (
        <div className="flex-1 flex flex-col items-center justify-center text-center py-8 space-y-3 opacity-60">
          <Navigation2 className="w-12 h-12 text-[var(--ink-muted)] stroke-[1.2]" />
          <div>
            <p className="text-sm font-medium text-[var(--ink)]">Plan a Safe Marine Route</p>
            <p className="text-xs text-[var(--ink-muted)] mt-1 max-w-[280px]">
              Enter your departure and destination ports. Tarang will compute the safest route 
              considering real-time weather, hazards, and maritime boundaries.
            </p>
          </div>
        </div>
      )}
    </div>
  );
};
