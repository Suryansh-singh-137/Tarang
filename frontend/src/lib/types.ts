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

export type QueryResultPayload = {
  answer_text: string;
  language: string;
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
  role: "user" | "assistant";
  content: string;
  language?: string;
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
