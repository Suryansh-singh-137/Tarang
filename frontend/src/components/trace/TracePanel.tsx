import React, { useState } from "react";
import {
  ChevronDown,
  ChevronRight,
  Shield,
  CheckCircle2,
  AlertCircle,
  HelpCircle,
  Activity,
  Layers,
  FileText,
} from "lucide-react";
import { TraceEntry, EvidenceItem, LanguageCode } from "@/lib/types";
import { translations } from "@/lib/i18n";

interface Props {
  trace: TraceEntry[];
  evidence?: EvidenceItem[];
  language?: LanguageCode;
  className?: string;
  isOpen?: boolean;
  onToggle?: () => void;
}

export const TracePanel: React.FC<Props> = ({
  trace,
  evidence = [],
  language = "en",
  className = "",
  isOpen = true,
  onToggle,
}) => {
  const [expandedAgent, setExpandedAgent] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<"trace" | "evidence">("trace");
  const t = translations[language] || translations.en;

  const toggleAgent = (name: string) => {
    setExpandedAgent(expandedAgent === name ? null : name);
  };

  const getStatusBadge = (status: string) => {
    switch (status.toLowerCase()) {
      case "success":
        return (
          <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-[#1B8755] bg-[#EBF7F0] px-2 py-0.5 rounded-full border border-[#C3E8D2]">
            <CheckCircle2 className="w-3 h-3" /> success
          </span>
        );
      case "insufficient_data":
      case "fallback":
        return (
          <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-[#B45309] bg-[#FEF3C7] px-2 py-0.5 rounded-full border border-[#FDE68A]">
            <AlertCircle className="w-3 h-3" /> fallback
          </span>
        );
      case "skipped":
        return (
          <span className="inline-flex items-center gap-1 text-[11px] font-medium text-[var(--ink-subtle)] bg-[var(--surface-muted)] px-2 py-0.5 rounded-full border border-[var(--border)]">
            skipped
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1 text-[11px] font-medium text-[var(--ink-subtle)] bg-[var(--surface-muted)] px-2 py-0.5 rounded-full">
            <HelpCircle className="w-3 h-3" /> {status}
          </span>
        );
    }
  };

  return (
    <div className={`bg-[var(--surface)] border border-[var(--border)] rounded-xl shadow-xs overflow-hidden flex flex-col ${className}`}>
      {/* Header with toggle */}
      <div className="p-3.5 bg-[var(--surface-muted)] border-b border-[var(--border)] flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Activity className="w-4 h-4 text-[var(--current)]" />
          <h2 className="text-xs font-bold uppercase tracking-wider text-[var(--ink-muted)]">
            {t.reasoningTrace}
          </h2>
          <span className="text-[11px] font-medium text-[var(--ink-subtle)] bg-white px-2 py-0.5 rounded-full border border-[var(--border)]">
            {trace.length} steps
          </span>
        </div>

        {onToggle && (
          <button
            type="button"
            onClick={onToggle}
            className="p-1 text-[var(--ink-muted)] hover:text-[var(--ink)] hover:bg-[var(--foam)] rounded-md transition-colors"
            title={isOpen ? "Collapse trace panel" : "Expand trace panel"}
          >
            {isOpen ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
          </button>
        )}
      </div>

      {isOpen && (
        <>
          {/* Sub-tabs: Trace vs Evidence */}
          <div className="flex items-center border-b border-[var(--border)] bg-white px-3 pt-2">
            <button
              type="button"
              onClick={() => setActiveTab("trace")}
              className={`flex items-center gap-1.5 pb-2 px-3 text-xs font-semibold border-b-2 transition-all ${
                activeTab === "trace"
                  ? "border-[var(--current)] text-[var(--current)]"
                  : "border-transparent text-[var(--ink-muted)] hover:text-[var(--ink)]"
              }`}
            >
              <Layers className="w-3.5 h-3.5" />
              Agent Pipeline ({trace.length})
            </button>
            <button
              type="button"
              onClick={() => setActiveTab("evidence")}
              className={`flex items-center gap-1.5 pb-2 px-3 text-xs font-semibold border-b-2 transition-all ${
                activeTab === "evidence"
                  ? "border-[var(--current)] text-[var(--current)]"
                  : "border-transparent text-[var(--ink-muted)] hover:text-[var(--ink)]"
              }`}
            >
              <FileText className="w-3.5 h-3.5" />
              Factual Evidence ({evidence.length})
            </button>
          </div>

          {/* Content Area */}
          <div className="p-3 overflow-y-auto max-h-[380px] space-y-2">
            {activeTab === "trace" ? (
              trace.length === 0 ? (
                <div className="text-center py-8 text-xs text-[var(--ink-subtle)]">
                  Reasoning trace will appear as agents execute queries.
                </div>
              ) : (
                trace.map((item, idx) => {
                  const isExpanded = expandedAgent === item.agent_name;
                  return (
                    <div
                      key={idx}
                      className="border border-[var(--border)] rounded-lg bg-white transition-all overflow-hidden"
                    >
                      <button
                        type="button"
                        onClick={() => toggleAgent(item.agent_name)}
                        className="w-full flex items-center justify-between p-2.5 hover:bg-[var(--surface-muted)] transition-colors text-left"
                      >
                        <div className="flex items-center gap-2 truncate">
                          {isExpanded ? (
                            <ChevronDown className="w-3.5 h-3.5 text-[var(--ink-subtle)] shrink-0" />
                          ) : (
                            <ChevronRight className="w-3.5 h-3.5 text-[var(--ink-subtle)] shrink-0" />
                          )}
                          <span className="text-xs font-bold text-[var(--ink)] font-mono">
                            {item.agent_name}
                          </span>
                        </div>
                        <div className="shrink-0">{getStatusBadge(item.status)}</div>
                      </button>

                      {isExpanded && (
                        <div className="p-3 bg-[var(--surface-muted)] border-t border-[var(--border)] text-xs space-y-2">
                          <div>
                            <span className="text-[11px] font-semibold text-[var(--ink-subtle)] uppercase block mb-0.5">
                              Agent Summary
                            </span>
                            <p className="text-[var(--ink)] leading-relaxed">
                              {item.summary || "Completed task successfully."}
                            </p>
                          </div>

                          <div>
                            <span className="text-[11px] font-semibold text-[var(--ink-subtle)] uppercase block mb-0.5">
                              Data Source & Provenance
                            </span>
                            <span className="text-[var(--ink-muted)] font-mono text-[11px] bg-white px-2 py-1 rounded border border-[var(--border)] inline-block">
                              {item.source || "System default"}
                            </span>
                          </div>

                          {item.used_fallback && (
                            <div className="p-2 bg-[#FEF3C7] rounded text-[11px] text-[#92400E] border border-[#FDE68A]">
                              ⚠️ Offline fallback data was used because live API was unreachable.
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  );
                })
              )
            ) : evidence.length === 0 ? (
              <div className="text-center py-8 text-xs text-[var(--ink-subtle)]">
                Factual evidence claims will populate during data-backed answers.
              </div>
            ) : (
              evidence.map((ev, idx) => (
                <div key={idx} className="p-2.5 bg-white border border-[var(--border)] rounded-lg text-xs space-y-1">
                  <div className="font-medium text-[var(--ink)] leading-snug">{ev.claim}</div>
                  <div className="flex items-center justify-between text-[11px] text-[var(--ink-subtle)] pt-1 border-t border-[var(--border)]">
                    <span className="truncate max-w-[200px]" title={ev.source}>
                      {ev.source}
                    </span>
                    {ev.provenance_tier && (
                      <span className="font-mono text-[10px] bg-[var(--foam)] text-[var(--current)] px-1.5 py-0.5 rounded">
                        {ev.provenance_tier}
                      </span>
                    )}
                  </div>
                </div>
              ))
            )}
          </div>
        </>
      )}
    </div>
  );
};
