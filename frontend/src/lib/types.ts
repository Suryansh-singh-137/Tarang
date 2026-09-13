// TypeScript schema definitions for Tarang Coastal Dawn frontend

export type LanguageCode = "en" | "hi" | "ta";

export type RiskLabel = "LOW" | "MODERATE" | "HIGH" | "EXTREME" | "UNKNOWN";

export type RiskComponent = {
  label: string;
  raw_value: number | string;
  raw_unit: string;
  component_score: number;
  weight: number;
  contribution: number;
};

export type RiskData = {
  composite_score: number | null;
  risk_label: RiskLabel;
  recommendation: string;
  components?: RiskComponent[];
  evidence_coverage?: string;
  data_sources_live?: Record<string, boolean>;
};

export type EvidenceItem = {
  claim: string;
  value?: any;
  unit?: string;
  source: string;
  source_time?: string;
  retrieved_at?: string;
  provenance_tier?: string;
};

export type TraceEntry = {
  agent_name: string;
  status: "success" | "skipped" | "error" | "insufficient_data" | "unknown";
  summary: string;
  source: string;
  used_fallback?: boolean;
  data_quality?: string;
};

export type ProgressEventData = {
  node: string;
  agent_name: string;
  status: string;
  summary: string;
  source: string;
};

export type LocationStatus = "coastal" | "inland" | "unresolved" | "idle";

export type ParsedIntent = {
  location_name: string;
  lat: number | null;
  lon: number | null;
  time_window: string;
  time_start_utc?: string;
  time_end_utc?: string;
  query_type: string;
  needs_weather?: boolean;
  needs_pfz?: boolean;
  needs_hazard?: boolean;
  needs_geofence?: boolean;
  needs_risk?: boolean;
  location_status?: "coastal" | "inland" | "unresolved";
  distance_to_coast_km?: number | null;
};

export type GeoJSONFeature = {
  type: "Feature";
  geometry: {
    type: "Point" | "LineString" | "Polygon";
    coordinates: any;
  };
  properties: Record<string, any>;
};

export type MapGeoJSON = {
  type: "FeatureCollection";
  features: GeoJSONFeature[];
};

export type LocationMode = "DEVICE" | "EXPLICIT_PLACE" | "EXPLICIT_COORDINATES" | "INHERITED" | "NONE";
export type ExecutionStatus = "success" | "partial" | "failed" | "skipped";
export type DataStatus = "live" | "cached" | "mixed" | "unavailable";

export type DeviceLocation = {
  lat: number;
  lon: number;
  accuracy?: number | null;
  captured_at?: string | null;
  permission_status?: string;
};

export type ResolvedLocation = {
  lat: number;
  lon: number;
  name: string;
  source: string;
  confidence: number;
  coastal: boolean;
  nearest_coast_km?: number | null;
  state?: string | null;
  district?: string | null;
};

export type OceanData = {
  station_name?: string;
  water_level_m: number;
  datum: string;
  current_phase: string;
  next_high_tide?: {
    time_utc: string;
    time_ist: string;
    height_m: number;
  };
  next_low_tide?: {
    time_utc: string;
    time_ist: string;
    height_m: number;
  };
  tidal_range_m?: number;
  tidal_stream_knots?: number;
  source: string;
};

export type QueryResultPayload = {
  request_id?: string;
  conversation_id?: string;
  answer_text: string;
  language: string;
  location?: {
    mode: LocationMode;
    resolved: ResolvedLocation | null;
    query?: any;
    device?: DeviceLocation | null;
  };
  execution_status?: ExecutionStatus;
  overall_data_status?: DataStatus;
  agents?: {
    weather?: TraceEntry | any;
    pfz?: TraceEntry | any;
    ocean?: TraceEntry | any;
    hazard?: TraceEntry | any;
    geofence?: TraceEntry | any;
    risk?: TraceEntry | any;
  };
  map_geojson: MapGeoJSON;
  trace: TraceEntry[];
  risk_data?: RiskData;
  evidence?: EvidenceItem[];
  parsed_intent?: ParsedIntent;
  conversation_history?: Array<{ role: string; content: string }>;
  last_parsed_intent?: ParsedIntent | null;
  last_results?: Record<string, any>;
  changed_fields?: string[];
};

export type Message = {
  id: string;
  request_id?: string;
  role: "user" | "assistant";
  content: string;
  language?: string;
  location?: {
    mode: LocationMode;
    resolved: ResolvedLocation | null;
  };
  execution_status?: ExecutionStatus;
  overall_data_status?: DataStatus;
  risk_data?: RiskData;
  evidence?: EvidenceItem[];
  trace?: TraceEntry[];
  map_geojson?: MapGeoJSON;
  parsed_intent?: ParsedIntent;
  timestamp: string;
  isStreaming?: boolean;
  isError?: boolean;
};


export type ChatState = {
  conversation: Array<{ role: string; content: string }>;
  last_parsed_intent: ParsedIntent | null;
  last_results: Record<string, any>;
};

export type LiveConditionsSummary = {
  locationName: string;
  lat: number;
  lon: number;
  waveHeightM: number;
  windSpeedKmh: number;
  seaState: string;
  riskLabel: RiskLabel;
  source: string;
  isFallback: boolean;
};
