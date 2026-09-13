import React from "react";
import { CheckCircle2, Circle, Loader2, CloudRain, Fish, AlertTriangle, ShieldCheck } from "lucide-react";
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
  const completedAgentNames = new Set(completedSteps.map((s) => s.agent_name || s.node));

  return (
    <div
      className={`p-3.5 bg-white/90 rounded-xl border border-[var(--border)] shadow-xs transition-all ${className}`}
      aria-label="Agent reasoning progress"
    >
      <div className="flex items-center justify-between mb-2.5">
        <span className="text-xs font-semibold tracking-wider text-[var(--ink-muted)] uppercase">
          Live Reasoning Pipeline
        </span>
        <span className="flex items-center gap-1.5 text-xs font-medium text-[var(--current)]">
          <Loader2 className="w-3.5 h-3.5 animate-spin" />
          Processing
        </span>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
        {AGENT_ORDER.map(({ key, label, icon: Icon }) => {
          const isDone = completedAgentNames.has(key);
          const isCurrent = activeStep === key || (!isDone && completedSteps.length === 0 && key === "weather_agent");

          return (
            <div
              key={key}
              className={`flex items-center gap-2 p-2 rounded-lg text-xs font-medium border transition-all ${
                isDone
                  ? "bg-[#EBF7F0] border-[#C3E8D2] text-[#1B8755]"
                  : isCurrent
                  ? "bg-[var(--foam)] border-[var(--current)] text-[var(--current)] ring-1 ring-[var(--current)]/20 shadow-xs"
                  : "bg-[var(--surface-muted)] border-[var(--border)] text-[var(--ink-subtle)] opacity-70"
              }`}
            >
              {isDone ? (
                <CheckCircle2 className="w-4 h-4 text-[#1B8755] shrink-0" />
              ) : isCurrent ? (
                <Loader2 className="w-4 h-4 text-[var(--current)] animate-spin shrink-0" />
              ) : (
                <Circle className="w-4 h-4 text-[var(--ink-subtle)] shrink-0 opacity-40" />
              )}
              <span className="truncate">{label}</span>
            </div>
          );
        })}
      </div>

      {/* Latest agent summary preview if available */}
      {completedSteps.length > 0 && (
        <div className="mt-2.5 pt-2 border-t border-[var(--border)] text-xs text-[var(--ink-muted)] truncate flex items-center gap-1.5">
          <span className="w-1.5 h-1.5 rounded-full bg-[var(--current)] shrink-0" />
          <span className="truncate">
            {completedSteps[completedSteps.length - 1].summary || "Analysis in progress..."}
          </span>
        </div>
      )}
    </div>
  );
};
