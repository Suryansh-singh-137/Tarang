// Unified API client for Tarang backend (SSE query streaming, STT, and TTS)

import {
  ChatState,
  ProgressEventData,
  QueryResultPayload,
  SelectedLocation,
  MarineContext,
  LocationSearchResult,
  RouteResult,
  EcosystemProductivityResponse,
  ProductivityDiagnosisResponse,
} from "./types";

export const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

export type StreamCallbacks = {
  onProgress?: (progress: ProgressEventData) => void;
  onResult?: (result: QueryResultPayload) => void;
  onError?: (error: string) => void;
};

export interface QueryOptions {
  request_id?: string;
  conversation_id?: string;
  device_location?: {
    lat: number;
    lon: number;
    accuracy?: number | null;
    captured_at?: string | null;
    permission_status?: string;
  } | null;
  selected_location?: SelectedLocation | null;
  marine_context?: MarineContext | null;
  user_lat?: number | null;
  user_lon?: number | null;
  user_location_name?: string | null;
  language?: string | null;
  signal?: AbortSignal;
}

/**
 * Stream query via POST /query with SSE event parsing
 */
export async function streamQuery(
  query: string,
  state: ChatState,
  callbacks: StreamCallbacks,
  options?: QueryOptions
): Promise<void> {
  try {
    const response = await fetch(`${API_BASE_URL}/query`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Accept": "text/event-stream",
      },
      body: JSON.stringify({
        query,
        request_id: options?.request_id,
        conversation_id: options?.conversation_id,
        device_location: options?.device_location,
        selected_location: options?.selected_location ?? null,
        marine_context: options?.marine_context ?? null,
        conversation: state.conversation,
        last_parsed_intent: state.last_parsed_intent,
        last_results: state.last_results,
        user_lat: options?.user_lat ?? (options?.selected_location ? options.selected_location.lat : null),
        user_lon: options?.user_lon ?? (options?.selected_location ? options.selected_location.lon : null),
        user_location_name: options?.user_location_name ?? (options?.user_lat != null ? "Current Location" : (options?.selected_location ? options.selected_location.name : null)),
        language: options?.language ?? null,
      }),
      signal: options?.signal,
    });


    if (!response.ok) {
      throw new Error(`Server responded with HTTP ${response.status}`);
    }

    const reader = response.body?.getReader();
    if (!reader) {
      throw new Error("Unable to read response stream from server");
    }

    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const normalized = buffer.replace(/\r\n/g, "\n");
      const chunks = normalized.split("\n\n");
      buffer = chunks.pop() || "";

      for (const chunk of chunks) {
        if (!chunk.trim()) continue;

        let eventType = "message";
        let dataStr = "";

        const lines = chunk.split("\n");
        for (const line of lines) {
          if (line.startsWith("event:")) {
            eventType = line.replace("event:", "").trim();
          } else if (line.startsWith("data:")) {
            dataStr = line.replace("data:", "").trim();
          }
        }

        if (!dataStr) continue;

        try {
          const parsed = JSON.parse(dataStr);
          if (eventType === "progress") {
            callbacks.onProgress?.(parsed as ProgressEventData);
          } else if (eventType === "result") {
            callbacks.onResult?.(parsed as QueryResultPayload);
          } else if (eventType === "error") {
            callbacks.onError?.(parsed.error || "An unexpected error occurred");
          }
        } catch (e) {
          console.warn("Could not parse SSE JSON:", dataStr, e);
        }
      }
    }
  } catch (err: any) {
    if (err.name === "AbortError") {
      console.log("Query request aborted by user");
      return;
    }
    console.error("Query stream error:", err);
    callbacks.onError?.(err.message || "Failed to communicate with Tarang server");
  }
}

/**
 * Transcribe recorded audio blob via POST /transcribe (Groq Whisper)
 */
export async function transcribeAudio(audioBlob: Blob): Promise<{ transcript: string; language?: string }> {
  const formData = new FormData();
  formData.append("audio", audioBlob, "recording.webm");

  const response = await fetch(`${API_BASE_URL}/transcribe`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    const errorText = await response.text().catch(() => "");
    throw new Error(`Transcription failed (${response.status}): ${errorText}`);
  }

  const data = await response.json();
  return {
    transcript: data.transcript || "",
    language: data.detected_language_whisper,
  };
}

/**
 * Synthesize text into audio bytes via POST /speak (Sarvam AI TTS)
 */
export async function synthesizeSpeech(text: string, language: string): Promise<Blob> {
  const response = await fetch(`${API_BASE_URL}/speak`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      text,
      language: language || "en",
    }),
  });

  if (!response.ok) {
    const errorText = await response.text().catch(() => "");
    throw new Error(`TTS synthesis failed with HTTP ${response.status}: ${errorText}`);
  }

  const contentType = response.headers.get("content-type") || "";
  if (!contentType.includes("audio")) {
    const errorJson = await response.text().catch(() => "");
    throw new Error(`Expected audio bytes but received ${contentType}: ${errorJson}`);
  }

  const blob = await response.blob();
  if (!blob || blob.size === 0) {
    throw new Error("Received empty audio response from TTS server");
  }

  return blob;
}

/**
 * Search locations via GET /location/search
 */
export async function searchLocationsApi(query: string, limit: number = 6): Promise<LocationSearchResult[]> {
  if (!query || !query.trim()) return [];
  try {
    const res = await fetch(`${API_BASE_URL}/location/search?q=${encodeURIComponent(query.trim())}&limit=${limit}`);
    if (!res.ok) return [];
    const data = await res.json();
    return data.results || [];
  } catch (err) {
    console.error("Failed to search locations:", err);
    return [];
  }
}

/**
 * Reverse geocode coordinates via GET /location/reverse
 */
export async function reverseGeocodeApi(
  lat: number,
  lon: number
): Promise<{ name: string; display_name: string; state?: string; country?: string } | null> {
  try {
    const res = await fetch(`${API_BASE_URL}/location/reverse?lat=${lat}&lon=${lon}`, {
      signal: AbortSignal.timeout(3000),
    });
    if (!res.ok) return null;
    const data = await res.json();
    return data.location || null;
  } catch (err) {
    console.warn("Failed to reverse geocode:", err);
    return null;
  }
}

/**
 * Resolve canonical location via POST /location/resolve
 */
export async function resolveLocationApi(
  lat: number,
  lon: number,
  name?: string,
  source: string = "search"
): Promise<{ location: SelectedLocation; marine_context: MarineContext } | null> {
  try {
    const res = await fetch(`${API_BASE_URL}/location/resolve`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ lat, lon, name, source }),
      signal: AbortSignal.timeout(3000),
    });
    if (!res.ok) return null;
    return await res.json();
  } catch (err) {
    console.warn("Failed to resolve location:", err);
    return null;
  }
}

/**
 * Update session canonical location via POST /session/location
 */
export async function setSessionLocationApi(
  conversationId: string,
  location: SelectedLocation,
  marineContext?: MarineContext
): Promise<boolean> {
  try {
    const res = await fetch(`${API_BASE_URL}/session/location`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        conversation_id: conversationId,
        location,
        marine_context: marineContext,
      }),
    });
    return res.ok;
  } catch (err) {
    console.warn("Failed to set session location:", err);
    return false;
  }
}

/**
 * Retrieve session canonical location via GET /session/location
 */
export async function getSessionLocationApi(
  conversationId: string
): Promise<{ selected_location: SelectedLocation | null; marine_context: MarineContext | null } | null> {
  try {
    const res = await fetch(`${API_BASE_URL}/session/location?conversation_id=${encodeURIComponent(conversationId)}`);
    if (!res.ok) return null;
    return await res.json();
  } catch (err) {
    console.warn("Failed to get session location:", err);
    return null;
  }
}

/**
 * Retrieve Potential Fishing Zones (PFZ) for a location via GET /location/pfz
 */
export async function fetchPfzZonesApi(
  lat: number,
  lon: number,
  name?: string
): Promise<{
  status: string;
  is_coastal: boolean;
  location?: { name: string; lat: number; lon: number };
  zones: any[];
  nearest_zone_km?: number;
  zone_count?: number;
  avg_chl?: number;
  source?: string;
  data_quality?: string;
  used_fallback?: boolean;
  summary?: string;
  features?: any[];
} | null> {
  try {
    const nameParam = name ? `&name=${encodeURIComponent(name)}` : "";
    const res = await fetch(`${API_BASE_URL}/location/pfz?lat=${lat}&lon=${lon}${nameParam}`);
    if (!res.ok) return null;
    return await res.json();
  } catch (err) {
    console.warn("Failed to fetch PFZ zones:", err);
    return null;
  }
}

export interface GeofenceEvaluationResult {
  is_breached: boolean;
  boundary_name: string;
  distance_km: number;
  status: "breach" | "critical_buffer" | "warning_buffer" | "safe";
  bearing_to_safety: number;
  bearing_cardinal: string;
  warning_title: string;
  warning_message: string;
  sector: string;
  coordinates: {
    lat: number;
    lon: number;
  };
  coastguard_number: string;
  whatsapp_sent?: boolean;
  whatsapp_result?: {
    success: boolean;
    simulated?: boolean;
    to?: string;
    from?: string;
    sid?: string;
    error?: string;
    message_preview?: string;
    note?: string;
    rate_limited?: boolean;
    next_allowed_in_seconds?: number;
  };
  sms_sent?: boolean;
  sms_result?: {
    success: boolean;
    simulated?: boolean;
    to?: string;
    from?: string;
    sid?: string;
    error?: string;
    message_preview?: string;
    note?: string;
    rate_limited?: boolean;
    next_allowed_in_seconds?: number;
  };
}

/**
 * Evaluate maritime geofence status (IMBL boundary breach) and optionally trigger WhatsApp + SMS alerts
 */
export async function evaluateGeofenceApi(
  lat: number,
  lon: number,
  phone?: string,
  name?: string,
  triggerWhatsapp: boolean = true,
  triggerSms: boolean = true,
  forceDispatch: boolean = false
): Promise<GeofenceEvaluationResult | null> {
  try {
    const res = await fetch(`${API_BASE_URL}/geofence/evaluate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        lat,
        lon,
        phone: phone || undefined,
        name: name || undefined,
        trigger_whatsapp: triggerWhatsapp,
        trigger_sms: triggerSms,
        force_dispatch: forceDispatch,
      }),
    });
    if (!res.ok) return null;
    return await res.json();
  } catch (err) {
    console.warn("Failed to evaluate maritime geofence:", err);
    return null;
  }
}


// ---------------------------------------------------------------------------
// Route Planning API
// ---------------------------------------------------------------------------

export interface PlanRouteOptions {
  start_lat: number;
  start_lon: number;
  end_lat: number;
  end_lon: number;
  start_name?: string;
  end_name?: string;
  departure_utc?: string;
  time_window?: string;
  include_pfz?: boolean;
  mode?: string;
}

/**
 * Plan a safe marine route between two locations.
 * Uses deterministic A* optimization with multi-objective profiles.
 */
export async function planRoute(
  options: PlanRouteOptions
): Promise<RouteResult | null> {
  try {
    const res = await fetch(`${API_BASE_URL}/route`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        start_lat: options.start_lat,
        start_lon: options.start_lon,
        end_lat: options.end_lat,
        end_lon: options.end_lon,
        start_name: options.start_name || "Start",
        end_name: options.end_name || "Destination",
        departure_utc: options.departure_utc,
        time_window: options.time_window || "next_24h",
        include_pfz: options.include_pfz ?? true,
        mode: options.mode || "all",
      }),
    });
    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      console.error("Route planning failed:", errData);
      return null;
    }
    return await res.json();
  } catch (err) {
    console.error("Failed to plan route:", err);
    return null;
  }
}

// ---------------------------------------------------------------------------
// Ecosystem Productivity & Researcher Suite APIs
// ---------------------------------------------------------------------------

export async function fetchProductivityAnalyticsApi(
  region: string,
  startYear: number = 2018,
  endYear: number = 2024
): Promise<EcosystemProductivityResponse | null> {
  try {
    const res = await fetch(
      `${API_BASE_URL}/analytics/productivity?region=${encodeURIComponent(region)}&start_year=${startYear}&end_year=${endYear}`
    );
    if (!res.ok) return null;
    return await res.json();
  } catch (err) {
    console.error("Failed to fetch productivity analytics:", err);
    return null;
  }
}

export async function diagnoseProductivityApi(
  region: string,
  startYear: number = 2018,
  endYear: number = 2024
): Promise<ProductivityDiagnosisResponse | null> {
  try {
    const res = await fetch(`${API_BASE_URL}/analytics/productivity/diagnose`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        region,
        start_year: startYear,
        end_year: endYear,
      }),
    });
    if (!res.ok) return null;
    return await res.json();
  } catch (err) {
    console.error("Failed to diagnose productivity decline:", err);
    return null;
  }
}

export async function chatResearcherEcosystemApi(
  region: string,
  message: string,
  history: Array<{ role: string; content: string }> = []
): Promise<string> {
  try {
    const res = await fetch(`${API_BASE_URL}/analytics/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        region,
        message,
        history,
      }),
    });
    if (!res.ok) {
      throw new Error(`Chat request failed with HTTP ${res.status}`);
    }
    const data = await res.json();
    return data.reply || "";
  } catch (err: any) {
    console.error("Failed in researcher ecosystem chat:", err);
    throw err;
  }
}

// ---------------------------------------------------------------------------
// Wind Direction Grid API
// ---------------------------------------------------------------------------

export interface WindPoint {
  lat: number;
  lon: number;
  speed_kmh: number;
  /** Meteorological convention: direction FROM which the wind blows (0° = from North) */
  direction_deg: number;
}

export interface WindGridResponse {
  points: WindPoint[];
  total: number;
  source: string;
}

/**
 * Fetch a spatial grid of wind vectors for the given bounding box.
 * Uses Open-Meteo Forecast API via the Tarang backend (no API key exposed).
 *
 * @param latMin  Southern latitude bound
 * @param latMax  Northern latitude bound
 * @param lonMin  Western longitude bound
 * @param lonMax  Eastern longitude bound
 * @param gridN   Points per side (total = gridN²). Default 4 → 16 arrows.
 */
export async function fetchWindGridApi(
  latMin: number,
  latMax: number,
  lonMin: number,
  lonMax: number,
  gridN: number = 4
): Promise<WindGridResponse | null> {
  try {
    let s = Math.max(-85, Math.min(85, latMin));
    let n = Math.max(-85, Math.min(85, latMax));
    let w = Math.max(-180, Math.min(180, lonMin));
    let e = Math.max(-180, Math.min(180, lonMax));
    if (s > n) [s, n] = [n, s];
    if (w > e) [w, e] = [e, w];

    const params = new URLSearchParams({
      lat_min: s.toFixed(4),
      lat_max: n.toFixed(4),
      lon_min: w.toFixed(4),
      lon_max: e.toFixed(4),
      grid_n: String(Math.max(2, Math.min(gridN, 5))),
    });
    const res = await fetch(`${API_BASE_URL}/weather/wind-grid?${params}`, {
      signal: AbortSignal.timeout(25000),
    });
    if (!res.ok) {
      console.warn("[WindGrid] Backend returned", res.status);
      return null;
    }
    return await res.json();
  } catch (err) {
    console.warn("[WindGrid] Failed to fetch wind grid:", err);
    return null;
  }
}

export interface MarineScalarPoint {
  lat: number;
  lon: number;
  value: number;
  unit: string;
}

export interface MarineLayerResponse {
  layer_type: string;
  points: MarineScalarPoint[];
  total: number;
  unit: string;
  source: string;
}

export async function fetchMarineLayerGrid(
  latMin: number,
  latMax: number,
  lonMin: number,
  lonMax: number,
  layerType: "temperature" | "sst" | "chlorophyll",
  gridN: number = 4
): Promise<MarineLayerResponse | null> {
  try {
    let s = Math.max(-85, Math.min(85, latMin));
    let n = Math.max(-85, Math.min(85, latMax));
    let w = Math.max(-180, Math.min(180, lonMin));
    let e = Math.max(-180, Math.min(180, lonMax));
    if (s > n) [s, n] = [n, s];
    if (w > e) [w, e] = [e, w];

    const params = new URLSearchParams({
      lat_min: s.toFixed(4),
      lat_max: n.toFixed(4),
      lon_min: w.toFixed(4),
      lon_max: e.toFixed(4),
      layer_type: layerType,
      grid_n: String(Math.max(2, Math.min(gridN, 5))),
    });
    const res = await fetch(`${API_BASE_URL}/weather/marine-layer-grid?${params}`, {
      signal: AbortSignal.timeout(20000),
    });
    if (!res.ok) return null;
    return await res.json();
  } catch (err) {
    console.warn(`[MarineLayer] Failed to fetch ${layerType}:`, err);
    return null;
  }
}

export async function fetchImblBoundary(): Promise<any | null> {
  try {
    const res = await fetch(`${API_BASE_URL}/boundaries/imbl`, {
      signal: AbortSignal.timeout(10000),
    });
    if (!res.ok) return null;
    return await res.json();
  } catch (err) {
    console.warn("[IMBL] Failed to fetch IMBL boundary:", err);
    return null;
  }
}

export async function fetchRegionalPfz(
  latMin: number,
  latMax: number,
  lonMin: number,
  lonMax: number
): Promise<{ zones: any[]; features: any[]; total: number } | null> {
  try {
    const params = new URLSearchParams({
      lat_min: latMin.toFixed(4),
      lat_max: latMax.toFixed(4),
      lon_min: lonMin.toFixed(4),
      lon_max: lonMax.toFixed(4),
    });
    const res = await fetch(`${API_BASE_URL}/marine/pfz-grid?${params}`, {
      signal: AbortSignal.timeout(15000),
    });
    if (!res.ok) return null;
    return await res.json();
  } catch (err) {
    console.warn("[PFZ] Failed to fetch regional PFZ:", err);
    return null;
  }
}


