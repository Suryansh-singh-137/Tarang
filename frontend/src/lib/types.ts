// TypeScript schema definitions for Tarang Coastal Dawn frontend

export type LanguageCode = "en" | "hi" | "ta" | "gu" | "bn" | "te" | "ml" | "mr" | "od";

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

export type ResponseMode =
  | "factual_direct"
  | "specialist_card"
  | "applicability_explanation"
  | "safety_assessment"
  | "clarification";

export type PresentationHint =
  | "location_card"
  | "weather_card"
  | "ocean_card"
  | "pfz_card"
  | "hazard_card"
  | "safety_card"
  | "applicability_card"
  | "clarification_card";

export type AnswerPlan = {
  intent_name: string;
  primary_capability: string;
  required_agents: string[];
  response_mode: ResponseMode;
  location_scope: string;
  evidence_needed: string[];
  presentation_hint: PresentationHint;
  show_score?: boolean;
  primary_message_style?: string;
  max_primary_sentences?: number;
  safety_action?: string;
  intent_groups?: any[];
  evidence_scope?: string[];
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
  intent_name?: string;
  answer_plan?: AnswerPlan;
  response_mode?: ResponseMode;
  query_signature?: string;
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

export interface ChangeItem {
  factor: string;
  from: string;
  to: string;
}

export interface ChangeSummary {
  has_changes: boolean;
  previous_risk: string;
  current_risk: string;
  changes: ChangeItem[];
}

export interface MarineSnapshot {
  location: {
    name: string;
    lat: number;
    lon: number;
    coastal: boolean;
    state?: string | null;
    district?: string | null;
  };
  generated_at: string;
  weather: {
    wave_height_m?: number | null;
    wind_speed_kmh?: number | null;
    wind_direction_deg?: number | null;
    sea_state?: string;
    temperature_c?: number | null;
    pressure_msl_hpa?: number | null;
    source?: string;
    observed_at?: string;
    data_quality?: string;
  };
  ocean: {
    water_level_m?: number | null;
    tide_datum?: string;
    current_phase?: string;
    tide_station?: string;
    source?: string;
    predicted_at?: string;
    data_quality?: string;
  };
  pfz: {
    nearest_zone_km?: number | null;
    zone_bearing_deg?: number | null;
    total_zones?: number;
    overall_productivity?: string;
    is_proxy: boolean;
    proxy_type?: string;
    source?: string;
    data_quality?: string;
  };
  hazards: {
    overall_hazard_level?: string;
    active_warnings?: string[];
    hazards?: any[];
    source?: string;
    checked_at?: string;
    data_quality?: string;
  };
  geofence: {
    imbl_distance_km?: number | null;
    boundary_risk?: string;
    source?: string;
  };
  sst?: {
    sst_celsius?: number | null;
    sst_anomaly_c?: number | null;
    observation_time?: string | null;
    source?: string;
    data_status?: string;
    disclaimer?: string;
  } | null;
  risk: {
    composite_score?: number | null;
    risk_label: RiskLabel;
    final_level?: RiskLabel;
    components?: any[];
    recommendation?: string;
    override_reason?: string | null;
    top_factor?: string | null;
  };
  data_quality: {
    overall_status: string;
  };
  evidence?: EvidenceItem[];
  change_summary?: ChangeSummary | null;
}

export type TarangResponse = {
  request_id: string;
  conversation_id: string;
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
    sst?: TraceEntry | any;
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
  answer_plan?: AnswerPlan;
  response_mode?: ResponseMode;
  query_signature?: string;
  conversation_history?: Array<{ role: string; content: string }>;
  last_parsed_intent?: ParsedIntent | null;
  last_results?: Record<string, any>;
  changed_fields?: string[];
  selected_location?: SelectedLocation;
  marine_context?: MarineContext;
  marine_snapshot?: MarineSnapshot | null;
  change_summary?: ChangeSummary | null;
};

export type QueryResultPayload = TarangResponse;

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
  answer_plan?: AnswerPlan;
  response_mode?: ResponseMode;
  query_signature?: string;
  timestamp: string;
  isStreaming?: boolean;
  isError?: boolean;
  marine_snapshot?: MarineSnapshot | null;
  change_summary?: ChangeSummary | null;
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

// Universal Location & Marine Context System (PRD)
export type MarineContextType = "inland" | "coastal" | "offshore" | "unknown";

export interface MarineContext {
  type: MarineContextType;
  is_coastal: boolean;
  nearest_port?: string | null;
  distance_to_coast_km?: number | null;
  tide_available: boolean;
  fishing_data_available: boolean;
}

export interface SelectedLocation {
  name: string;
  display_name: string;
  lat: number;
  lon: number;
  state?: string | null;
  country?: string | null;
  source: "search" | "gps" | "map" | "conversation" | "default";
}

export interface LocationSearchResult {
  name: string;
  display_name: string;
  lat: number;
  lon: number;
  state?: string | null;
  country?: string | null;
}

// ---------------------------------------------------------------------------
// Route Planning Types
// ---------------------------------------------------------------------------

export interface RouteWaypoint {
  lat: number;
  lon: number;
  name?: string;
  risk_score: number;
  risk_label: RiskLabel;
  wave_height_m: number;
  wind_speed_kmh: number;
  boundary_dist_km: number;
  hazard_level: string;
  pfz_chl?: number;
}

export interface RouteLeg {
  from: { lat: number; lon: number };
  to: { lat: number; lon: number };
  distance_km: number;
  risk_score: number;
  risk_label: RiskLabel;
  wave_height_m: number;
  wind_speed_kmh: number;
  boundary_dist_km: number;
  hazard_level: string;
  estimated_time_h: number;
  arrival_time_utc?: string;
}

export interface RouteResult {
  status: "success" | "no_route" | "too_far" | "error";
  total_distance_km: number;
  total_duration_h: number;
  avg_risk_score: number;
  max_risk_score: number;
  risk_label: RiskLabel;
  waypoints: RouteWaypoint[];
  legs: RouteLeg[];
  route_geojson: MapGeoJSON;
  summary: string;
  warnings: string[];
  error?: string | null;
}
