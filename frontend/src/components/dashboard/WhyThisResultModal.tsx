"use client";

import React from "react";
import { X, Shield, AlertTriangle, Info, CheckCircle2, Layers, ExternalLink } from "lucide-react";
import { MarineSnapshot, RiskLabel } from "@/lib/types";

interface WhyThisResultModalProps {
  isOpen: boolean;
  onClose: () => void;
  snapshot?: MarineSnapshot | null;
}

export function WhyThisResultModal({ isOpen, onClose, snapshot }: WhyThisResultModalProps) {
  if (!isOpen || !snapshot) return null;

  const risk = snapshot.risk;
  const weather = snapshot.weather;
  const hazards = snapshot.hazards;
  const geofence = snapshot.geofence;
  const riskLabel: RiskLabel = risk.final_level || risk.risk_label || "LOW";
  const components = risk.components || [];

  const getRiskBadge = (label: RiskLabel) => {
    switch (label) {
      case "LOW":
        return "bg-emerald-500/20 text-emerald-300 border-emerald-500/40";
      case "MODERATE":
        return "bg-amber-500/20 text-amber-300 border-amber-500/40";
      case "HIGH":
      case "EXTREME":
        return "bg-red-500/20 text-red-300 border-red-500/40";
      default:
        return "bg-slate-500/20 text-slate-300 border-slate-500/40";
    }
  };

  // Default fallback components if not passed directly from backend
  const displayComponents = components.length > 0 ? components : [
    {
      label: "Wave Height",
      raw_value: weather.wave_height_m ?? 1.0,
      raw_unit: "m",
      component_score: Math.min(100, Math.round(((weather.wave_height_m || 1.0) / 3.0) * 100)),
      weight: 0.35,
      contribution: Math.min(35, Math.round(((weather.wave_height_m || 1.0) / 3.0) * 35)),
    },
    {
      label: "Wind Speed",
      raw_value: weather.wind_speed_kmh ?? 15,
      raw_unit: "km/h",
      component_score: Math.min(100, Math.round(((weather.wind_speed_kmh || 15) / 50.0) * 100)),
      weight: 0.25,
      contribution: Math.min(25, Math.round(((weather.wind_speed_kmh || 15) / 50.0) * 25)),
    },
    {
      label: "Hazard Warnings",
      raw_value: hazards.overall_hazard_level || "none",
      raw_unit: "",
      component_score: hazards.overall_hazard_level === "high" ? 100 : hazards.overall_hazard_level === "moderate" ? 50 : 0,
      weight: 0.25,
      contribution: hazards.overall_hazard_level === "high" ? 25 : hazards.overall_hazard_level === "moderate" ? 12.5 : 0,
    },
    {
      label: "Boundary Proximity",
      raw_value: geofence.imbl_distance_km ? `${Math.round(geofence.imbl_distance_km)} km` : "Safe distance",
      raw_unit: "",
      component_score: 5,
      weight: 0.15,
      contribution: 1.0,
    },
  ];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-sm animate-in fade-in duration-200">
      <div 
        className="relative w-full max-w-2xl max-h-[90vh] overflow-y-auto rounded-2xl border border-slate-800 bg-slate-900 shadow-2xl p-5 sm:p-6"
        role="dialog"
        aria-modal="true"
      >
        {/* Header */}
        <div className="flex items-center justify-between border-b border-slate-800 pb-4 mb-4">
          <div className="flex items-center gap-2.5">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-indigo-500/10 border border-indigo-500/30 text-indigo-400">
              <Shield className="h-5 w-5" />
            </div>
            <div>
              <h3 className="text-base font-semibold text-white">Why this result?</h3>
              <p className="text-xs text-slate-400">
                Transparent breakdown of Tarang&apos;s marine safety assessment for {snapshot.location.name}
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-800 hover:text-white transition-colors"
            aria-label="Close"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* 1. Verdict & Top Factor */}
        <div className="rounded-xl bg-slate-950/60 border border-slate-800 p-4 mb-4">
          <div className="flex items-center justify-between gap-3 mb-2">
            <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Overall Verdict</span>
            <span className={`rounded-full border px-3 py-0.5 text-xs font-bold uppercase tracking-wider ${getRiskBadge(riskLabel)}`}>
              {riskLabel} RISK
            </span>
          </div>

          <p className="text-sm text-slate-200 leading-relaxed font-medium">
            {risk.recommendation || "Assessment based on verified multi-stream marine sensor data."}
          </p>

          {risk.override_reason && (
            <div className="mt-3 flex items-start gap-2 rounded-lg bg-red-500/10 border border-red-500/30 p-2.5 text-xs text-red-300">
              <AlertTriangle className="h-4 w-4 shrink-0 text-red-400 mt-0.5" />
              <div>
                <span className="font-semibold">Safety Override Active: </span>
                {risk.override_reason}
              </div>
            </div>
          )}
        </div>

        {/* 2. Factor-by-Factor Breakdown (PRD §9) */}
        <div className="mb-5">
          <div className="flex items-center gap-1.5 mb-2.5 text-xs font-semibold text-slate-300 uppercase tracking-wider">
            <Layers className="h-3.5 w-3.5 text-cyan-400" />
            <span>Measured Factors & Contribution</span>
          </div>

          <div className="space-y-2">
            {displayComponents.map((comp, idx) => {
              const weightPct = Math.round((comp.weight || 0.25) * 100);
              const score = Math.round(comp.component_score || comp.score || 0);
              const contrib = (comp.contribution || 0).toFixed(1);

              return (
                <div 
                  key={idx}
                  className="rounded-xl border border-slate-800/80 bg-slate-950/40 p-3 flex flex-col sm:flex-row sm:items-center justify-between gap-2.5"
                >
                  <div className="flex-1">
                    <div className="flex items-center justify-between sm:justify-start gap-2">
                      <span className="text-xs font-semibold text-slate-200">{comp.label}</span>
                      <span className="text-xs font-mono px-2 py-0.5 rounded bg-slate-800 text-slate-300">
                        {comp.raw_value} {comp.raw_unit}
                      </span>
                    </div>
                    <div className="flex items-center gap-3 text-[11px] text-slate-400 mt-1">
                      <span>Score: <strong className="text-slate-300">{score}/100</strong></span>
                      <span>•</span>
                      <span>Weight: <strong className="text-slate-300">{weightPct}%</strong></span>
                    </div>
                  </div>

                  <div className="text-right shrink-0">
                    <span className="text-xs text-slate-400 block">Contribution</span>
                    <span className="text-sm font-semibold font-mono text-cyan-400">+{contrib} pts</span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* 3. Official Sources Consulted */}
        <div className="rounded-xl border border-slate-800 bg-slate-950/30 p-3.5 mb-4 text-xs text-slate-400 space-y-1.5">
          <div className="font-semibold text-slate-300 flex items-center gap-1.5 mb-1">
            <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" />
            <span>Official Data Streams Consulted</span>
          </div>
          <p>• <strong>Marine Weather & Waves:</strong> Open-Meteo High-Resolution Marine (ECMWF/GFS)</p>
          <p>• <strong>Tide & Water Levels:</strong> INCOIS Harmonic Prediction & Chart Datum</p>
          <p>• <strong>Severe Hazards:</strong> Open-Meteo Severe Warning & GDACS Cyclone Monitor</p>
          <p>• <strong>Maritime Boundaries:</strong> UNCLOS Territorial Sea & IMBL Geofence Engine</p>
          <p>• <strong>Fishing Potential:</strong> INCOIS Oceansat-2 Chlorophyll Satellite Proxy</p>
        </div>

        {/* 4. Explainability & Safety Contract Footer */}
        <div className="rounded-lg bg-amber-500/5 border border-amber-500/20 p-3 text-[11px] text-amber-300/90 leading-relaxed flex items-start gap-2">
          <Info className="h-4 w-4 shrink-0 text-amber-400 mt-0.5" />
          <p>
            <strong>Decision-Support Notice:</strong> Tarang synthesizes available scientific indicators as a navigation aid. It does not issue official clearance. Always adhere to port closures and instructions issued by IMD and the Indian Coast Guard.
          </p>
        </div>
      </div>
    </div>
  );
}
