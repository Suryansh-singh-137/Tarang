"use client";

import React, { useState, useEffect, useMemo, useRef } from "react";
import {
  TrendingUp,
  Activity,
  Waves,
  Thermometer,
  Fish,
  AlertTriangle,
  Download,
  Info,
  Calendar,
  Layers,
  ChevronRight,
  ShieldAlert,
  CheckCircle2,
  FileText,
  Sliders,
  ExternalLink,
  Sparkles,
  RefreshCw,
  Eye,
  EyeOff,
  Bot,
  MessageSquare,
} from "lucide-react";
import {
  EcosystemProductivityResponse,
  EcosystemTimeSeriesPoint,
  ProductivityDiagnosisResponse,
  EcosystemRegionMetadata,
} from "@/lib/types";
import { fetchProductivityAnalyticsApi, diagnoseProductivityApi } from "@/lib/api";
import { ResearcherChatbot } from "./ResearcherChatbot";

const PRESET_REGIONS = [
  { id: "malabar", name: "Malabar Coast", state: "Kerala", emoji: "🌴" },
  { id: "gulf_of_mannar", name: "Gulf of Mannar", state: "Tamil Nadu", emoji: "🌊" },
  { id: "saurashtra", name: "Saurashtra Coast", state: "Gujarat", emoji: "⚓" },
  { id: "konkan", name: "Konkan Coast", state: "Maharashtra", emoji: "🚢" },
  { id: "coromandel", name: "Coromandel Coast", state: "Andhra / TN", emoji: "🌀" },
];

export const EcosystemAnalyticsView: React.FC = () => {
  const [selectedRegion, setSelectedRegion] = useState<string>("malabar");
  const [startYear, setStartYear] = useState<number>(2018);
  const [endYear, setEndYear] = useState<number>(2024);

  const [data, setData] = useState<EcosystemProductivityResponse | null>(null);
  const [diagnosis, setDiagnosis] = useState<ProductivityDiagnosisResponse | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Active view tab: chart or dedicated AI assistant
  const [activeTab, setActiveTab] = useState<"chart" | "chat">("chart");

  // Series visibility toggles
  const [showChl, setShowChl] = useState(true);
  const [showSst, setShowSst] = useState(true);
  const [showCatch, setShowCatch] = useState(true);
  const [showAnomalies, setShowAnomalies] = useState(true);

  // Chart hover interaction
  const [hoverIndex, setHoverIndex] = useState<number | null>(null);
  const chartSvgRef = useRef<SVGSVGElement>(null);

  // Load data
  useEffect(() => {
    let isMounted = true;
    setIsLoading(true);
    setError(null);

    Promise.all([
      fetchProductivityAnalyticsApi(selectedRegion, startYear, endYear),
      diagnoseProductivityApi(selectedRegion),
    ])
      .then(([prodRes, diagRes]) => {
        if (!isMounted) return;
        if (prodRes && prodRes.series) {
          setData(prodRes);
        } else {
          setError("Failed to retrieve ecosystem time-series data.");
        }
        if (diagRes && diagRes.primary_causes) {
          setDiagnosis(diagRes);
        }
        setIsLoading(false);
      })
      .catch((err) => {
        if (!isMounted) return;
        setError(err.message || "Network error loading analytics.");
        setIsLoading(false);
      });

    return () => {
      isMounted = false;
    };
  }, [selectedRegion, startYear, endYear]);

  const series = data?.series || [];

  // Chart dimensions & scaling
  const chartWidth = 960;
  const chartHeight = 350;
  const padding = { top: 34, right: 70, bottom: 45, left: 65 };
  const innerWidth = chartWidth - padding.left - padding.right;
  const innerHeight = chartHeight - padding.top - padding.bottom;

  // Compute domains
  const { minChl, maxChl, minSst, maxSst, maxCatch } = useMemo(() => {
    if (!series.length) return { minChl: 0, maxChl: 6, minSst: 24, maxSst: 32, maxCatch: 100000 };
    const chls = series.map((s) => s.chlorophyll_mg_m3);
    const ssts = series.map((s) => s.sst_celsius);
    const catches = series.map((s) => s.catch_tonnes);

    return {
      minChl: 0,
      maxChl: Math.max(5.5, Math.ceil(Math.max(...chls) * 1.15)),
      minSst: Math.floor(Math.min(...ssts) - 1),
      maxSst: Math.ceil(Math.max(...ssts) + 1),
      maxCatch: Math.ceil(Math.max(...catches) * 1.15),
    };
  }, [series]);

  // Coordinate mappers
  const getX = (index: number) => padding.left + (index / Math.max(1, series.length - 1)) * innerWidth;
  const getYChl = (val: number) => padding.top + innerHeight - ((val - minChl) / (maxChl - minChl || 1)) * innerHeight;
  const getYSst = (val: number) => padding.top + innerHeight - ((val - minSst) / (maxSst - minSst || 1)) * innerHeight;
  const getYCatch = (val: number) => padding.top + innerHeight - (val / (maxCatch || 1)) * innerHeight;

  // Generate SVG path strings
  const chlPath = useMemo(() => {
    if (!series.length) return "";
    return series.map((p, i) => `${i === 0 ? "M" : "L"} ${getX(i).toFixed(1)} ${getYChl(p.chlorophyll_mg_m3).toFixed(1)}`).join(" ");
  }, [series, minChl, maxChl]);

  const chlAreaPath = useMemo(() => {
    if (!series.length) return "";
    const base = padding.top + innerHeight;
    const line = series.map((p, i) => `${i === 0 ? "M" : "L"} ${getX(i).toFixed(1)} ${getYChl(p.chlorophyll_mg_m3).toFixed(1)}`).join(" ");
    return `${line} L ${getX(series.length - 1).toFixed(1)} ${base} L ${getX(0).toFixed(1)} ${base} Z`;
  }, [series, minChl, maxChl]);

  const sstPath = useMemo(() => {
    if (!series.length) return "";
    return series.map((p, i) => `${i === 0 ? "M" : "L"} ${getX(i).toFixed(1)} ${getYSst(p.sst_celsius).toFixed(1)}`).join(" ");
  }, [series, minSst, maxSst]);

  const sstBaselinePath = useMemo(() => {
    if (!series.length) return "";
    return series.map((p, i) => `${i === 0 ? "M" : "L"} ${getX(i).toFixed(1)} ${getYSst(p.sst_baseline_celsius).toFixed(1)}`).join(" ");
  }, [series, minSst, maxSst]);

  const catchPath = useMemo(() => {
    if (!series.length) return "";
    return series.map((p, i) => `${i === 0 ? "M" : "L"} ${getX(i).toFixed(1)} ${getYCatch(p.catch_tonnes).toFixed(1)}`).join(" ");
  }, [series, maxCatch]);

  const catchAreaPath = useMemo(() => {
    if (!series.length) return "";
    const base = padding.top + innerHeight;
    const line = series.map((p, i) => `${i === 0 ? "M" : "L"} ${getX(i).toFixed(1)} ${getYCatch(p.catch_tonnes).toFixed(1)}`).join(" ");
    return `${line} L ${getX(series.length - 1).toFixed(1)} ${base} L ${getX(0).toFixed(1)} ${base} Z`;
  }, [series, maxCatch]);

  // Handle Chart mousemove
  const handleMouseMove = (e: React.MouseEvent<SVGSVGElement>) => {
    if (!series.length || !chartSvgRef.current) return;
    const rect = chartSvgRef.current.getBoundingClientRect();
    const clientX = e.clientX - rect.left;
    const svgX = (clientX / rect.width) * chartWidth;

    const boundedX = Math.max(padding.left, Math.min(padding.left + innerWidth, svgX));
    const ratio = (boundedX - padding.left) / innerWidth;
    const index = Math.round(ratio * (series.length - 1));
    setHoverIndex(index);
  };

  const hoveredPoint: EcosystemTimeSeriesPoint | null = hoverIndex !== null && series[hoverIndex] ? series[hoverIndex] : null;

  // CSV Export Handler
  const handleExportCSV = () => {
    if (!series.length) return;
    const headers = [
      "Month",
      "SST_Celsius",
      "SST_Baseline_Celsius",
      "SST_Anomaly_Celsius",
      "Chlorophyll_mg_m3",
      "Chlorophyll_Baseline_mg_m3",
      "Chlorophyll_Anomaly_Z",
      "Catch_Tonnes",
      "Catch_Baseline_Tonnes",
      "CPUE_kg_hr",
      "Anomaly_Flag",
      "Event_Description",
    ];
    const rows = series.map((s) => [
      s.month,
      s.sst_celsius,
      s.sst_baseline_celsius,
      s.sst_anomaly_celsius,
      s.chlorophyll_mg_m3,
      s.chlorophyll_baseline_mg_m3,
      s.chlorophyll_anomaly_z,
      s.catch_tonnes,
      s.catch_baseline_tonnes,
      s.cpue_kg_per_hour,
      s.anomaly_flag,
      `"${s.event_description || ""}"`,
    ]);
    const csvContent = [headers.join(","), ...rows.map((r) => r.join(","))].join("\n");
    const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `tarang_${selectedRegion}_productivity_timeseries_${startYear}_${endYear}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const correlations = data?.correlations;
  const anomalies = data?.anomalies_summary;

  // Markdown Report Export Handler
  const handleExportMarkdown = () => {
    if (!data || !diagnosis) return;
    const mdContent = `# TARANG Fisheries Ecosystem Diagnosis: ${data.metadata.name}
**Time Horizon:** ${data.time_window.start_year}–${data.time_window.end_year}
**Dominant Target Species:** ${data.metadata.dominant_species?.join(", ")}
**Ecological Status:** ${anomalies?.stress_label || "Active Monitoring"} (Stress Index: ${anomalies?.stress_index ?? 0}/100)

## 1. Multi-Variable Correlation Matrix
- Chlorophyll ↔ Catch Trophic Coupling: r = ${correlations?.chl_vs_catch?.r ?? "N/A"} (p = ${correlations?.chl_vs_catch?.p_value ?? "N/A"})
- SST Anomaly ↔ Catch Displacement: r = ${correlations?.sst_anomaly_vs_catch?.r ?? "N/A"} (p = ${correlations?.sst_anomaly_vs_catch?.p_value ?? "N/A"})
- Upwelling Coupling (SST ↔ CHL): r = ${correlations?.chl_vs_sst?.r ?? "N/A"} (p = ${correlations?.chl_vs_sst?.p_value ?? "N/A"})

## 2. Identified Primary Causes of Decline
${diagnosis.primary_causes.map((c, i) => `### ${i + 1}. ${c.driver} (${c.severity} Severity)\n${c.mechanism}\n- **Empirical Metric:** ${c.empirical_metric}\n`).join("\n")}

## 3. Recommended Fisheries Management Interventions
${diagnosis.management_recommendations.map((r, i) => `- **${r.action}**: ${r.detail}`).join("\n")}

## 4. Data Provenance & Citations
${(data.metadata.sources || []).map((s) => `- ${s}`).join("\n")}
`;
    const blob = new Blob([mdContent], { type: "text/markdown;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `tarang_${selectedRegion}_diagnosis_brief.md`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="flex flex-col h-full overflow-y-auto px-4 sm:px-6 py-5 gap-6 text-[var(--ink)]">
      {/* Header Bar */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-[var(--border)] pb-5">
        <div className="space-y-1">
          <div className="flex items-center gap-2.5">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-emerald-600 to-teal-800 flex items-center justify-center text-white shadow-sm">
              <Activity className="w-5 h-5" />
            </div>
            <div>
              <h1 className="text-xl font-bold tracking-tight text-[var(--ink)] flex items-center gap-2">
                Ecosystem Productivity & Anomaly Engine
                <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200">
                  Researcher Suite
                </span>
              </h1>
              <p className="text-xs text-[var(--ink-muted)]">
                Longitudinal multi-series correlation (Chlorophyll-a, SST, CMFRI Catch) & automated causal attribution for fish stock decline.
              </p>
            </div>
          </div>
        </div>

        {/* Export & Action Buttons */}
        <div className="flex items-center gap-2">
          {/* Quick toggle for Researcher AI Fellow */}
          <button
            type="button"
            onClick={() => setActiveTab(activeTab === "chat" ? "chart" : "chat")}
            className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-bold rounded-lg transition-all cursor-pointer shadow-xs ${activeTab === "chat"
                ? "bg-slate-700 hover:bg-slate-800 text-white"
                : "bg-teal-600 hover:bg-teal-700 text-white"
              }`}
            title={activeTab === "chat" ? "View time-series charts" : "Open Researcher AI Assistant"}
          >
            <Bot className="w-3.5 h-3.5" />
            <span>{activeTab === "chat" ? "📊 View Charts" : "💬 Ask AI Fellow"}</span>
          </button>
          <button
            type="button"
            onClick={handleExportCSV}
            disabled={!series.length}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg bg-[var(--surface)] hover:bg-[var(--surface-muted)] border border-[var(--border)] transition-colors cursor-pointer disabled:opacity-50 shadow-2xs"
            title="Download complete aligned CSV dataset"
          >
            <Download className="w-3.5 h-3.5 text-emerald-600" />
            <span>Export CSV</span>
          </button>
          <button
            type="button"
            onClick={handleExportMarkdown}
            disabled={!diagnosis}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg bg-[#0C6E8C] hover:bg-[#09576F] text-white transition-colors cursor-pointer disabled:opacity-50 shadow-xs"
            title="Download researcher brief report"
          >
            <FileText className="w-3.5 h-3.5 text-white" />
            <span>Research Brief</span>
          </button>
          <a
            href="/Tarang_Researcher_Data_Extraction_Methodology.pdf"
            download="Tarang_Researcher_Data_Extraction_Methodology.pdf"
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg bg-[var(--surface)] hover:bg-[var(--surface-muted)] border border-[var(--border)] transition-colors cursor-pointer shadow-2xs text-[var(--ink)]"
            title="Download complete scientific data extraction methodology PDF"
          >
            <FileText className="w-3.5 h-3.5 text-teal-600" />
            <span>Methodology PDF</span>
          </a>
        </div>
      </div>

      {/* Control Bar: Region Selector & Time Window */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-3 bg-[var(--surface)] border border-[var(--border)] rounded-2xl p-3.5 shadow-2xs">
        {/* Region Pills */}
        <div className="flex items-center gap-1.5 overflow-x-auto pb-1 lg:pb-0">
          <span className="text-xs font-semibold text-[var(--ink-muted)] uppercase tracking-wider mr-1 hidden sm:inline">
            Region:
          </span>
          {PRESET_REGIONS.map((reg) => {
            const isSelected = selectedRegion === reg.id;
            return (
              <button
                key={reg.id}
                type="button"
                onClick={() => setSelectedRegion(reg.id)}
                className={`px-3 py-1.5 rounded-xl text-xs font-semibold flex items-center gap-1.5 transition-all cursor-pointer shrink-0 ${isSelected
                    ? "bg-[#0C6E8C] text-white shadow-xs"
                    : "bg-[var(--surface-muted)] text-[var(--ink-muted)] hover:text-[var(--ink)] hover:bg-[var(--border)]/60"
                  }`}
              >
                <span>{reg.emoji}</span>
                <span>{reg.name}</span>
                <span className={`text-[10px] ${isSelected ? "text-cyan-200" : "text-[var(--ink-subtle)]"}`}>
                  ({reg.state})
                </span>
              </button>
            );
          })}
        </div>

        {/* Time Window Buttons */}
        <div className="flex items-center gap-1.5 self-end lg:self-auto shrink-0">
          <span className="text-xs font-semibold text-[var(--ink-muted)] uppercase tracking-wider mr-1 hidden sm:inline">
            Window:
          </span>
          {[
            { label: "2018–2024 (7-Yr)", start: 2018, end: 2024 },
            { label: "2021–2024 (4-Yr)", start: 2021, end: 2024 },
            { label: "2023–2024 (El Niño)", start: 2023, end: 2024 },
          ].map((w) => {
            const isSelected = startYear === w.start && endYear === w.end;
            return (
              <button
                key={w.label}
                type="button"
                onClick={() => {
                  setStartYear(w.start);
                  setEndYear(w.end);
                }}
                className={`px-2.5 py-1 text-[11px] font-semibold rounded-lg transition-all cursor-pointer ${isSelected
                    ? "bg-[var(--ink)] text-[var(--surface)] shadow-2xs"
                    : "text-[var(--ink-muted)] hover:text-[var(--ink)] bg-[var(--surface-muted)]"
                  }`}
              >
                {w.label}
              </button>
            );
          })}
        </div>
      </div>

      {/* Primary View Switcher: Interactive Charts vs Bio-Oceanographic AI Assistant */}
      <div className="flex items-center justify-between border-b border-[var(--border)] pb-2 pt-0.5">
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => setActiveTab("chart")}
            className={`px-3.5 py-1.5 rounded-xl text-xs font-bold flex items-center gap-2 transition-all cursor-pointer ${activeTab === "chart"
                ? "bg-[#0C6E8C] text-white shadow-xs"
                : "bg-[var(--surface-muted)] text-[var(--ink-muted)] hover:text-[var(--ink)]"
              }`}
          >
            <TrendingUp className="w-4 h-4" />
            <span>Time-Series Chart & Anomaly Analysis</span>
          </button>

          <button
            type="button"
            onClick={() => setActiveTab("chat")}
            className={`px-3.5 py-1.5 rounded-xl text-xs font-bold flex items-center gap-2 transition-all cursor-pointer ${activeTab === "chat"
                ? "bg-teal-600 text-white shadow-xs"
                : "bg-teal-50 dark:bg-teal-950/40 text-teal-800 dark:text-teal-300 border border-teal-200 dark:border-teal-800/60 hover:bg-teal-100"
              }`}
          >
            <Bot className="w-4 h-4 text-teal-600 dark:text-teal-300" />
            <span>Bio-Oceanographic AI Assistant</span>
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
          </button>
        </div>

        {activeTab === "chart" && (
          <button
            type="button"
            onClick={() => {
              const el = document.getElementById("researcher-chatbot-section");
              if (el) el.scrollIntoView({ behavior: "smooth" });
            }}
            className="hidden sm:flex items-center gap-1 text-xs text-teal-700 dark:text-teal-400 hover:underline font-medium cursor-pointer"
          >
            <span>Jump to AI Chatbot</span>
            <span>↓</span>
          </button>
        )}
      </div>

      {/* TAB CONTENT: Dedicated Chatbot View */}
      {activeTab === "chat" && (
        <div className="space-y-4">
          <div className="bg-teal-50 border border-teal-200 rounded-2xl p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div>
              <h2 className="text-sm font-bold text-teal-950 flex items-center gap-2">
                <Bot className="w-4 h-4 text-teal-600" />
                Bio-Oceanographic AI Assistant · {data?.metadata?.name || "Coastal Waters"}
              </h2>
              <p className="text-xs text-teal-900 mt-0.5">
                Specialized in causal oceanographic modeling, Chlorophyll-a drop correlation, Marine Heatwaves, and CMFRI fish stock diagnostics.
              </p>
            </div>
            <button
              type="button"
              onClick={() => setActiveTab("chart")}
              className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-white border border-teal-300 text-teal-900 hover:bg-teal-50 cursor-pointer shrink-0"
            >
              ← Back to Time-Series Charts
            </button>
          </div>

          <ResearcherChatbot
            regionId={selectedRegion}
            regionName={data?.metadata?.name || "Selected Coastal Region"}
            dominantSpecies={data?.metadata?.dominant_species || []}
          />
        </div>
      )}

      {/* TAB CONTENT: Chart & Analysis View */}
      {activeTab === "chart" && (
        <>
          {/* Main Interactive Chart Card */}
          <div className="bg-[var(--surface)] border border-[var(--border)] rounded-2xl p-4 sm:p-5 shadow-xs space-y-4">
            {/* Chart Header & Legend Controls */}
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-[var(--border)] pb-3">
              <div>
                <h2 className="text-sm font-bold text-[var(--ink)] flex items-center gap-2">
                  <span>{data?.metadata?.name || "Coastal Waters"}</span>
                  <span className="text-xs font-normal text-[var(--ink-muted)]">
                    · {data?.metadata?.time_range} ({series.length} monthly observations)
                  </span>
                </h2>
                <p className="text-[11px] text-[var(--ink-muted)] mt-0.5">
                  Dominant target fisheries: {data?.metadata?.dominant_species?.join(", ")}
                </p>
              </div>

              {/* Toggle Series Controls */}
              <div className="flex items-center gap-2 flex-wrap text-xs">
                {/* Chlorophyll */}
                <button
                  type="button"
                  onClick={() => setShowChl(!showChl)}
                  className={`flex items-center gap-1.5 px-2.5 py-1 rounded-lg border transition-all cursor-pointer font-medium ${showChl
                      ? "bg-emerald-50 border-emerald-300 text-emerald-900 font-semibold"
                      : "bg-[var(--surface-muted)] border-[var(--border)] text-[var(--ink-muted)] opacity-60"
                    }`}
                >
                  <span className="w-2.5 h-2.5 rounded-full bg-emerald-500" />
                  <span>Chlorophyll-a (mg/m³)</span>
                </button>

                {/* SST */}
                <button
                  type="button"
                  onClick={() => setShowSst(!showSst)}
                  className={`flex items-center gap-1.5 px-2.5 py-1 rounded-lg border transition-all cursor-pointer font-medium ${showSst
                      ? "bg-rose-50 border-rose-300 text-rose-900 font-semibold"
                      : "bg-[var(--surface-muted)] border-[var(--border)] text-[var(--ink-muted)] opacity-60"
                    }`}
                >
                  <span className="w-2.5 h-2.5 rounded-full bg-rose-500" />
                  <span>SST (°C)</span>
                </button>

                {/* Catch */}
                <button
                  type="button"
                  onClick={() => setShowCatch(!showCatch)}
                  className={`flex items-center gap-1.5 px-2.5 py-1 rounded-lg border transition-all cursor-pointer font-medium ${showCatch
                      ? "bg-cyan-50 border-cyan-300 text-cyan-900 font-semibold"
                      : "bg-[var(--surface-muted)] border-[var(--border)] text-[var(--ink-muted)] opacity-60"
                    }`}
                >
                  <span className="w-2.5 h-2.5 rounded-sm bg-cyan-600" />
                  <span>Reported Catch (Tonnes)</span>
                </button>

                {/* Anomaly Highlight Toggle */}
                <button
                  type="button"
                  onClick={() => setShowAnomalies(!showAnomalies)}
                  className={`flex items-center gap-1.5 px-2.5 py-1 rounded-lg border transition-all cursor-pointer font-medium ${showAnomalies
                      ? "bg-amber-50 border-amber-300 text-amber-900 font-semibold"
                      : "bg-[var(--surface-muted)] border-[var(--border)] text-[var(--ink-muted)] opacity-60"
                    }`}
                >
                  <AlertTriangle className="w-3 h-3 text-amber-600" />
                  <span>Anomaly Bands</span>
                </button>
              </div>
            </div>

            {/* SVG Time-Series Chart */}
            <div className="relative w-full overflow-hidden select-none">
              {isLoading ? (
                <div className="w-full h-[340px] flex flex-col items-center justify-center gap-2 bg-[var(--surface-muted)] rounded-xl animate-pulse">
                  <RefreshCw className="w-6 h-6 animate-spin text-[#0C6E8C]" />
                  <span className="text-xs text-[var(--ink-muted)]">Aligning satellite ocean color & CMFRI catch time-series...</span>
                </div>
              ) : error ? (
                <div className="w-full h-[340px] flex items-center justify-center bg-rose-50 border border-rose-200 rounded-xl p-4 text-xs text-rose-800">
                  {error}
                </div>
              ) : (
                <div className="relative">
                  <svg
                    ref={chartSvgRef}
                    viewBox={`0 0 ${chartWidth} ${chartHeight}`}
                    className="w-full h-auto cursor-crosshair overflow-visible"
                    onMouseMove={handleMouseMove}
                    onMouseLeave={() => setHoverIndex(null)}
                  >
                    <defs>
                      {/* Chlorophyll Area Gradient */}
                      <linearGradient id="chlGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="#10B981" stopOpacity="0.28" />
                        <stop offset="100%" stopColor="#10B981" stopOpacity="0.0" />
                      </linearGradient>

                      {/* Catch Area Gradient */}
                      <linearGradient id="catchGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="#0891B2" stopOpacity="0.18" />
                        <stop offset="100%" stopColor="#0891B2" stopOpacity="0.0" />
                      </linearGradient>
                    </defs>

                    {/* Horizontal Gridlines */}
                    {[0, 0.25, 0.5, 0.75, 1].map((pct) => {
                      const y = padding.top + pct * innerHeight;
                      return (
                        <line
                          key={pct}
                          x1={padding.left}
                          y1={y}
                          x2={padding.left + innerWidth}
                          y2={y}
                          stroke="currentColor"
                          className="text-[var(--border)] opacity-60"
                          strokeDasharray="3 3"
                        />
                      );
                    })}

                    {/* Anomaly Shading Bands */}
                    {showAnomalies &&
                      series.map((p, i) => {
                        if (p.anomaly_flag === "nominal") return null;
                        const x = getX(i) - (innerWidth / series.length) * 0.5;
                        const bandWidth = innerWidth / series.length;
                        const isMhw = p.anomaly_flag === "thermal_mhw";
                        return (
                          <rect
                            key={i}
                            x={x}
                            y={padding.top}
                            width={bandWidth}
                            height={innerHeight}
                            fill={isMhw ? "#EF4444" : "#F59E0B"}
                            opacity={hoverIndex === i ? 0.28 : 0.14}
                            className="transition-opacity"
                          />
                        );
                      })}

                    {/* Left Y-Axis Labels (Chlorophyll & SST) */}
                    <text
                      x={padding.left - 10}
                      y={padding.top - 18}
                      textAnchor="end"
                      className="font-mono text-[9px] fill-emerald-700 font-bold"
                    >
                      CHL (mg/m³)
                    </text>
                    <text
                      x={padding.left - 10}
                      y={padding.top - 6}
                      textAnchor="end"
                      className="font-mono text-[9px] fill-rose-700 font-bold"
                    >
                      SST (°C)
                    </text>
                    {[0, 0.5, 1].map((pct) => {
                      const y = padding.top + (1 - pct) * innerHeight;
                      const chlVal = (minChl + pct * (maxChl - minChl)).toFixed(1);
                      const sstVal = (minSst + pct * (maxSst - minSst)).toFixed(0);
                      return (
                        <g key={pct}>
                          <text
                            x={padding.left - 10}
                            y={y + 3}
                            textAnchor="end"
                            className="font-mono text-[9px] fill-[var(--ink-muted)] font-medium"
                          >
                            {chlVal} / {sstVal}°
                          </text>
                        </g>
                      );
                    })}

                    {/* Right Y-Axis Labels (Catch Tonnes) */}
                    <text
                      x={padding.left + innerWidth + 10}
                      y={padding.top - 10}
                      textAnchor="start"
                      className="font-mono text-[9px] fill-cyan-800 font-bold"
                    >
                      LANDINGS (T)
                    </text>
                    {[0, 0.5, 1].map((pct) => {
                      const y = padding.top + (1 - pct) * innerHeight;
                      const catchVal = Math.round((pct * maxCatch) / 1000);
                      return (
                        <text
                          key={pct}
                          x={padding.left + innerWidth + 10}
                          y={y + 3}
                          textAnchor="start"
                          className="font-mono text-[9px] fill-cyan-700 font-medium"
                        >
                          {catchVal}k T
                        </text>
                      );
                    })}

                    {/* Series 1: Reported Catch (Area + Bars) */}
                    {showCatch && (
                      <g>
                        <path d={catchAreaPath} fill="url(#catchGrad)" />
                        <path
                          d={catchPath}
                          fill="none"
                          stroke="#0891B2"
                          strokeWidth="2.2"
                          strokeLinejoin="round"
                          strokeLinecap="round"
                        />
                      </g>
                    )}

                    {/* Series 2: Chlorophyll-a (Filled Area + Curve) */}
                    {showChl && (
                      <g>
                        <path d={chlAreaPath} fill="url(#chlGrad)" />
                        <path
                          d={chlPath}
                          fill="none"
                          stroke="#10B981"
                          strokeWidth="2.4"
                          strokeLinejoin="round"
                          strokeLinecap="round"
                        />
                      </g>
                    )}

                    {/* Series 3: SST Baseline (Dashed) & Actual SST (Line) */}
                    {showSst && (
                      <g>
                        <path
                          d={sstBaselinePath}
                          fill="none"
                          stroke="#F43F5E"
                          strokeWidth="1.2"
                          strokeDasharray="4 4"
                          opacity="0.6"
                        />
                        <path
                          d={sstPath}
                          fill="none"
                          stroke="#E11D48"
                          strokeWidth="2.2"
                          strokeLinejoin="round"
                          strokeLinecap="round"
                        />
                      </g>
                    )}

                    {/* X-Axis Month Labels (sparse every 6 months) */}
                    {series.map((p, i) => {
                      if (i % 6 !== 0 && i !== series.length - 1) return null;
                      const x = getX(i);
                      const y = padding.top + innerHeight + 18;
                      return (
                        <g key={i}>
                          <line
                            x1={x}
                            y1={padding.top + innerHeight}
                            x2={x}
                            y2={padding.top + innerHeight + 4}
                            stroke="currentColor"
                            className="text-[var(--border)]"
                          />
                          <text
                            x={x}
                            y={y}
                            textAnchor="middle"
                            className="font-mono text-[9px] fill-[var(--ink-muted)]"
                          >
                            {p.month}
                          </text>
                        </g>
                      );
                    })}

                    {/* Crosshair Cursor & Indicator Dots */}
                    {hoverIndex !== null && series[hoverIndex] && (
                      <g>
                        <line
                          x1={getX(hoverIndex)}
                          y1={padding.top}
                          x2={getX(hoverIndex)}
                          y2={padding.top + innerHeight}
                          stroke="currentColor"
                          className="text-[var(--ink)] opacity-70"
                          strokeDasharray="2 2"
                          strokeWidth="1.5"
                        />
                        {showChl && (
                          <circle
                            cx={getX(hoverIndex)}
                            cy={getYChl(series[hoverIndex].chlorophyll_mg_m3)}
                            r="4.5"
                            fill="#10B981"
                            stroke="#FFFFFF"
                            strokeWidth="2"
                            className="shadow-sm"
                          />
                        )}
                        {showSst && (
                          <circle
                            cx={getX(hoverIndex)}
                            cy={getYSst(series[hoverIndex].sst_celsius)}
                            r="4.5"
                            fill="#E11D48"
                            stroke="#FFFFFF"
                            strokeWidth="2"
                            className="shadow-sm"
                          />
                        )}
                        {showCatch && (
                          <circle
                            cx={getX(hoverIndex)}
                            cy={getYCatch(series[hoverIndex].catch_tonnes)}
                            r="4.5"
                            fill="#0891B2"
                            stroke="#FFFFFF"
                            strokeWidth="2"
                            className="shadow-sm"
                          />
                        )}
                      </g>
                    )}
                  </svg>

                  {/* Floating Tooltip Box */}
                  {hoveredPoint && (
                    <div className="mt-3 p-3 bg-[var(--surface-muted)]/90 border border-[var(--border)] rounded-xl flex flex-wrap items-center justify-between gap-4 text-xs shadow-2xs">
                      <div className="flex items-center gap-2">
                        <span className="font-mono font-bold text-sm text-[var(--ink)]">
                          📅 {hoveredPoint.month}
                        </span>
                        {hoveredPoint.anomaly_flag !== "nominal" && (
                          <span
                            className={`text-[10px] font-bold px-2 py-0.5 rounded-full uppercase ${hoveredPoint.anomaly_flag === "thermal_mhw"
                                ? "bg-rose-100 text-rose-800 border border-rose-200"
                                : "bg-amber-100 text-amber-800 border border-amber-200"
                              }`}
                          >
                            {hoveredPoint.anomaly_flag === "thermal_mhw" ? "🔥 Marine Heatwave" : "📉 Chlorophyll Deficit"}
                          </span>
                        )}
                      </div>

                      <div className="flex items-center gap-4 flex-wrap">
                        {/* CHL Readout */}
                        <div className="flex items-center gap-1.5">
                          <span className="w-2 h-2 rounded-full bg-emerald-500" />
                          <span className="text-[var(--ink-muted)]">Chlorophyll:</span>
                          <span className="font-mono font-bold text-emerald-700">
                            {hoveredPoint.chlorophyll_mg_m3} mg/m³
                          </span>
                          <span className="text-[10px] text-[var(--ink-subtle)]">
                            (Z: {hoveredPoint.chlorophyll_anomaly_z >= 0 ? `+${hoveredPoint.chlorophyll_anomaly_z}` : hoveredPoint.chlorophyll_anomaly_z})
                          </span>
                        </div>

                        {/* SST Readout */}
                        <div className="flex items-center gap-1.5">
                          <span className="w-2 h-2 rounded-full bg-rose-500" />
                          <span className="text-[var(--ink-muted)]">SST:</span>
                          <span className="font-mono font-bold text-rose-700">
                            {hoveredPoint.sst_celsius}°C
                          </span>
                          <span
                            className={`text-[10px] font-semibold ${hoveredPoint.sst_anomaly_celsius >= 1.0 ? "text-rose-600 font-bold" : "text-[var(--ink-subtle)]"
                              }`}
                          >
                            ({hoveredPoint.sst_anomaly_celsius >= 0 ? `+${hoveredPoint.sst_anomaly_celsius}` : hoveredPoint.sst_anomaly_celsius}°C vs base)
                          </span>
                        </div>

                        {/* Catch Readout */}
                        <div className="flex items-center gap-1.5">
                          <span className="w-2 h-2 rounded-sm bg-cyan-600" />
                          <span className="text-[var(--ink-muted)]">Catch:</span>
                          <span className="font-mono font-bold text-cyan-800">
                            {hoveredPoint.catch_tonnes.toLocaleString()} Tonnes
                          </span>
                          <span className="text-[10px] text-[var(--ink-subtle)]">
                            ({Math.round((hoveredPoint.catch_tonnes / hoveredPoint.catch_baseline_tonnes) * 100)}% of norm)
                          </span>
                        </div>
                      </div>

                      {hoveredPoint.event_description && (
                        <div className="w-full text-[11px] text-amber-900 bg-amber-50 p-2 rounded-lg border border-amber-200">
                          <strong>Ecological Driver:</strong> {hoveredPoint.event_description}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>

          {/* Statistical Telemetry Grid: Correlations & Anomaly Indicators */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {/* Card 1: Chlorophyll ↔ Catch Correlation */}
            <div className="bg-[var(--surface)] border border-[var(--border)] rounded-2xl p-4 shadow-2xs space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-emerald-800 uppercase tracking-wider flex items-center gap-1.5">
                  <span className="w-2 h-2 rounded-full bg-emerald-500" />
                  Trophic Coupling
                </span>
                <span className="font-mono text-xs font-bold text-[var(--ink-muted)]">
                  p = {correlations?.chl_vs_catch?.p_value ?? 0.001}
                </span>
              </div>
              <div className="flex items-baseline gap-2">
                <span className="text-2xl font-black font-mono text-[var(--ink)]">
                  r = {correlations?.chl_vs_catch?.r ?? 0.45}
                </span>
                <span className="text-[11px] text-emerald-800 bg-emerald-50 px-2 py-0.5 rounded-full font-semibold border border-emerald-200">
                  Bottom-Up Driver
                </span>
              </div>
              <p className="text-[11px] text-[var(--ink-muted)] leading-relaxed">
                {correlations?.chl_vs_catch?.interpretation ||
                  "Abundance of primary phytoplankton biomass directly dictates pelagic foraging schools and landing volume."}
              </p>
            </div>

            {/* Card 2: SST Anomaly ↔ Catch Correlation */}
            <div className="bg-[var(--surface)] border border-[var(--border)] rounded-2xl p-4 shadow-2xs space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-rose-800 uppercase tracking-wider flex items-center gap-1.5">
                  <span className="w-2 h-2 rounded-full bg-rose-500" />
                  Thermal Stress Impact
                </span>
                <span className="font-mono text-xs font-bold text-[var(--ink-muted)]">
                  p = {correlations?.sst_anomaly_vs_catch?.p_value ?? 0.001}
                </span>
              </div>
              <div className="flex items-baseline gap-2">
                <span className="text-2xl font-black font-mono text-[var(--ink)]">
                  r = {correlations?.sst_anomaly_vs_catch?.r ?? -0.39}
                </span>
                <span className="text-[11px] text-rose-800 bg-rose-50 px-2 py-0.5 rounded-full font-semibold border border-rose-200">
                  Thermal Avoidance
                </span>
              </div>
              <p className="text-[11px] text-[var(--ink-muted)] leading-relaxed">
                {correlations?.sst_anomaly_vs_catch?.interpretation ||
                  "Positive sea surface thermal anomalies drive pelagic shoals into deeper cooler layers beyond traditional artisanal gear."}
              </p>
            </div>

            {/* Card 3: Ecological Stress Index */}
            <div className="bg-[var(--surface)] border border-[var(--border)] rounded-2xl p-4 shadow-2xs space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-amber-800 uppercase tracking-wider flex items-center gap-1.5">
                  <AlertTriangle className="w-3.5 h-3.5 text-amber-600" />
                  Ecosystem Stress Level
                </span>
                <span className="font-mono text-xs font-bold text-amber-700">
                  Score: {anomalies?.stress_index ?? 75}/100
                </span>
              </div>
              <div className="flex items-baseline gap-2">
                <span className="text-base font-bold text-[var(--ink)]">
                  {anomalies?.stress_label || "Severe Ecological Disruption"}
                </span>
              </div>
              <div className="flex items-center gap-3 text-[11px] text-[var(--ink-muted)] pt-1">
                <span>🔥 {anomalies?.marine_heatwave_months ?? 0} MHW Months</span>
                <span>·</span>
                <span>📉 {anomalies?.chlorophyll_deficit_months ?? 0} Deficit Months</span>
              </div>
            </div>
          </div>

          {/* Deep Scientific Causal Attribution Panel */}
          {diagnosis && (
            <div className="bg-[var(--surface)] border border-[var(--border)] rounded-2xl p-5 shadow-xs space-y-5">
              <div className="border-b border-[var(--border)] pb-3">
                <h3 className="text-base font-bold text-[var(--ink)] flex items-center gap-2">
                  <Sparkles className="w-4 h-4 text-[#0C6E8C]" />
                  Scientific Causal Attribution: Why Did Fish Productivity Decline?
                </h3>
                <p className="text-xs text-[var(--ink-muted)] mt-0.5">
                  Synthesized by cross-referencing INCOIS physical ocean color with ICAR-CMFRI biological recruitment benchmarks.
                </p>
              </div>

              {/* Causes List */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {diagnosis.primary_causes.map((cause, idx) => (
                  <div
                    key={idx}
                    className="bg-[var(--surface-muted)]/60 border border-[var(--border)] rounded-xl p-4 space-y-2.5 flex flex-col justify-between"
                  >
                    <div className="space-y-1.5">
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-bold text-[var(--ink)] flex items-center gap-1.5">
                          <span className="w-5 h-5 rounded-full bg-[#0C6E8C]/15 text-[#0C6E8C] flex items-center justify-center text-xs font-black">
                            {idx + 1}
                          </span>
                          {cause.driver}
                        </span>
                        <span
                          className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${cause.severity === "HIGH"
                              ? "bg-rose-100 text-rose-800"
                              : "bg-amber-100 text-amber-800"
                            }`}
                        >
                          {cause.severity}
                        </span>
                      </div>
                      <p className="text-xs text-[var(--ink-muted)] leading-relaxed">
                        {cause.mechanism}
                      </p>
                    </div>
                    <div className="pt-2 border-t border-[var(--border)] text-[10px] font-mono text-[#0C6E8C]">
                      Metric: {cause.empirical_metric}
                    </div>
                  </div>
                ))}
              </div>

              {/* Actionable Policy & Management Interventions */}
              <div className="space-y-2.5 pt-2">
                <span className="text-xs font-bold text-[var(--ink)] uppercase tracking-wider block">
                  💡 Evidence-Based Resource Management Interventions
                </span>
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                  {diagnosis.management_recommendations.map((rec, i) => (
                    <div
                      key={i}
                      className="bg-emerald-50/70 border border-emerald-200 rounded-xl p-3.5 space-y-1"
                    >
                      <span className="text-xs font-bold text-emerald-900 block">
                        ✓ {rec.action}
                      </span>
                      <p className="text-[11px] text-emerald-900 leading-relaxed">
                        {rec.detail}
                      </p>
                    </div>
                  ))}
                </div>
              </div>

              {/* Citations Footer */}
              <div className="bg-[var(--surface-muted)] px-3.5 py-2.5 rounded-xl border border-[var(--border)] text-[10px] text-[var(--ink-muted)] space-y-1">
                <strong>Data Provenance & Scientific References:</strong>
                <ul className="list-disc list-inside space-y-0.5 text-[var(--ink-subtle)]">
                  {diagnosis.data_citations.map((src, sIdx) => (
                    <li key={sIdx}>{src}</li>
                  ))}
                </ul>
              </div>
            </div>
          )}

          {/* Dedicated Researcher Bio-Oceanographic AI Chatbot */}
          <div id="researcher-chatbot-section" className="pt-3">
            <ResearcherChatbot
              regionId={selectedRegion}
              regionName={data?.metadata?.name || "Selected Coastal Region"}
              dominantSpecies={data?.metadata?.dominant_species || []}
            />
          </div>

          {/* Floating Trigger to switch to Assistant or scroll */}
          <button
            type="button"
            onClick={() => setActiveTab("chat")}
            className="fixed bottom-6 right-6 z-40 flex items-center gap-2 px-4 py-2.5 rounded-full bg-teal-600 hover:bg-teal-700 text-white font-bold text-xs shadow-xl hover:scale-105 transition-all cursor-pointer border border-white/20"
            title="Open Dedicated AI Assistant"
          >
            <Bot className="w-4 h-4 animate-bounce" />
            <span>Ask AI Fellow</span>
          </button>
        </>
      )}
    </div>
  );
};
