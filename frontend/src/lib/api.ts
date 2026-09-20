// Unified API client for Tarang backend (SSE query streaming, STT, and TTS)

import {
  ChatState,
  ProgressEventData,
  QueryResultPayload,
  SelectedLocation,
  MarineContext,
  LocationSearchResult,
  RouteResult,
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
  triggerSms: boolean = true
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
