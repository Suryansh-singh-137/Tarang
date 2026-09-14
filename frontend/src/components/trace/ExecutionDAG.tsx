"use client";

import React, { useState } from "react";
import {
  Cpu,
  GitBranch,
  CheckCircle2,
  AlertCircle,
  Clock,
  Sparkles,
  Layers,
  ArrowDown,
  ExternalLink,
  Shield,
  Activity,
  Waves,
  Fish,
  AlertTriangle,
  Compass,
  Radio,
  FileText,
  Volume2,
  X,
  Eye,
} from "lucide-react";
import { TraceEntry, EvidenceItem, LanguageCode } from "@/lib/types";

interface Props {
  trace?: TraceEntry[];
  evidence?: EvidenceItem[];
  language?: LanguageCode;
  className?: string;
}

interface DAGNode {
  id: string;
  name: string;
  label: string;
  category: "ingestion" | "routing" | "specialist" | "reasoning" | "synthesis" | "output";
  icon: any;
  description: string;
  sourceDefault: string;
  tier?: string;
  readsFrom: string[];
  writesTo: string[];
}

const DAG_NODES: DAGNode[] = [
  {
    id: "detect_and_parse",
    name: "detect_and_parse",
    label: "Intent & Location Resolver",
    category: "ingestion",
    icon: Compass,
    description: "Detects query language, extracts time windows, and resolves coordinates against the national coastal gazetteer.",
    sourceDefault: "Local Coastal Gazetteer & Whisper ASR",
    tier: "Core Runtime",
    readsFrom: ["raw_query", "device_location", "conversation_history"],
    writesTo: ["parsed_intent", "resolved_location", "detected_language"],
  },
  {
    id: "supervisor",
    name: "supervisor",
    label: "Supervisor Fan-Out Router",
    category: "routing",
    icon: GitBranch,
    description: "Evaluates needs flags (needs_weather, needs_pfz, needs_hazard, needs_geofence) to route to specialized agents.",
    sourceDefault: "Deterministic Routing Edge (No LLM hop)",
    tier: "Graph Control",
    readsFrom: ["parsed_intent"],
    writesTo: ["selective_agent_dispatch"],
  },
  {
    id: "weather_agent",
    name: "weather_agent",
    label: "Marine Weather Agent",
    category: "specialist",
    icon: Waves,
    description: "Queries high-resolution wave height, swell, wind velocity, and WMO sea-state.",
    sourceDefault: "Open-Meteo Marine + ECMWF ERA5 / ICON",
    tier: "Tier 3: NWP Models",
    readsFrom: ["resolved_location", "time_window"],
    writesTo: ["weather_result"],
  },
  {
    id: "ocean_agent",
    name: "ocean_agent",
    label: "Harmonic Tidal Agent",
    category: "specialist",
    icon: Activity,
    description: "Computes water levels above Chart Datum, tidal cycle, and upcoming high/low tides using harmonic constituents.",
    sourceDefault: "Survey of India Tide Tables & INCOIS Baseline",
    tier: "Tier 1: National Mandate",
    readsFrom: ["resolved_location", "time_window"],
    writesTo: ["ocean_result"],
  },
  {
    id: "pfz_agent",
    name: "pfz_agent",
    label: "Potential Fishing Zones Agent",
    category: "specialist",
    icon: Fish,
    description: "Identifies chlorophyll-a concentration gradients and high-productivity marine zones within operational radius.",
    sourceDefault: "INCOIS Oceansat-2 Chlorophyll Satellite Grid",
    tier: "Tier 4: Scientific Proxy",
    readsFrom: ["resolved_location"],
    writesTo: ["pfz_result"],
  },
  {
    id: "hazard_agent",
    name: "hazard_agent",
    label: "Coastal Hazard & Cyclone Agent",
    category: "specialist",
    icon: AlertTriangle,
    description: "Scans active tropical cyclones, depressions, and INCOIS rough sea / high swell advisories.",
    sourceDefault: "GDACS International Feed + IMD Cyclone Center",
    tier: "Tier 2: Global Awareness",
    readsFrom: ["resolved_location"],
    writesTo: ["hazard_result"],
  },
  {
    id: "geofence_agent",
    name: "geofence_agent",
    label: "Maritime Boundary (IMBL) Agent",
    category: "specialist",
    icon: Shield,
    description: "Calculates distance to International Maritime Boundary Lines (Palk Bay / Sir Creek) with 5nm safety buffers.",
    sourceDefault: "UNCLOS Official Maritime Baseline Shapefiles",
    tier: "Tier 1: Boundary Law",
    readsFrom: ["resolved_location"],
    writesTo: ["geofence_result"],
  },
  {
    id: "risk_agent",
    name: "risk_agent",
    label: "Deterministic Risk Engine",
    category: "reasoning",
    icon: Cpu,
    description: "Synthesizes specialist findings into an un-hallucinated composite risk score (0-100) and risk label.",
    sourceDefault: "Deterministic Multi-Factor Scoring Formula",
    tier: "Safety Critical",
    readsFrom: ["weather_result", "hazard_result", "geofence_result"],
    writesTo: ["risk_data", "composite_score"],
  },
  {
    id: "explain_risk",
    name: "explain_risk",
    label: "Non-LLM Risk Explainer",
    category: "reasoning",
    icon: FileText,
    description: "Constructs deterministic contributor breakdowns (wave contribution, wind factor) without LLM hallucination.",
    sourceDefault: "Rule-Based Deterministic Justification",
    tier: "Safety Critical",
    readsFrom: ["risk_data"],
    writesTo: ["risk_explanation"],
  },
  {
    id: "synthesis",
    name: "synthesis",
    label: "Decision Support Synthesis",
    category: "synthesis",
    icon: Sparkles,
    description: "Generates multilingual conversational advice in English, Hindi, or Tamil with data quality disclosures.",
    sourceDefault: "Groq Llama-3 70B / Rule-based Fallback",
    tier: "Synthesis Layer",
    readsFrom: ["risk_data", "all_agent_results", "detected_language"],
    writesTo: ["final_answer_text", "evidence"],
  },
  {
    id: "output_tts",
    name: "output_tts",
    label: "Streaming Output & Speech",
    category: "output",
    icon: Volume2,
    description: "Streams SSE event payload to client and provides acoustic speech synthesis.",
    sourceDefault: "Server-Sent Events + Sarvam AI Bulbul / Web Speech",
    tier: "Presentation",
    readsFrom: ["final_answer_text"],
    writesTo: ["client_sse_stream", "audio_blob"],
  },
];

export const ExecutionDAG: React.FC<Props> = ({
  trace = [],
  evidence = [],
  language = "en",
  className = "",
}) => {
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>("risk_agent");
  const [filterMode, setFilterMode] = useState<"all" | "active" | "specialists">("all");

  // Map trace entries by agent name
  const traceMap = React.useMemo(() => {
    const map = new Map<string, TraceEntry>();
    trace.forEach((t) => {
      map.set(t.agent_name, t);
    });
    return map;
  }, [trace]);

  const getNodeStatus = (nodeId: string) => {
    if (traceMap.has(nodeId)) {
      const entry = traceMap.get(nodeId)!;
      return {
        hasRun: true,
        status: entry.status.toLowerCase(),
        summary: entry.summary,
        source: entry.source,
        used_fallback: entry.used_fallback,
      };
    }

    if (nodeId === "detect_and_parse" || nodeId === "supervisor") {
      return {
        hasRun: trace.length > 0,
        status: trace.length > 0 ? "success" : "idle",
        summary: trace.length > 0 ? "Completed query parsing & routing" : "Awaiting user query",
        source: "Tarang Graph Runtime",
        used_fallback: false,
      };
    }

    if (nodeId === "synthesis" || nodeId === "output_tts") {
      const ran = trace.length > 0;
      return {
        hasRun: ran,
        status: ran ? "success" : "idle",
        summary: ran ? "Assembled response & evidence citations" : "Awaiting pipeline inputs",
        source: "Groq LLM / TTS Service",
        used_fallback: false,
      };
    }

    return {
      hasRun: false,
      status: "idle",
      summary: "Node in standby mode",
      source: "Tarang Multi-Agent System",
      used_fallback: false,
    };
  };

  const selectedNode = DAG_NODES.find((n) => n.id === selectedNodeId) || DAG_NODES[0];
  const selectedStatus = getNodeStatus(selectedNode.id);

  // Filter nodes according to toggle
  const specialistNodes = DAG_NODES.filter((n) => n.category === "specialist");
  const filteredNodes = DAG_NODES.filter((n) => {
    if (filterMode === "active") {
      const st = getNodeStatus(n.id);
      return st.hasRun && st.status !== "skipped";
    }
    if (filterMode === "specialists") {
      return n.category === "specialist" || n.category === "reasoning";
    }
    return true;
  });

  return (
    <div className={`space-y-6 ${className}`}>
      {/* Top Controls & Topology Legend */}
      <div className="bg-[var(--surface)] border border-[var(--border)] rounded-2xl p-4 sm:p-5 shadow-2xs flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 font-mono-data text-xs text-[var(--ink-muted)] uppercase tracking-wider mb-1">
            <GitBranch className="w-3.5 h-3.5 text-[var(--current)]" />
            <span>StateGraph Topology • Milestone 5 Architecture</span>
          </div>
          <h2 className="text-base sm:text-lg font-bold text-[var(--ink)] flex items-center gap-2">
            <span>LangGraph Multi-Agent DAG</span>
            <span className="text-xs font-mono font-normal bg-[var(--foam)] text-[var(--current)] px-2.5 py-0.5 rounded-full border border-[var(--current)]/20">
              {trace.length > 0 ? `${trace.length} Nodes Executed` : "Standby Pipeline"}
            </span>
          </h2>
        </div>

        {/* Filter mode toggles */}
        <div className="flex items-center gap-1.5 p-1 bg-[var(--surface-muted)] rounded-xl border border-[var(--border)] self-start sm:self-auto">
          <button
            type="button"
            onClick={() => setFilterMode("all")}
            className={`px-3 py-1 text-xs font-medium rounded-lg transition-all cursor-pointer ${
              filterMode === "all"
                ? "bg-[var(--surface)] text-[var(--ink)] shadow-2xs font-semibold"
                : "text-[var(--ink-muted)] hover:text-[var(--ink)]"
            }`}
          >
            All Nodes (11)
          </button>
          <button
            type="button"
            onClick={() => setFilterMode("active")}
            className={`px-3 py-1 text-xs font-medium rounded-lg transition-all cursor-pointer ${
              filterMode === "active"
                ? "bg-[var(--surface)] text-[var(--ink)] shadow-2xs font-semibold"
                : "text-[var(--ink-muted)] hover:text-[var(--ink)]"
            }`}
          >
            Active Path
          </button>
          <button
            type="button"
            onClick={() => setFilterMode("specialists")}
            className={`px-3 py-1 text-xs font-medium rounded-lg transition-all cursor-pointer ${
              filterMode === "specialists"
                ? "bg-[var(--surface)] text-[var(--ink)] shadow-2xs font-semibold"
                : "text-[var(--ink-muted)] hover:text-[var(--ink)]"
            }`}
          >
            Specialists Only
          </button>
        </div>
      </div>

      {/* Main DAG Canvas + Inspector Split View */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Visual Graph Topology Container (Left 7 Cols) */}
        <div className="lg:col-span-7 bg-[var(--surface)] border border-[var(--border)] rounded-2xl p-5 sm:p-6 shadow-2xs space-y-6 relative overflow-hidden">
          {/* Visual Background grid pattern */}
          <div
            className="absolute inset-0 opacity-[0.03] pointer-events-none"
            style={{
              backgroundImage: "radial-gradient(var(--ink) 1px, transparent 1px)",
              backgroundSize: "16px 16px",
            }}
          />

          {/* Phase 1: Ingestion & Supervisor */}
          <div className="space-y-3 relative z-10">
            <span className="font-mono-data text-[10px] uppercase text-[var(--ink-subtle)] tracking-widest block">
              PHASE 1: INGESTION & CONDITIONAL ROUTING
            </span>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {[DAG_NODES[0], DAG_NODES[1]].map((node) => {
                const st = getNodeStatus(node.id);
                const isSelected = selectedNodeId === node.id;
                const Icon = node.icon;

                return (
                  <button
                    key={node.id}
                    type="button"
                    onClick={() => setSelectedNodeId(node.id)}
                    className={`p-3.5 rounded-xl border text-left transition-all cursor-pointer flex flex-col justify-between gap-2.5 ${
                      isSelected
                        ? "border-[var(--current)] bg-[var(--foam)]/40 shadow-xs ring-2 ring-[var(--current)]/20"
                        : "border-[var(--border)] bg-[var(--surface)] hover:bg-[var(--surface-muted)]/60"
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <div className="w-7 h-7 rounded-lg bg-[var(--surface-muted)] border border-[var(--border)] flex items-center justify-center text-[var(--current)]">
                          <Icon className="w-3.5 h-3.5" />
                        </div>
                        <span className="font-mono text-xs font-bold text-[var(--ink)]">
                          {node.name}
                        </span>
                      </div>
                      {st.hasRun ? (
                        <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
                      ) : (
                        <span className="w-2 h-2 rounded-full bg-slate-300 shrink-0" />
                      )}
                    </div>
                    <span className="text-[11px] text-[var(--ink-muted)] line-clamp-1">
                      {node.label}
                    </span>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Connecting Fan-Out Indicator */}
          <div className="flex items-center justify-center py-1">
            <div className="flex items-center gap-2 text-[10px] font-mono-data text-[var(--ink-subtle)] px-3 py-1 rounded-full bg-[var(--surface-muted)] border border-[var(--border)]">
              <ArrowDown className="w-3 h-3 text-[var(--current)]" />
              <span>PARALLEL CONDITIONAL FAN-OUT (Selective Re-Invocation)</span>
            </div>
          </div>

          {/* Phase 2: Parallel Specialist Nodes */}
          <div className="space-y-3 relative z-10">
            <span className="font-mono-data text-[10px] uppercase text-[var(--ink-subtle)] tracking-widest block">
              PHASE 2: SPECIALIZED TELEMETRY AGENTS (Parallel Execution)
            </span>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {specialistNodes.map((node) => {
                const st = getNodeStatus(node.id);
                const isSelected = selectedNodeId === node.id;
                const Icon = node.icon;

                let badgeColor = "bg-slate-100 text-slate-600 border-slate-200";
                let statusLabel = "standby";

                if (st.status === "success") {
                  badgeColor = "bg-emerald-50 text-emerald-700 border-emerald-200";
                  statusLabel = st.used_fallback ? "cached" : "live";
                } else if (st.status === "skipped") {
                  badgeColor = "bg-slate-100 text-slate-500 border-slate-200";
                  statusLabel = "skipped";
                }

                return (
                  <button
                    key={node.id}
                    type="button"
                    onClick={() => setSelectedNodeId(node.id)}
                    className={`p-3.5 rounded-xl border text-left transition-all cursor-pointer flex flex-col justify-between gap-2.5 ${
                      isSelected
                        ? "border-[var(--current)] bg-[var(--foam)]/40 shadow-xs ring-2 ring-[var(--current)]/20"
                        : "border-[var(--border)] bg-[var(--surface)] hover:bg-[var(--surface-muted)]/60"
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <div className="w-7 h-7 rounded-lg bg-[var(--surface-muted)] border border-[var(--border)] flex items-center justify-center text-[var(--current)]">
                          <Icon className="w-3.5 h-3.5" />
                        </div>
                        <span className="font-mono text-xs font-bold text-[var(--ink)]">
                          {node.name}
                        </span>
                      </div>
                      <span className={`text-[10px] font-mono px-2 py-0.5 rounded-full border ${badgeColor}`}>
                        {statusLabel}
                      </span>
                    </div>

                    <div className="flex items-center justify-between text-[11px] text-[var(--ink-muted)]">
                      <span className="truncate max-w-[140px]">{node.label}</span>
                      <span className="text-[10px] font-mono-data text-[var(--ink-subtle)] truncate max-w-[100px]">
                        {node.tier?.split(":")[0] || "Specialist"}
                      </span>
                    </div>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Connecting Fan-In Indicator */}
          <div className="flex items-center justify-center py-1">
            <div className="flex items-center gap-2 text-[10px] font-mono-data text-[var(--ink-subtle)] px-3 py-1 rounded-full bg-[var(--surface-muted)] border border-[var(--border)]">
              <ArrowDown className="w-3 h-3 text-[var(--current)]" />
              <span>FAN-IN: DETERMINISTIC REASONING (Zero Hallucination)</span>
            </div>
          </div>

          {/* Phase 3: Reasoning & Synthesis */}
          <div className="space-y-3 relative z-10">
            <span className="font-mono-data text-[10px] uppercase text-[var(--ink-subtle)] tracking-widest block">
              PHASE 3: DETERMINISTIC RISK & LLM SYNTHESIS
            </span>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              {[DAG_NODES[7], DAG_NODES[8], DAG_NODES[9]].map((node) => {
                const st = getNodeStatus(node.id);
                const isSelected = selectedNodeId === node.id;
                const Icon = node.icon;

                return (
                  <button
                    key={node.id}
                    type="button"
                    onClick={() => setSelectedNodeId(node.id)}
                    className={`p-3.5 rounded-xl border text-left transition-all cursor-pointer flex flex-col justify-between gap-2.5 ${
                      isSelected
                        ? "border-[var(--current)] bg-[var(--foam)]/40 shadow-xs ring-2 ring-[var(--current)]/20"
                        : "border-[var(--border)] bg-[var(--surface)] hover:bg-[var(--surface-muted)]/60"
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-1.5">
                        <div className="w-6 h-6 rounded-md bg-[var(--surface-muted)] border border-[var(--border)] flex items-center justify-center text-[var(--current)]">
                          <Icon className="w-3 h-3" />
                        </div>
                        <span className="font-mono text-[11px] font-bold text-[var(--ink)]">
                          {node.name}
                        </span>
                      </div>
                    </div>
                    <span className="text-[10px] text-[var(--ink-muted)] line-clamp-1">
                      {node.label}
                    </span>
                  </button>
                );
              })}
            </div>
          </div>
        </div>

        {/* Node Inspector Detail Panel (Right 5 Cols) */}
        <div className="lg:col-span-5 bg-[var(--surface)] border border-[var(--border)] rounded-2xl p-5 sm:p-6 shadow-2xs space-y-5 sticky top-20">
          <div className="flex items-center justify-between pb-3 border-b border-[var(--border)]">
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 rounded-lg bg-[var(--foam)] border border-[var(--current)]/20 flex items-center justify-center text-[var(--current)]">
                <selectedNode.icon className="w-4 h-4" />
              </div>
              <div>
                <span className="text-[10px] font-mono-data uppercase text-[var(--ink-subtle)] block">
                  Node Inspector
                </span>
                <h3 className="font-bold text-sm text-[var(--ink)] font-mono">
                  {selectedNode.name}
                </h3>
              </div>
            </div>

            <span className="text-[10px] font-mono uppercase px-2.5 py-1 rounded-full bg-[var(--surface-muted)] border border-[var(--border)] text-[var(--ink-muted)]">
              {selectedNode.category}
            </span>
          </div>

          {/* Description */}
          <div className="space-y-1.5">
            <span className="text-[10px] font-bold text-[var(--ink-subtle)] uppercase tracking-wider font-mono-data">
              Capability & Role
            </span>
            <p className="text-xs text-[var(--ink)] leading-relaxed">
              {selectedNode.description}
            </p>
          </div>

          {/* Execution Status for this query */}
          <div className="p-3.5 rounded-xl bg-[var(--surface-muted)]/70 border border-[var(--border)] space-y-2">
            <span className="text-[10px] font-bold text-[var(--ink-subtle)] uppercase tracking-wider font-mono-data flex items-center justify-between">
              <span>Active Query Execution</span>
              <span className={`px-2 py-0.5 rounded text-[9px] font-mono uppercase font-bold ${
                selectedStatus.status === "success"
                  ? "bg-emerald-100 text-emerald-800"
                  : selectedStatus.status === "skipped"
                  ? "bg-slate-200 text-slate-700"
                  : "bg-amber-100 text-amber-800"
              }`}>
                {selectedStatus.status}
              </span>
            </span>

            <p className="text-xs text-[var(--ink)] font-mono leading-relaxed">
              {selectedStatus.summary}
            </p>

            {selectedStatus.used_fallback && (
              <div className="pt-1 text-[11px] text-amber-800 flex items-center gap-1.5 font-medium">
                <AlertCircle className="w-3.5 h-3.5 text-amber-600 shrink-0" />
                <span>Historical satellite proxy / cache utilized</span>
              </div>
            )}
          </div>

          {/* Source Attribution & Data Tier */}
          <div className="space-y-1.5">
            <span className="text-[10px] font-bold text-[var(--ink-subtle)] uppercase tracking-wider font-mono-data">
              Data Source & Authority
            </span>
            <div className="p-3 rounded-xl border border-[var(--border)] bg-white text-xs space-y-1">
              <span className="font-semibold text-[var(--ink)] block">
                {selectedStatus.source || selectedNode.sourceDefault}
              </span>
              {selectedNode.tier && (
                <span className="text-[10px] font-mono text-[var(--current)] font-medium block">
                  {selectedNode.tier}
                </span>
              )}
            </div>
          </div>

          {/* State Variables In/Out */}
          <div className="grid grid-cols-2 gap-3 pt-2 text-[11px] font-mono">
            <div className="p-2.5 rounded-lg bg-[var(--surface-muted)]/50 border border-[var(--border)] space-y-1">
              <span className="text-[9px] text-[var(--ink-subtle)] uppercase tracking-wider block">
                State Reads:
              </span>
              {selectedNode.readsFrom.map((key) => (
                <span key={key} className="block text-[10px] text-[var(--ink-muted)] truncate">
                  • {key}
                </span>
              ))}
            </div>

            <div className="p-2.5 rounded-lg bg-[var(--surface-muted)]/50 border border-[var(--border)] space-y-1">
              <span className="text-[9px] text-[var(--ink-subtle)] uppercase tracking-wider block">
                State Writes:
              </span>
              {selectedNode.writesTo.map((key) => (
                <span key={key} className="block text-[10px] text-emerald-700 truncate font-semibold">
                  + {key}
                </span>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
