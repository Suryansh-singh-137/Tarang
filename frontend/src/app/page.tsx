"use client";

import React, { useState, useEffect } from "react";
import dynamic from "next/dynamic";
import {
  MessageSquare,
  Map as MapIcon,
  Activity,
  Layers,
  Sparkles,
  Shield,
  HelpCircle,
  Menu,
  X,
  Compass,
} from "lucide-react";

import { LandingHero } from "@/components/landing/LandingHero";
import { SidebarDashboard } from "@/components/dashboard/SidebarDashboard";
import { ChatPanel } from "@/components/chat/ChatPanel";
import { ChatInput } from "@/components/chat/ChatInput";
import { TracePanel } from "@/components/trace/TracePanel";
import { LanguageToggle } from "@/components/common/LanguageToggle";

import {
  Message,
  LanguageCode,
  ChatState,
  ProgressEventData,
  MapGeoJSON,
  RiskLabel,
  LiveConditionsSummary,
} from "@/lib/types";
import { streamQuery, API_BASE_URL } from "@/lib/api";
import { translations } from "@/lib/i18n";

// Dynamic Leaflet import to prevent any SSR hydration mismatch
const MarineMap = dynamic(
  () => import("@/components/map/MarineMap").then((mod) => mod.MarineMap),
  {
    ssr: false,
    loading: () => (
      <div className="w-full h-full min-h-[350px] bg-[#E2ECEE] rounded-xl flex items-center justify-center text-xs text-[var(--ink-muted)] animate-pulse">
        Initializing Marine Chart...
      </div>
    ),
  }
);

export default function Home() {
  const [viewMode, setViewMode] = useState<"landing" | "workspace">("landing");
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [progressSteps, setProgressSteps] = useState<ProgressEventData[]>([]);
  const [currentLanguage, setCurrentLanguage] = useState<LanguageCode>("en");
  const [detectedLanguage, setDetectedLanguage] = useState<string | null>(null);

  // Active mobile view tab
  const [mobileTab, setMobileTab] = useState<"chat" | "map" | "trace" | "dashboard">("chat");
  const [isTraceOpen, setIsTraceOpen] = useState(true);
  const [isMobileSidebarOpen, setIsMobileSidebarOpen] = useState(false);

  // GeoJSON and Risk state for Map and Dashboard
  const [mapGeoJson, setMapGeoJson] = useState<MapGeoJSON | null>(null);
  const [currentRiskLabel, setCurrentRiskLabel] = useState<RiskLabel>("LOW");
  const [liveConditions, setLiveConditions] = useState<LiveConditionsSummary | null>(null);
  const [activeCycloneAlert, setActiveCycloneAlert] = useState<{
    name: string;
    level: string;
    distanceKm: number;
    windSpeedKmh: number;
  } | null>(null);

  // Pipeline state for Multi-turn memory (M5)
  const [pipelineState, setPipelineState] = useState<ChatState>({
    conversation: [],
    last_parsed_intent: null,
    last_results: {},
  });

  const t = translations[currentLanguage] || translations.en;

  // Initial probe for live conditions on mount
  useEffect(() => {
    // Check if backend is available and initialize default conditions
    setLiveConditions({
      locationName: "Thoothukudi Harbour",
      lat: 8.7642,
      lon: 78.1348,
      waveHeightM: 0.85,
      windSpeedKmh: 11.8,
      seaState: "slight",
      riskLabel: "LOW",
      source: "Open-Meteo ERA5 / Live Marine",
      isFallback: false,
    });
  }, []);

  // Handle Query Submission
  const handleSendMessage = async (queryText: string) => {
    if (!queryText.trim() || isLoading) return;

    // Transition from landing page to workspace immediately upon query
    if (viewMode === "landing") {
      setViewMode("workspace");
    }

    const userMsgId = "user-" + Date.now();
    const assistantMsgId = "asst-" + Date.now();
    const timeStr = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });

    // Add user message
    const userMessage: Message = {
      id: userMsgId,
      role: "user",
      content: queryText,
      timestamp: timeStr,
    };

    // Add placeholder assistant message
    const assistantMessage: Message = {
      id: assistantMsgId,
      role: "assistant",
      content: "",
      timestamp: timeStr,
      isStreaming: true,
    };

    setMessages((prev) => [...prev, userMessage, assistantMessage]);
    setIsLoading(true);
    setProgressSteps([]);

    await streamQuery(
      queryText,
      pipelineState,
      {
        onProgress: (progressData) => {
          setProgressSteps((prev) => [...prev, progressData]);
        },
        onResult: (result) => {
          // Update assistant message
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === assistantMsgId
                ? {
                    ...msg,
                    content: result.answer_text,
                    language: result.language,
                    risk_data: result.risk_data,
                    evidence: result.evidence,
                    trace: result.trace,
                    map_geojson: result.map_geojson,
                    parsed_intent: result.parsed_intent,
                    isStreaming: false,
                  }
                : msg
            )
          );

          // Update multi-turn memory
          setPipelineState({
            conversation: result.conversation_history || [],
            last_parsed_intent: result.last_parsed_intent || null,
            last_results: result.last_results || {},
          });

          // Update map GeoJSON
          if (result.map_geojson && result.map_geojson.features) {
            setMapGeoJson(result.map_geojson);
          }

          // Update risk verdict
          if (result.risk_data?.risk_label) {
            setCurrentRiskLabel(result.risk_data.risk_label);
          }

          // Auto-update language chrome if detected
          if (result.language && (result.language === "hi" || result.language === "ta" || result.language === "en")) {
            setDetectedLanguage(result.language);
            setCurrentLanguage(result.language as LanguageCode);
          }

          // Update Live Conditions from weather agent result
          const weatherResult = result.last_results?.weather_agent;
          if (weatherResult && weatherResult.data) {
            const wData = weatherResult.data;
            setLiveConditions({
              locationName: result.parsed_intent?.location_name || "Target Location",
              lat: result.parsed_intent?.lat || 8.7642,
              lon: result.parsed_intent?.lon || 78.1348,
              waveHeightM: wData.wave_height_m || 1.0,
              windSpeedKmh: wData.wind_speed_kmh || 15.0,
              seaState: wData.sea_state || "moderate",
              riskLabel: result.risk_data?.risk_label || "LOW",
              source: weatherResult.source || "Open-Meteo",
              isFallback: weatherResult.used_fallback || false,
            });
          }

          // Update cyclone alert if hazard agent detected active cyclone
          const hazardResult = result.last_results?.hazard_agent;
          if (hazardResult && hazardResult.data?.cyclone_warning) {
            const hData = hazardResult.data;
            setActiveCycloneAlert({
              name: hData.cyclone_name || "Active Advisory",
              level: hData.cyclone_alert_level || "Warning",
              distanceKm: hData.cyclone_distance_km || 150,
              windSpeedKmh: hData.cyclone_wind_kmh || 95,
            });
          }

          setIsLoading(false);
        },
        onError: (err) => {
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === assistantMsgId
                ? {
                    ...msg,
                    content: `Error: ${err}. Please check your connection to Tarang backend.`,
                    isStreaming: false,
                    isError: true,
                  }
                : msg
            )
          );
          setIsLoading(false);
        },
      }
    );
  };

  const handleSelectLocation = (placeName: string) => {
    handleSendMessage(`Is it safe to fish near ${placeName} today?`);
  };

  const handleSelectPrompt = (promptText: string) => {
    handleSendMessage(promptText);
  };

  const handleStartVoiceLanding = () => {
    setViewMode("workspace");
    setMobileTab("chat");
  };

  // Get active query location name for map header
  const activeLocationName =
    messages[messages.length - 1]?.parsed_intent?.location_name ||
    liveConditions?.locationName ||
    "Coastal Waters";

  // Current active trace from latest assistant response or live progress steps
  const activeTrace =
    messages.filter((m) => m.role === "assistant" && m.trace && m.trace.length > 0).slice(-1)[0]?.trace ||
    progressSteps.map((p) => ({
      agent_name: p.agent_name || p.node,
      status: (p.status as any) || "success",
      summary: p.summary,
      source: p.source,
    }));

  const activeEvidence =
    messages.filter((m) => m.role === "assistant" && m.evidence && m.evidence.length > 0).slice(-1)[0]?.evidence ||
    [];

  return (
    <div className="flex flex-col h-screen overflow-hidden bg-[var(--neutral)] text-[var(--ink)]">
      {/* ── Top Navigation Bar: Hairline-thin Nav (Part 0 PRD) ── */}
      <header className="h-14 px-4 sm:px-8 bg-[var(--surface)] border-b border-[var(--border)] flex items-center justify-between shrink-0 z-30 shadow-2xs">
        <div className="flex items-center gap-6 sm:gap-8">
          {/* Mobile Sidebar Toggle (workspace mode) */}
          {viewMode === "workspace" && (
            <button
              type="button"
              onClick={() => setIsMobileSidebarOpen(!isMobileSidebarOpen)}
              className="lg:hidden p-2 text-[var(--ink-muted)] hover:text-[var(--ink)] hover:bg-[var(--foam)] rounded-lg min-h-[48px] min-w-[48px] flex items-center justify-center cursor-pointer"
              aria-label="Toggle navigation menu"
            >
              {isMobileSidebarOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
            </button>
          )}

          {/* Wordmark: TARANG in Instrument Serif / Fraunces with small-caps tracking ~0.18em */}
          <button
            type="button"
            onClick={() => setViewMode(messages.length === 0 ? "landing" : "workspace")}
            className="flex items-center gap-3 text-left group cursor-pointer"
          >
            <span className="font-serif-display text-lg sm:text-xl font-semibold tracking-wordmark text-[var(--ink)]">
              TARANG
            </span>
            {viewMode === "workspace" && (
              <span className="hidden md:inline-block text-xs text-[var(--ink-subtle)] font-normal border-l border-[var(--border)] pl-2.5">
                {t.appSubtitle}
              </span>
            )}
          </button>

          {/* Part 0 Instrument Nav Links: FLEET FORECAST ARCHIVE */}
          <div className="hidden sm:flex items-center gap-6 font-mono-data text-[11px] text-[var(--ink-muted)]">
            <button
              type="button"
              onClick={() => handleSendMessage("What is the fleet forecast for Tamil Nadu coast today?")}
              className="hover:text-[var(--current)] transition-colors tracking-wider cursor-pointer"
            >
              FLEET
            </button>
            <button
              type="button"
              onClick={() => handleSendMessage("Show me the sea weather forecast for today")}
              className="hover:text-[var(--current)] transition-colors tracking-wider cursor-pointer"
            >
              FORECAST
            </button>
            <button
              type="button"
              onClick={() => handleSendMessage("Show recent marine safety advisories and cyclone history")}
              className="hover:text-[var(--current)] transition-colors tracking-wider cursor-pointer"
            >
              ARCHIVE
            </button>
          </div>
        </div>

        {/* Right Nav Actions: Coordinates readout & Language Switcher */}
        <div className="flex items-center gap-3 sm:gap-4 font-mono-data text-[11px]">
          <span className="hidden lg:inline text-[var(--ink-subtle)]">EST. 2024 / COASTAL SYSTEMS</span>
          <span className="hidden lg:inline text-[var(--border)]">|</span>
          <span className="text-[var(--current)] font-medium">
            {liveConditions
              ? `${liveConditions.lat.toFixed(2)}°N, ${liveConditions.lon.toFixed(2)}°E`
              : "21.14°N"}
          </span>

          {/* Switch to Landing Page button if in workspace */}
          {viewMode === "workspace" && (
            <button
              type="button"
              onClick={() => setViewMode("landing")}
              className="font-sans text-xs font-medium text-[var(--ink-muted)] hover:text-[var(--current)] px-3 py-1.5 rounded-full hover:bg-[var(--foam)] transition-colors hidden sm:inline-block cursor-pointer"
            >
              Home
            </button>
          )}

          {/* Language Toggle (EN / हिं / த) */}
          <LanguageToggle
            currentLanguage={currentLanguage}
            onSelectLanguage={(lang) => setCurrentLanguage(lang)}
            detectedBadge={detectedLanguage}
          />
        </div>
      </header>

      {/* ── Main Content Area ── */}
      {viewMode === "landing" && messages.length === 0 ? (
        // Part 0: Serene Landing Hero Threshold
        <main className="flex-1 overflow-y-auto">
          <LandingHero
            language={currentLanguage}
            liveConditions={liveConditions}
            onStartVoice={handleStartVoiceLanding}
            onSubmitText={handleSendMessage}
            onSelectPrompt={handleSelectPrompt}
          />
        </main>
      ) : (
        // Part 1: Working 3-Panel Workspace (Desktop) & Tabbed Layout (Mobile)
        <main className="flex-1 flex overflow-hidden relative">
          {/* ── 1. Left Sidebar Dashboard (Desktop: ~300px, Mobile: Drawer) ── */}
          <div
            className={`
              fixed lg:relative top-16 lg:top-0 bottom-0 left-0 z-40
              w-72 sm:w-80 bg-[var(--surface)] border-r border-[var(--border)]
              transition-transform duration-300 ease-in-out shrink-0
              ${isMobileSidebarOpen ? "translate-x-0 shadow-xl" : "-translate-x-full lg:translate-x-0"}
              ${mobileTab === "dashboard" ? "translate-x-0 w-full" : ""}
            `}
          >
            <SidebarDashboard
              language={currentLanguage}
              liveConditions={liveConditions}
              activeCycloneAlert={activeCycloneAlert}
              onSelectLocation={(place) => {
                handleSelectLocation(place);
                setIsMobileSidebarOpen(false);
                if (mobileTab === "dashboard") setMobileTab("chat");
              }}
              onSelectPrompt={(prompt) => {
                handleSelectPrompt(prompt);
                setIsMobileSidebarOpen(false);
                if (mobileTab === "dashboard") setMobileTab("chat");
              }}
              className="h-full"
            />
          </div>

          {/* Mobile Overlay backdrop when drawer is open */}
          {isMobileSidebarOpen && (
            <div
              className="fixed inset-0 bg-black/30 z-30 lg:hidden"
              onClick={() => setIsMobileSidebarOpen(false)}
            />
          )}

          {/* ── 2. Center Column: Chat & Voice Interface (~45-50% width on Desktop) ── */}
          <div
            className={`
              flex-1 flex flex-col h-full overflow-hidden bg-[var(--neutral)] border-r border-[var(--border)]
              ${mobileTab !== "chat" ? "hidden lg:flex" : "flex"}
            `}
          >
            {/* Chat message stream with live SSE progress stepper */}
            <div className="flex-1 overflow-hidden">
              <ChatPanel
                messages={messages}
                isLoading={isLoading}
                progressSteps={progressSteps}
                language={currentLanguage}
                onSelectPrompt={handleSelectPrompt}
                onViewTrace={() => {
                  setMobileTab("trace");
                  setIsTraceOpen(true);
                }}
                className="h-full"
              />
            </div>

            {/* Bottom Input Area: Dominant 56px Mic Button + 48px Text Input */}
            <div className="p-3 sm:p-4 bg-[var(--surface)] border-t border-[var(--border)] shrink-0 z-10 shadow-xs">
              <ChatInput
                onSendMessage={handleSendMessage}
                isLoading={isLoading}
                language={currentLanguage}
              />
            </div>
          </div>

          {/* ── 3. Right Column: Marine Map & Collapsible Trace Panel (~35-40% on Desktop) ── */}
          <div
            className={`
              w-full lg:w-[420px] xl:w-[480px] shrink-0 h-full flex flex-col bg-[var(--surface-muted)] overflow-hidden
              ${mobileTab === "map" || mobileTab === "trace" ? "flex" : "hidden lg:flex"}
            `}
          >
            {/* Top half: Leaflet Interactive Marine Chart */}
            <div className={`p-3 shrink-0 ${mobileTab === "trace" ? "hidden lg:block h-[45%]" : "flex-1 lg:h-[50%]"}`}>
              <MarineMap
                geoJson={mapGeoJson}
                riskLabel={currentRiskLabel}
                locationName={activeLocationName}
                className="h-full"
              />
            </div>

            {/* Bottom half: Collapsible Reasoning Trace Panel */}
            <div className={`p-3 pt-0 flex-1 overflow-hidden ${mobileTab === "map" ? "hidden lg:flex" : "flex"}`}>
              <TracePanel
                trace={activeTrace}
                evidence={activeEvidence}
                language={currentLanguage}
                isOpen={isTraceOpen}
                onToggle={() => setIsTraceOpen(!isTraceOpen)}
                className="h-full w-full"
              />
            </div>
          </div>

          {/* ── Mobile Navigation Tabs Bar (< 1024px) ── */}
          <nav className="lg:hidden fixed bottom-0 left-0 right-0 h-14 bg-[var(--surface)] border-t border-[var(--border)] flex items-center justify-around z-20 shadow-lg px-2">
            <button
              type="button"
              onClick={() => setMobileTab("chat")}
              className={`flex flex-col items-center justify-center flex-1 h-full text-[11px] font-medium transition-colors ${
                mobileTab === "chat" ? "text-[var(--current)] font-semibold" : "text-[var(--ink-muted)]"
              }`}
            >
              <MessageSquare className="w-4 h-4 mb-0.5" />
              <span>{t.navChat}</span>
            </button>

            <button
              type="button"
              onClick={() => setMobileTab("map")}
              className={`flex flex-col items-center justify-center flex-1 h-full text-[11px] font-medium transition-colors ${
                mobileTab === "map" ? "text-[var(--current)] font-semibold" : "text-[var(--ink-muted)]"
              }`}
            >
              <MapIcon className="w-4 h-4 mb-0.5" />
              <span>{t.navMap}</span>
            </button>

            <button
              type="button"
              onClick={() => setMobileTab("trace")}
              className={`flex flex-col items-center justify-center flex-1 h-full text-[11px] font-medium transition-colors ${
                mobileTab === "trace" ? "text-[var(--current)] font-semibold" : "text-[var(--ink-muted)]"
              }`}
            >
              <Activity className="w-4 h-4 mb-0.5" />
              <span>{t.navTrace}</span>
            </button>

            <button
              type="button"
              onClick={() => setMobileTab("dashboard")}
              className={`flex flex-col items-center justify-center flex-1 h-full text-[11px] font-medium transition-colors ${
                mobileTab === "dashboard" ? "text-[var(--current)] font-semibold" : "text-[var(--ink-muted)]"
              }`}
            >
              <Compass className="w-4 h-4 mb-0.5" />
              <span>{t.navDashboard}</span>
            </button>
          </nav>
        </main>
      )}
    </div>
  );
}
