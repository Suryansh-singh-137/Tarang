"use client";

import React, { useState } from "react";
import { ChevronDown, ChevronUp, Database, Activity, CheckCircle2, AlertCircle, Clock, ShieldCheck } from "lucide-react";
import { TraceEntry, EvidenceItem } from "@/lib/types";

interface EvidenceTimelineDrawerProps {
  trace?: TraceEntry[];
  evidence?: EvidenceItem[];
  overallDataStatus?: string;
}

export function EvidenceTimelineDrawer({
  trace = [],
  evidence = [],
  overallDataStatus = "live",
}: EvidenceTimelineDrawerProps) {
  const [isOpen, setIsOpen] = useState(false);

  if (trace.length === 0 && evidence.length === 0) return null;

  return (
    <div className="rounded-xl border border-slate-800 bg-slate-950/60 overflow-hidden mt-3 text-xs transition-all">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full flex items-center justify-between p-3 text-slate-300 hover:text-white hover:bg-slate-900/50 transition-colors"
        aria-expanded={isOpen}
      >
        <div className="flex items-center gap-2">
          <Activity className="h-4 w-4 text-cyan-400" />
          <span className="font-semibold text-slate-200">Execution Trace & Evidence Timeline</span>
          <span className="rounded-full bg-slate-800 px-2 py-0.5 text-[10px] text-slate-400">
            {trace.length} agent steps • {evidence.length} claims
          </span>
        </div>

        <div className="flex items-center gap-2">
          <span className={`text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded ${
            overallDataStatus === "live" ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/30" : "bg-amber-500/10 text-amber-400 border border-amber-500/30"
          }`}>
            {overallDataStatus}
          </span>
          {isOpen ? <ChevronUp className="h-4 w-4 text-slate-400" /> : <ChevronDown className="h-4 w-4 text-slate-400" />}
        </div>
      </button>

      {isOpen && (
        <div className="border-t border-slate-800/80 p-3.5 space-y-3 bg-slate-900/30">
          {/* Agent execution sequence */}
          <div className="space-y-2">
            <span className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider block mb-1">
              Agent Execution Sequence
            </span>
            {trace.map((item, idx) => (
              <div
                key={idx}
                className="flex items-start gap-2.5 rounded-lg border border-slate-800/80 bg-slate-950/80 p-2 text-slate-300"
              >
                <div className="mt-0.5">
                  {item.status === "success" ? (
                    <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" />
                  ) : item.status === "skipped" ? (
                    <Clock className="h-3.5 w-3.5 text-slate-400" />
                  ) : (
                    <AlertCircle className="h-3.5 w-3.5 text-amber-400" />
                  )}
                </div>

                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-semibold text-slate-200">{item.agent_name}</span>
                    <span className="text-[10px] text-slate-400 font-mono">{item.source || "Deterministic Engine"}</span>
                  </div>
                  <p className="text-[11px] text-slate-400 mt-0.5">{item.summary}</p>
                </div>
              </div>
            ))}
          </div>

          {/* Evidence claims table */}
          {evidence.length > 0 && (
            <div className="space-y-1.5 pt-2 border-t border-slate-800/60">
              <span className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider block mb-1">
                Verified Sensor Claims
              </span>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-1.5">
                {evidence.map((ev, idx) => (
                  <div key={idx} className="rounded bg-slate-950/60 border border-slate-850 p-1.5 text-[11px] flex justify-between gap-2">
                    <span className="text-slate-300 truncate">{ev.claim}</span>
                    <span className="text-cyan-300 font-mono shrink-0">{ev.value} {ev.unit}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
