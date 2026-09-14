"use client";

import React from "react";
import { ArrowRight, TrendingUp, AlertCircle, CheckCircle2, X } from "lucide-react";
import { ChangeSummary } from "@/lib/types";

interface ChangeSinceLastCheckProps {
  changeSummary?: ChangeSummary | null;
  onDismiss?: () => void;
}

export function ChangeSinceLastCheck({ changeSummary, onDismiss }: ChangeSinceLastCheckProps) {
  if (!changeSummary || !changeSummary.has_changes) return null;

  const changes = changeSummary.changes || [];

  const getRiskColor = (risk: string) => {
    switch (risk?.toUpperCase()) {
      case "LOW":
        return "bg-emerald-500/20 text-emerald-300 border-emerald-500/30";
      case "MODERATE":
      case "CAUTION":
        return "bg-amber-500/20 text-amber-300 border-amber-500/30";
      case "HIGH":
      case "EXTREME":
        return "bg-red-500/20 text-red-300 border-red-500/30";
      default:
        return "bg-slate-500/20 text-slate-300 border-slate-500/30";
    }
  };

  return (
    <div className="rounded-xl border border-cyan-500/30 bg-gradient-to-r from-cyan-950/40 via-slate-900/60 to-slate-900/40 p-3.5 mb-3 shadow-lg relative">
      {onDismiss && (
        <button
          onClick={onDismiss}
          className="absolute top-2.5 right-2.5 p-1 text-slate-400 hover:text-white rounded-md transition-colors"
          aria-label="Dismiss"
        >
          <X className="h-3.5 w-3.5" />
        </button>
      )}

      <div className="flex items-center gap-2 mb-2">
        <TrendingUp className="h-4 w-4 text-cyan-400" />
        <span className="text-xs font-semibold text-cyan-300 uppercase tracking-wider">
          Changed Since Your Last Check
        </span>
      </div>

      {/* Risk Transition */}
      <div className="flex items-center gap-2 mb-3 text-xs">
        <span className={`px-2 py-0.5 rounded border font-semibold ${getRiskColor(changeSummary.previous_risk)}`}>
          {changeSummary.previous_risk}
        </span>
        <ArrowRight className="h-3 w-3 text-slate-400" />
        <span className={`px-2 py-0.5 rounded border font-semibold ${getRiskColor(changeSummary.current_risk)}`}>
          {changeSummary.current_risk}
        </span>
        <span className="text-slate-400 text-[11px] ml-1">
          {changeSummary.previous_risk !== changeSummary.current_risk ? "Risk level changed" : "Parameters shifted"}
        </span>
      </div>

      {/* Changes list */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs">
        {changes.map((item, idx) => (
          <div
            key={idx}
            className="flex items-center justify-between rounded-lg bg-slate-950/50 border border-slate-800/80 px-2.5 py-1.5"
          >
            <span className="text-slate-300 font-medium">{item.factor}:</span>
            <div className="flex items-center gap-1.5 font-mono text-slate-200">
              <span className="text-slate-400 line-through text-[11px]">{item.from}</span>
              <ArrowRight className="h-2.5 w-2.5 text-cyan-400" />
              <span className="text-cyan-300 font-semibold">{item.to}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
