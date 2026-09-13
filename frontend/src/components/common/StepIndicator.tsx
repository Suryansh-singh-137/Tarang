import React, { useState } from "react";
import {
  CheckCircle2,
  Circle,
  Loader2,
  CloudRain,
  Fish,
  AlertTriangle,
  ShieldCheck,
  ChevronDown,
  ChevronUp,
} from "lucide-react";
import { ProgressEventData } from "@/lib/types";

interface Props {
  activeStep?: string;
  completedSteps: ProgressEventData[];
  className?: string;
}

const AGENT_ORDER = [
  { key: "weather_agent", label: "Marine Weather", icon: CloudRain },
  { key: "pfz_agent", label: "Fishing Zones (PFZ)", icon: Fish },
  { key: "hazard_agent", label: "Cyclone & Hazard", icon: AlertTriangle },
  { key: "risk_agent", label: "Safety Assessment", icon: ShieldCheck },
];

export const StepIndicator: React.FC<Props> = ({
  activeStep,
  completedSteps,
  className = "",
}) => {
  const [isExpanded, setIsExpanded] = useState(false);
  const completedAgentNames = new Set(completedSteps.map((s) => s.agent_name || s.node));
  const latestSummary = completedSteps.length > 0 ? completedSteps[completedSteps.length - 1].summary : null;

  return (
    <div
      className={`bg-white/95 rounded-xl border border-[var(--border)] shadow-2xs transition-all overflow-hidden ${className}`}
      aria-label="Agent reasoning progress"
    >
      {/* Compact single-line summary by default (Part 1C.1) */}
      <button
        type="button"
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full px-3.5 py-2.5 flex items-center justify-between text-xs cursor-pointer hover:bg-[var(--foam)]/40 transition-colors"
        aria-label={isExpanded ? "Collapse reasoning pipeline steps" : "Expand reasoning pipeline steps"}
      >
        <div className="flex items-center gap-2 overflow-hidden pr-2">
          <Loader2 className="w-3.5 h-3.5 animate-spin text-[var(--current)] shrink-0" />
          <span className="font-medium text-[var(--ink)] truncate text-xs">
            {latestSummary ? latestSummary : `Checking sources (${completedSteps.length}/4 completed)...`}
          </span>
        </div>

        <div className="flex items-center gap-1.5 shrink-0 text-[11px] text-[var(--ink-muted)]">
          <span className="font-mono-data text-[10px] text-[var(--ink-subtle)] bg-[var(--surface-muted)] px-2 py-0.5 rounded-full border border-[var(--border)]">
            {completedSteps.length}/4
          </span>
          {isExpanded ? (
            <ChevronUp className="w-3.5 h-3.5 text-[var(--ink-subtle)]" />
          ) : (
            <ChevronDown className="w-3.5 h-3.5 text-[var(--ink-subtle)]" />
          )}
        </div>
      </button>

      {/* Expanded detailed multi-agent grid only when requested */}
      {isExpanded && (
        <div className="p-3 pt-2 border-t border-[var(--border)] space-y-2.5 animate-in fade-in duration-150">
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
            {AGENT_ORDER.map(({ key, label }) => {
              const isDone = completedAgentNames.has(key);
              const isCurrent = activeStep === key || (!isDone && completedSteps.length === 0 && key === "weather_agent");

              return (
                <div
                  key={key}
                  className={`flex items-center gap-1.5 p-2 rounded-lg text-xs font-medium border transition-all ${
                    isDone
                      ? "bg-[#EBF7F0] border-[#C3E8D2] text-[#1B8755]"
                      : isCurrent
                      ? "bg-[var(--foam)] border-[var(--current)] text-[var(--current)] ring-1 ring-[var(--current)]/20 shadow-xs"
                      : "bg-[var(--surface-muted)] border-[var(--border)] text-[var(--ink-subtle)] opacity-70"
                  }`}
                >
                  {isDone ? (
                    <CheckCircle2 className="w-3.5 h-3.5 text-[#1B8755] shrink-0" />
                  ) : isCurrent ? (
                    <Loader2 className="w-3.5 h-3.5 text-[var(--current)] animate-spin shrink-0" />
                  ) : (
                    <Circle className="w-3.5 h-3.5 text-[var(--ink-subtle)] shrink-0 opacity-40" />
                  )}
                  <span className="truncate">{label}</span>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
};
