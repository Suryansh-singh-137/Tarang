"use client";

import React, { useState, useEffect } from "react";
import dynamic from "next/dynamic";
import { LandingHero } from "@/components/landing/LandingHero";
import { FeaturesSection } from "@/components/landing/FeaturesSection";
import { LandingFooter } from "@/components/landing/LandingFooter";
import { IconRail, ActiveTab } from "@/components/navigation/IconRail";
import { ChatPanel } from "@/components/chat/ChatPanel";
import { ChatInput } from "@/components/chat/ChatInput";
import { AlertsView } from "@/components/alerts/AlertsView";
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
import { streamQuery } from "@/lib/api";
import { translations } from "@/lib/i18n";

// Dynamic Leaflet import to prevent any SSR hydration mismatch
const MarineMap = dynamic(
  () => import("@/components/map/MarineMap").then((mod) => mod.MarineMap),
  {
    ssr: false,
    loading: () => (
      <div className="w-full h-full min-h-[350px] bg-[#E2ECEE] rounded-2xl flex items-center justify-center text-xs text-[var(--ink-muted)] animate-pulse">
        Initializing Marine Chart...
      </div>
    ),
  }
);

export default function Home() {
  const [viewMode, setViewMode] = useState<"landing" | "workspace">("landing");
  const [activeTab, setActiveTab] = useState<ActiveTab>("chat");

  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [progressSteps, setProgressSteps] = useState<ProgressEventData[]>([]);
  const [currentLanguage, setCurrentLanguage] = useState<LanguageCode>("en");
  const [detectedLanguage, setDetectedLanguage] = useState<string | null>(null);

  // GeoJSON and Risk state for Map and Dashboard
  const [mapGeoJson, setMapGeoJson] = useState<MapGeoJSON | null>(null);
  const [currentRiskLabel, setCurrentRiskLabel] = useState<RiskLabel>("LOW");
  const [liveConditions, setLiveConditions] = useState<LiveConditionsSummary>({
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

  const [userCoords, setUserCoords] = useState<{ lat: number; lon: number } | null>(null);
  const [isManualLanguageOverride, setIsManualLanguageOverride] = useState(false);

  const t = translations[currentLanguage] || translations.en;

  // Initial probe for live conditions and browser geolocation on mount
  useEffect(() => {
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

    // Request browser geolocation on mount (permission prompt on first load)
    if (typeof navigator !== "undefined" && navigator.geolocation) {
      navigator.geolocation.getCurrentPosition(
        (position) => {
          const lat = position.coords.latitude;
          const lon = position.coords.longitude;
          setUserCoords({ lat, lon });
          setLiveConditions((prev) => ({
            ...prev,
            lat,
            lon,
            locationName: "Your Coastal Location",
          }));
        },
        (err) => {
          console.info("Browser geolocation unavailable or dismissed:", err.message);
        },
        { timeout: 8000, maximumAge: 300000 }
      );
    }
  }, []);

  // Handle Query Submission
  const handleSendMessage = async (queryText: string) => {
    if (!queryText.trim() || isLoading) return;

    // Transition from landing page to workspace immediately upon query
    if (viewMode === "landing") {
      setViewMode("workspace");
    }
    setActiveTab("chat");

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

          // Only auto-update language chrome if user has not set a manual override
          if (!isManualLanguageOverride && result.language && (result.language === "hi" || result.language === "ta" || result.language === "en")) {
            setDetectedLanguage(result.language);
            setCurrentLanguage(result.language as LanguageCode);
          }

          // Update Live Conditions from weather agent result
          const weatherResult = result.last_results?.weather_agent;
          if (weatherResult && weatherResult.data) {
            const wData = weatherResult.data;
            setLiveConditions({
              locationName: result.parsed_intent?.location_name || (userCoords ? "Your Coastal Location" : "Target Location"),
              lat: result.parsed_intent?.lat || userCoords?.lat || 8.7642,
              lon: result.parsed_intent?.lon || userCoords?.lon || 78.1348,
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
      },
      {
        user_lat: userCoords?.lat ?? null,
        user_lon: userCoords?.lon ?? null,
        user_location_name: userCoords ? "Your Coastal Location" : null,
        language: currentLanguage,
      }
    );
  };

  const handleSelectLanguage = (lang: LanguageCode) => {
    setCurrentLanguage(lang);
    setIsManualLanguageOverride(true);
  };

  const handleSelectPrompt = (promptText: string) => {
    handleSendMessage(promptText);
  };

  const handleStartVoiceLanding = () => {
    setViewMode("workspace");
    setActiveTab("chat");
  };

  const handleIntelligenceClick = () => {
    if (viewMode === "landing" && messages.length === 0) {
      const el = document.getElementById("features");
      if (el) {
        el.scrollIntoView({ behavior: "smooth" });
        return;
      }
    }
    handleSendMessage("What are the six specialized agents and data sources in Tarang?");
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
          {/* Wordmark: tarang. in Instrument Serif with trailing period per PRD Part 0 rule 7 */}
          <button
            type="button"
            onClick={() => setViewMode(messages.length === 0 ? "landing" : "workspace")}
            className="flex items-center gap-3 text-left group cursor-pointer"
          >
            <span className="font-serif-display text-xl sm:text-2xl font-normal text-[var(--ink)] tracking-tight">
              tarang.
            </span>
            {viewMode === "workspace" && (
              <span className="hidden md:inline-block text-xs text-[var(--ink-subtle)] font-normal border-l border-[var(--border)] pl-2.5">
                {t.appSubtitle}
              </span>
            )}
          </button>

          {/* Nav Links: INTELLIGENCE FLEET ARCHIVE */}
          <div className="hidden sm:flex items-center gap-6 font-mono-data text-[11px] text-[var(--ink-muted)]">
            <button
              type="button"
              onClick={handleIntelligenceClick}
              className="hover:text-[var(--current)] transition-colors tracking-editorial cursor-pointer uppercase"
            >
              INTELLIGENCE
            </button>
            <button
              type="button"
              onClick={() => handleSendMessage("What is the fleet forecast for Tamil Nadu coast today?")}
              className="hover:text-[var(--current)] transition-colors tracking-editorial cursor-pointer uppercase"
            >
              FLEET
            </button>
            <button
              type="button"
              onClick={() => handleSendMessage("Show recent marine safety advisories and cyclone history")}
              className="hover:text-[var(--current)] transition-colors tracking-editorial cursor-pointer uppercase"
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
            onSelectLanguage={handleSelectLanguage}
            detectedBadge={detectedLanguage}
          />
        </div>
      </header>

      {/* ── Main Content Area ── */}
      {viewMode === "landing" && messages.length === 0 ? (
        // Part 0 & 0.1: Asymmetric Hero + Below-the-fold Features + Quiet Hairline Footer
        <main className="flex-1 overflow-y-auto">
          <LandingHero
            language={currentLanguage}
            liveConditions={liveConditions}
            onStartVoice={handleStartVoiceLanding}
            onSubmitText={handleSendMessage}
            onSelectPrompt={handleSelectPrompt}
          />
          <div id="features">
            <FeaturesSection language={currentLanguage} />
          </div>
          <LandingFooter />
        </main>
      ) : (
        // Part 1: Icon Rail Navigation Model (Desktop 64px rail, Mobile 56px bottom tabs)
        <div className="flex-1 flex overflow-hidden relative">
          {/* ── Icon Rail (Navigation Destinations: Chat, Map, Alerts, Trace) ── */}
          <IconRail
            activeTab={activeTab}
            onSelectTab={(tab) => setActiveTab(tab)}
            hasMapData={Boolean(mapGeoJson?.features?.length)}
            hasActiveAlert={Boolean(activeCycloneAlert)}
            hasTraceData={Boolean(activeTrace && activeTrace.length > 0)}
          />

          {/* ── Active View Container (Only ONE view active at a time) ── */}
          <main className="flex-1 flex flex-col h-full overflow-hidden relative">
            {/* Destination 1: Chat View (Default) */}
            {activeTab === "chat" && (
              <div className="flex-1 flex flex-col h-full overflow-hidden bg-[var(--neutral)]">
                {/* Chat message stream with empty state */}
                <div className="flex-1 overflow-hidden">
                  <ChatPanel
                    messages={messages}
                    isLoading={isLoading}
                    progressSteps={progressSteps}
                    language={currentLanguage}
                    onSelectPrompt={handleSelectPrompt}
                    onViewTrace={() => setActiveTab("trace")}
                    className="h-full"
                  />
                </div>

                {/* Quiet single status line directly above the input bar (PRD Part 1 & 1C) */}
                <div className="px-4 py-2 bg-[var(--surface-muted)]/80 border-t border-[var(--border)] flex items-center justify-between text-xs font-mono-data text-[var(--ink-muted)] shrink-0 select-none">
                  {isLoading ? (
                    <div className="flex items-center gap-2 text-[var(--current)] font-medium truncate">
                      <span className="w-2 h-2 rounded-full bg-[var(--current)] animate-ping shrink-0" />
                      <span className="truncate">
                        {progressSteps[progressSteps.length - 1]?.summary || "Analyzing coastal conditions..."}
                      </span>
                    </div>
                  ) : (
                    <div className="flex items-center gap-2 truncate">
                      <span className="font-semibold text-[var(--ink)]">
                        {liveConditions?.locationName || "Thoothukudi Harbour"}
                      </span>
                      <span>·</span>
                      <span>{liveConditions?.waveHeightM.toFixed(1) ?? "0.8"}m wave</span>
                      <span>·</span>
                      <span
                        className={`font-semibold ${
                          currentRiskLabel === "HIGH"
                            ? "text-[#DC2626]"
                            : currentRiskLabel === "MODERATE"
                            ? "text-[#D97706]"
                            : "text-[#1B8755]"
                        }`}
                      >
                        {currentRiskLabel} RISK
                      </span>
                    </div>
                  )}

                  <div className="hidden sm:flex items-center gap-2 text-[11px] text-[var(--ink-subtle)] shrink-0">
                    <span>
                      {liveConditions ? `${liveConditions.lat.toFixed(2)}°N, ${liveConditions.lon.toFixed(2)}°E` : ""}
                    </span>
                  </div>
                </div>

                {/* Bottom Input Area: Dominant 56px Mic Button + 48px Text Input */}
                <div className="p-3 sm:p-4 bg-[var(--surface)] border-t border-[var(--border)] shrink-0 z-10 shadow-xs pb-16 md:pb-4">
                  <ChatInput
                    onSendMessage={handleSendMessage}
                    isLoading={isLoading}
                    language={currentLanguage}
                  />
                </div>
              </div>
            )}

            {/* Destination 2: Marine Map (Full Width) */}
            {activeTab === "map" && (
              <div className="flex-1 h-full overflow-hidden p-2 sm:p-4 pb-16 md:pb-4 bg-[var(--neutral)]">
                <MarineMap
                  geoJson={mapGeoJson}
                  riskLabel={currentRiskLabel}
                  locationName={activeLocationName}
                  className="w-full h-full rounded-2xl border border-[var(--border)] shadow-2xs overflow-hidden"
                />
              </div>
            )}

            {/* Destination 3: Hazard & Alerts View (Full Width) */}
            {activeTab === "alerts" && (
              <div className="flex-1 h-full overflow-y-auto pb-16 md:pb-4 bg-[var(--neutral)]">
                <AlertsView
                  language={currentLanguage}
                  onSelectLanguage={handleSelectLanguage}
                  activeCycloneAlert={activeCycloneAlert}
                />
              </div>
            )}

            {/* Destination 4: Reasoning Trace View (Full Width) */}
            {activeTab === "trace" && (
              <div className="flex-1 h-full overflow-y-auto pb-16 md:pb-4 bg-[var(--neutral)]">
                <TracePanel
                  trace={activeTrace}
                  evidence={activeEvidence}
                  language={currentLanguage}
                />
              </div>
            )}
          </main>
        </div>
      )}
    </div>
  );
}
