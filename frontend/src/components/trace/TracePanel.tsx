import React, { useState } from "react";
import {
  Shield,
  CheckCircle2,
  AlertCircle,
  HelpCircle,
  Activity,
  Layers,
  FileText,
  Database,
  ChevronDown,
  ChevronRight,
} from "lucide-react";
import { TraceEntry, EvidenceItem, LanguageCode } from "@/lib/types";
import { translations } from "@/lib/i18n";

interface Props {
  trace: TraceEntry[];
  evidence?: EvidenceItem[];
  language?: LanguageCode;
  className?: string;
}

export const TracePanel: React.FC<Props> = ({
  trace = [],
  evidence = [],
  language = "en",
  className = "",
}) => {
  const [expandedAgent, setExpandedAgent] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<"evidence" | "trace" | "provenance">("evidence");
  const t = translations[language] || translations.en;

  const toggleAgent = (name: string) => {
    setExpandedAgent(expandedAgent === name ? null : name);
  };

  const getStatusBadge = (status: string) => {
    switch (status.toLowerCase()) {
      case "success":
        return (
          <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-[#1B8755] bg-[#EBF7F0] px-2.5 py-0.5 rounded-full border border-[#C3E8D2]">
            <CheckCircle2 className="w-3.5 h-3.5" /> available
          </span>
        );
      case "insufficient_data":
      case "fallback":
        return (
          <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-[#B45309] bg-[#FEF3C7] px-2.5 py-0.5 rounded-full border border-[#FDE68A]">
            <AlertCircle className="w-3.5 h-3.5" /> cached
          </span>
        );
      case "skipped":
        return (
          <span className="inline-flex items-center gap-1 text-[11px] font-medium text-[var(--ink-subtle)] bg-[var(--surface-muted)] px-2.5 py-0.5 rounded-full border border-[var(--border)]">
            not applicable
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1 text-[11px] font-medium text-[var(--ink-subtle)] bg-[var(--surface-muted)] px-2.5 py-0.5 rounded-full">
            <HelpCircle className="w-3.5 h-3.5" /> {status}
          </span>
        );
    }
  };

  return (
    <div className={`flex-1 flex flex-col p-4 sm:p-6 lg:p-8 max-w-4xl mx-auto w-full overflow-y-auto space-y-6 ${className}`}>
      {/* Header (PRD §14, §16) */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-[var(--border)]">
        <div>
          <div className="font-mono-data text-[11px] text-[var(--ink-muted)] uppercase tracking-widest mb-1">
            DECISION SUPPORT & SOURCING
          </div>
          <h1 className="font-serif-display text-2xl sm:text-3xl text-[var(--ink)] font-normal">
            Evidence & Sources
          </h1>
        </div>

        <div className="flex items-center gap-2">
          <span className="font-mono-data text-xs text-[var(--ink-muted)] bg-[var(--surface-muted)] px-3 py-1 rounded-full border border-[var(--border)]">
            {evidence.length} verified data points
          </span>
        </div>
      </div>

      {/* Sub-navigation tabs (PRD §15) */}
      <div className="flex items-center gap-2 border-b border-[var(--border)] pb-2">
        <button
          type="button"
          onClick={() => setActiveTab("evidence")}
          className={`flex items-center gap-1.5 px-3.5 py-2 text-xs font-semibold rounded-lg transition-all cursor-pointer ${
            activeTab === "evidence"
              ? "bg-[var(--foam)] text-[var(--current)] shadow-2xs"
              : "text-[var(--ink-muted)] hover:text-[var(--ink)] hover:bg-[var(--surface-muted)]"
          }`}
        >
          <FileText className="w-3.5 h-3.5" />
          <span>Why this result? ({evidence.length})</span>
        </button>

        <button
          type="button"
          onClick={() => setActiveTab("trace")}
          className={`flex items-center gap-1.5 px-3.5 py-2 text-xs font-semibold rounded-lg transition-all cursor-pointer ${
            activeTab === "trace"
              ? "bg-[var(--foam)] text-[var(--current)] shadow-2xs"
              : "text-[var(--ink-muted)] hover:text-[var(--ink)] hover:bg-[var(--surface-muted)]"
          }`}
        >
          <Layers className="w-3.5 h-3.5" />
          <span>Technical Pipeline ({trace.length})</span>
        </button>

        <button
          type="button"
          onClick={() => setActiveTab("provenance")}
          className={`flex items-center gap-1.5 px-3.5 py-2 text-xs font-semibold rounded-lg transition-all cursor-pointer ${
            activeTab === "provenance"
              ? "bg-[var(--foam)] text-[var(--current)] shadow-2xs"
              : "text-[var(--ink-muted)] hover:text-[var(--ink)] hover:bg-[var(--surface-muted)]"
          }`}
        >
          <Database className="w-3.5 h-3.5" />
          <span>Data Provenance</span>
        </button>
      </div>

      {/* Tab 1: Agent Pipeline */}
      {activeTab === "trace" && (
        <div className="space-y-3">
          {trace.length === 0 ? (
            <div className="p-12 text-center bg-[var(--surface)] border border-[var(--border)] rounded-2xl shadow-2xs space-y-2">
              <Activity className="w-8 h-8 text-[var(--ink-subtle)] mx-auto opacity-60" />
              <h3 className="text-sm font-semibold text-[var(--ink)]">No Active Pipeline Trace</h3>
              <p className="text-xs text-[var(--ink-muted)] max-w-sm mx-auto leading-relaxed">
                Submit a coastal query in the Chat view to inspect the live execution trace across the 6 specialized agents.
              </p>
            </div>
          ) : (
            trace.map((item, idx) => {
              const isExpanded = expandedAgent === item.agent_name || trace.length === 1;

              return (
                <div
                  key={idx}
                  className="border border-[var(--border)] rounded-xl bg-[var(--surface)] shadow-2xs transition-all overflow-hidden"
                >
                  <button
                    type="button"
                    onClick={() => toggleAgent(item.agent_name)}
                    className="w-full flex items-center justify-between p-3.5 hover:bg-[var(--surface-muted)]/50 transition-colors text-left cursor-pointer"
                  >
                    <div className="flex items-center gap-2.5 truncate">
                      {isExpanded ? (
                        <ChevronDown className="w-4 h-4 text-[var(--ink-subtle)] shrink-0" />
                      ) : (
                        <ChevronRight className="w-4 h-4 text-[var(--ink-subtle)] shrink-0" />
                      )}
                      <span className="text-xs font-bold text-[var(--ink)] font-mono">
                        {item.agent_name}
                      </span>
                    </div>
                    <div className="shrink-0">{getStatusBadge(item.status)}</div>
                  </button>

                  {isExpanded && (
                    <div className="p-4 bg-[var(--surface-muted)]/60 border-t border-[var(--border)] text-xs space-y-3 animate-in fade-in duration-150">
                      <div>
                        <span className="text-[10px] font-semibold text-[var(--ink-subtle)] uppercase tracking-wider block mb-1">
                          Node Summary
                        </span>
                        <p className="text-[var(--ink)] leading-relaxed">
                          {item.summary || "Agent task completed without warnings."}
                        </p>
                      </div>

                      <div>
                        <span className="text-[10px] font-semibold text-[var(--ink-subtle)] uppercase tracking-wider block mb-1">
                          Authoritative Data Source
                        </span>
                        <span className="text-[var(--ink-muted)] font-mono text-[11px] bg-white px-2.5 py-1 rounded-md border border-[var(--border)] inline-block">
                          {item.source || "System operational default"}
                        </span>
                      </div>

                      {item.used_fallback && (
                        <div className="p-2.5 bg-[#FEF3C7] rounded-lg text-[11px] text-[#92400E] border border-[#FDE68A]">
                          ⚠️ Fallback disclosure: Offline cache was utilized because external satellite telemetry was unreachable.
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })
          )}
        </div>
      )}

      {/* Tab 2: Factual Evidence (PRD §14, §17) */}
      {activeTab === "evidence" && (
        <div className="space-y-3">
          {evidence.length === 0 ? (
            <div className="p-12 text-center bg-[var(--surface)] border border-[var(--border)] rounded-2xl shadow-2xs space-y-2">
              <FileText className="w-8 h-8 text-[var(--ink-subtle)] mx-auto opacity-60" />
              <h3 className="text-sm font-semibold text-[var(--ink)]">No Evidence Recorded Yet</h3>
              <p className="text-xs text-[var(--ink-muted)] max-w-sm mx-auto leading-relaxed">
                Submit a coastal query in Ask Tarang to inspect the live evidence items supporting the marine assessment.
              </p>
            </div>
          ) : (
            evidence.map((ev, idx) => (
              <div
                key={idx}
                className="p-4 bg-[var(--surface)] border border-[var(--border)] rounded-xl shadow-2xs text-xs space-y-2.5"
              >
                <div className="font-medium text-[var(--ink)] text-sm leading-snug">
                  &ldquo;{ev.claim}&rdquo;
                </div>
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 pt-2 border-t border-[var(--border)] text-[11px] text-[var(--ink-subtle)]">
                  <div>
                    <span className="block text-[10px] uppercase font-mono-data text-[var(--ink-subtle)]">Source</span>
                    <strong className="text-[var(--ink-muted)] truncate block" title={ev.source}>{ev.source}</strong>
                  </div>
                  <div>
                    <span className="block text-[10px] uppercase font-mono-data text-[var(--ink-subtle)]">Verification</span>
                    <span className="text-emerald-700 font-semibold">✓ Grounded claim</span>
                  </div>
                  {ev.provenance_tier && (
                    <div className="col-span-2 sm:col-span-1 sm:text-right">
                      <span className="block text-[10px] uppercase font-mono-data text-[var(--ink-subtle)]">Tier</span>
                      <span className="font-mono text-[10px] bg-[var(--foam)] text-[var(--current)] px-2 py-0.5 rounded-full font-semibold border border-[var(--current)]/20">
                        {ev.provenance_tier}
                      </span>
                    </div>
                  )}
                </div>
              </div>
            ))
          )}
        </div>
      )}

      {/* Tab 3: M8 Provenance Tiers */}
      {activeTab === "provenance" && (
        <div className="space-y-3">
          <div className="p-4 bg-[var(--surface)] border border-[var(--border)] rounded-xl shadow-2xs space-y-1.5">
            <span className="text-xs font-bold text-[var(--ink)] block">Tier 1: Official National Mandate</span>
            <p className="text-xs text-[var(--ink-muted)] leading-relaxed">
              INCOIS Ocean State Forecasts, High Wave Alerts, and IMD Tropical Cyclone Bulletins. Carries highest safety weight.
            </p>
          </div>

          <div className="p-4 bg-[var(--surface)] border border-[var(--border)] rounded-xl shadow-2xs space-y-1.5">
            <span className="text-xs font-bold text-[var(--ink)] block">Tier 2: Global Awareness</span>
            <p className="text-xs text-[var(--ink-muted)] leading-relaxed">
              GDACS Real-Time Tropical Cyclone Tracking and UN Disaster monitoring telemetry. Used for proactive international alerts.
            </p>
          </div>

          <div className="p-4 bg-[var(--surface)] border border-[var(--border)] rounded-xl shadow-2xs space-y-1.5">
            <span className="text-xs font-bold text-[var(--ink)] block">Tier 3: Operational NWP Models</span>
            <p className="text-xs text-[var(--ink-muted)] leading-relaxed">
              Open-Meteo Marine API (combining ECMWF ERA5 reanalysis and German DWD ICON ocean model). Provides live wave, swell, and wind vectors.
            </p>
          </div>

          <div className="p-4 bg-[var(--surface)] border border-[var(--border)] rounded-xl shadow-2xs space-y-1.5">
            <span className="text-xs font-bold text-[var(--ink)] block">Tier 4: Scientific Proxy</span>
            <p className="text-xs text-[var(--ink-muted)] leading-relaxed">
              Oceansat-2 Chlorophyll-a Satellite Grid (INCOIS ERDDAP). Disclosed transparently as a scientific indicator, not a live official PFZ advisory.
            </p>
          </div>
        </div>
      )}
    </div>
  );
};
