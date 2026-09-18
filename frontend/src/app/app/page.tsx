"use client";

import React, { useState, useEffect, useRef, useCallback, Suspense } from "react";
import dynamic from "next/dynamic";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { IconRail, ActiveTab } from "@/components/navigation/IconRail";
import { ChatPanel } from "@/components/chat/ChatPanel";
import { ChatInput } from "@/components/chat/ChatInput";
import { AlertsView } from "@/components/alerts/AlertsView";
import { TracePanel } from "@/components/trace/TracePanel";
import { FishingZonesView } from "@/components/pfz/FishingZonesView";
import { TripPlannerView } from "@/components/trip/TripPlannerView";
import { RoutePanel } from "@/components/route/RoutePanel";
import { LanguageToggle } from "@/components/common/LanguageToggle";
import { WhyThisResultModal } from "@/components/dashboard/WhyThisResultModal";
import { ChangeSinceLastCheck } from "@/components/dashboard/ChangeSinceLastCheck";
import { BorderBreachAlert } from "@/components/common/BorderBreachAlert";

import {
  Message,
  LanguageCode,
  ChatState,
  ProgressEventData,
  MapGeoJSON,
  RiskLabel,
  LiveConditionsSummary,
  LocationStatus,
  MarineSnapshot,
  ChangeSummary,
} from "@/lib/types";
import { streamQuery, evaluateGeofenceApi, GeofenceEvaluationResult } from "@/lib/api";
import { translations } from "@/lib/i18n";
import { useLocation } from "@/lib/locationContext";
import { LocationSelector } from "@/components/location/LocationSelector";

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

function AppWorkspace() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const initialQueryHandled = useRef(false);

  const {
    selectedLocation,
    marineContext,
    updateFromQueryResult,
    syncWithSession,
  } = useLocation();

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
    locationName: selectedLocation?.name || "Coastal Harbour",
    lat: selectedLocation?.lat || 9.9312,
    lon: selectedLocation?.lon || 76.2673,
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

  // PRD §17 & §10: Canonical MarineSnapshot and ChangeSummary state
  const [marineSnapshot, setMarineSnapshot] = useState<MarineSnapshot | null>(null);
  const [changeSummary, setChangeSummary] = useState<ChangeSummary | null>(null);
  const [isWhyModalOpen, setIsWhyModalOpen] = useState(false);

  const [userCoords, setUserCoords] = useState<{ lat: number; lon: number } | null>(null);
  const [locationStatus, setLocationStatus] = useState<LocationStatus>("idle");
  const [isManualLanguageOverride, setIsManualLanguageOverride] = useState(false);

  // International Maritime Geofence evaluation state & emergency WhatsApp
  const [geofenceEvaluation, setGeofenceEvaluation] = useState<GeofenceEvaluationResult | null>(null);
  const [isBreachDismissed, setIsBreachDismissed] = useState(false);
  const [userPhone, setUserPhone] = useState<string>("+919236454423");

  // Sync user's emergency WhatsApp phone number from localStorage
  useEffect(() => {
    if (typeof window !== "undefined") {
      const savedPhone = localStorage.getItem("tarang_user_phone");
      if (savedPhone) {
        setUserPhone(savedPhone);
      } else {
        localStorage.setItem("tarang_user_phone", "+919236454423");
      }
    }
  }, []);

  // Check geofence whenever user coords or selected location changes
  const lastGeofenceKey = useRef<string>("");
  const geofenceTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const runGeofenceCheck = useCallback((lat: number, lon: number, name: string) => {
    const activePhone = userPhone || "+919236454423";
    const key = `${lat.toFixed(4)},${lon.toFixed(4)}`;
    if (key === lastGeofenceKey.current && geofenceEvaluation) return; // Already evaluated these coords
    lastGeofenceKey.current = key;

    console.log("[Geofence] Calling API for:", { lat, lon, name, phone: activePhone });
    evaluateGeofenceApi(lat, lon, activePhone, name, true)
      .then((res) => {
        console.log("[Geofence] API response:", res);
        if (res) {
          setGeofenceEvaluation(res);
          if (res.is_breached) {
            setIsBreachDismissed(false);
            console.log("[Geofence] BREACH DETECTED — banner should appear");
          }
        }
      })
      .catch((err) => {
        console.error("[Geofence] evaluation error:", err);
        lastGeofenceKey.current = ""; // Reset so it retries
      });
  }, [userPhone, geofenceEvaluation]);

  useEffect(() => {
    const targetLat = selectedLocation?.lat ?? userCoords?.lat;
    const targetLon = selectedLocation?.lon ?? userCoords?.lon;
    const targetName = selectedLocation?.name ?? "Vessel Position";

    if (targetLat == null || targetLon == null) return;

    // Small delay to let rapid state changes settle, but don't clear on cleanup
    if (geofenceTimerRef.current) clearTimeout(geofenceTimerRef.current);
    geofenceTimerRef.current = setTimeout(() => {
      runGeofenceCheck(targetLat, targetLon, targetName);
    }, 300);
  }, [selectedLocation?.lat, selectedLocation?.lon, userCoords?.lat, userCoords?.lon, runGeofenceCheck]);

  // Pipeline state for Multi-turn memory
  const [pipelineState, setPipelineState] = useState<ChatState>({
    conversation: [],
    last_parsed_intent: null,
    last_results: {},
  });

  // Server-authoritative conversation session ID
  const [conversationId] = useState<string>(() => "conv-" + Math.random().toString(36).substring(2, 11));

  useEffect(() => {
    if (conversationId) {
      syncWithSession(conversationId);
    }
  }, [conversationId, syncWithSession]);

  useEffect(() => {
    if (selectedLocation) {
      setLiveConditions((prev) => ({
        ...prev,
        lat: selectedLocation.lat,
        lon: selectedLocation.lon,
        locationName: selectedLocation.name,
      }));
      if (marineContext?.is_coastal || marineContext?.type === "coastal" || marineContext?.type === "offshore") {
        setLocationStatus("coastal");
      } else if (marineContext?.type === "inland") {
        setLocationStatus("inland");
      }
    }
  }, [selectedLocation, marineContext]);

  const t = translations[currentLanguage] || translations.en;

  const [geoNotice, setGeoNotice] = useState<string | null>(null);

  // Robust geolocation handler with user-gesture support and permissions API
  const requestBrowserLocation = (isUserGesture = false) => {
    if (typeof navigator === "undefined" || !navigator.geolocation) {
      if (isUserGesture) {
        setGeoNotice("Geolocation is not supported by your browser.");
      }
      return;
    }

    if (navigator.permissions && navigator.permissions.query) {
      navigator.permissions
        .query({ name: "geolocation" as PermissionName })
        .then((perm) => {
          if (perm.state === "denied" && isUserGesture) {
            setGeoNotice(
              "Location permission is blocked in browser settings. Please click the site icon in your address bar to allow location."
            );
          }
          perm.onchange = () => {
            if (perm.state === "granted") {
              setGeoNotice(null);
              requestBrowserLocation(false);
            }
          };
        })
        .catch((err) => {
          console.warn("[APP] navigator.permissions.query error:", err);
        });
    }

    navigator.geolocation.getCurrentPosition(
      (position) => {
        const lat = position.coords.latitude;
        const lon = position.coords.longitude;
        setUserCoords({ lat, lon });
        setGeoNotice(null);
      },
      (err) => {
        if (isUserGesture) {
          if (err.code === 1) {
            setGeoNotice(
              "Location permission was denied. Click the lock/settings icon in the browser address bar to allow location access."
            );
          } else {
            setGeoNotice(`Could not determine position: ${err.message}`);
          }
        }
      },
      { timeout: 10000, maximumAge: 60000, enableHighAccuracy: true }
    );
  };

  // Initial probe on mount
  useEffect(() => {
    requestBrowserLocation(false);
  }, []);

  // Handle Query Submission
  const handleSendMessage = async (queryText: string) => {
    if (!queryText.trim() || isLoading) return;

    setActiveTab("chat");

    const userMsgId = "user-" + Date.now();
    const assistantMsgId = "asst-" + Date.now();
    const requestId = "req-" + Date.now() + "-" + Math.random().toString(36).substring(2, 7);
    const timeStr = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });

    // Add user message
    const userMessage: Message = {
      id: userMsgId,
      request_id: requestId,
      role: "user",
      content: queryText,
      timestamp: timeStr,
    };

    // Add placeholder assistant message
    const assistantMessage: Message = {
      id: assistantMsgId,
      request_id: requestId,
      role: "assistant",
      content: "",
      timestamp: timeStr,
      isStreaming: true,
    };

    setMessages((prev) => [...prev, userMessage, assistantMessage]);
    setIsLoading(true);
    setProgressSteps([]);

    const deviceLocation = userCoords
      ? {
          lat: userCoords.lat,
          lon: userCoords.lon,
          accuracy: null,
          captured_at: new Date().toISOString(),
          permission_status: "granted",
        }
      : null;

    await streamQuery(
      queryText,
      pipelineState,
      {
        onProgress: (progressData) => {
          setProgressSteps((prev) => [...prev, progressData]);
        },
        onResult: (result) => {
          // If server returned canonical selected_location, sync with client LocationContext
          if (result.selected_location) {
            updateFromQueryResult(result.selected_location, result.marine_context);
          }

          // Update assistant message with canonical response data
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === assistantMsgId
                ? {
                    ...msg,
                    request_id: result.request_id,
                    content: result.answer_text,
                    language: result.language,
                    location: result.location,
                    execution_status: result.execution_status,
                    overall_data_status: result.overall_data_status,
                    risk_data: result.risk_data,
                    evidence: result.evidence,
                    trace: result.trace,
                    map_geojson: result.map_geojson,
                    parsed_intent: result.parsed_intent,
                    answer_plan: result.answer_plan,
                    response_mode: result.response_mode,
                    query_signature: result.query_signature,
                    marine_snapshot: result.marine_snapshot,
                    change_summary: result.change_summary,
                    isStreaming: false,
                  }
                : msg
            )
          );

          // Update marine snapshot & change summary (PRD §17, §10)
          if (result.marine_snapshot) {
            setMarineSnapshot(result.marine_snapshot);
            const rLbl = result.marine_snapshot.risk?.final_level || result.marine_snapshot.risk?.risk_label;
            if (rLbl) {
              setCurrentRiskLabel(rLbl);
            }
          }
          if (result.change_summary) {
            setChangeSummary(result.change_summary);
          }

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

          // Determine real location status (coastal, inland, or unresolved)
          const resolvedLoc = result.location?.resolved;
          const locStatus = result.parsed_intent?.location_status;

          const isCoas =
            resolvedLoc?.coastal === true ||
            locStatus === "coastal";

          const isInl =
            locStatus === "inland" ||
            (resolvedLoc && resolvedLoc.coastal === false) ||
            (!isCoas && (
              result.answer_text?.toLowerCase().includes("inland") ||
              result.answer_text?.includes("अंतर्देशीय") ||
              result.answer_text?.includes("உள்நாட்டு")
            ));

          if (isCoas && resolvedLoc) {
            setLocationStatus("coastal");
            const weatherResult = result.agents?.weather || result.last_results?.weather_agent;
            const wData = weatherResult?.data;
            setLiveConditions({
              locationName: resolvedLoc.name || result.parsed_intent?.location_name || "Coastal Waters",
              lat: resolvedLoc.lat,
              lon: resolvedLoc.lon,
              waveHeightM: wData?.wave_height_m ?? 1.0,
              windSpeedKmh: wData?.wind_speed_kmh ?? 15.0,
              seaState: wData?.sea_state || "moderate",
              riskLabel: result.risk_data?.risk_label || "LOW",
              source: weatherResult?.source || "Open-Meteo",
              isFallback: weatherResult?.used_fallback || false,
            });
          } else if (isInl) {
            setLocationStatus("inland");
          } else {
            setLocationStatus("unresolved");
          }

          // Update cyclone alert if hazard agent detected active cyclone
          const hazardResult = result.agents?.hazard || result.last_results?.hazard_agent;
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
                    content: err || "Something went wrong — please try again.",
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
        request_id: requestId,
        conversation_id: conversationId,
        device_location: deviceLocation,
        selected_location: selectedLocation,
        marine_context: marineContext,
        user_lat: userCoords?.lat ?? (selectedLocation ? selectedLocation.lat : null),
        user_lon: userCoords?.lon ?? (selectedLocation ? selectedLocation.lon : null),
        user_location_name: selectedLocation ? selectedLocation.name : null,
        language: currentLanguage,
      }
    );
  };

  // Check for starter query handoff from landing page (?q=...)
  useEffect(() => {
    const q = searchParams.get("q");
    if (q && !initialQueryHandled.current) {
      initialQueryHandled.current = true;
      handleSendMessage(q);
    }
  }, [searchParams]);

  const handleSelectLanguage = (lang: LanguageCode) => {
    setCurrentLanguage(lang);
    setIsManualLanguageOverride(true);
  };

  const handleSelectPrompt = (promptText: string) => {
    handleSendMessage(promptText);
  };

  const handleRecheck = () => {
    handleSendMessage("is it still safe now? check conditions again");
  };

  // Get active query location name for map header
  const activeLocationName =
    messages[messages.length - 1]?.parsed_intent?.location_name ||
    marineSnapshot?.location?.name ||
    liveConditions?.locationName ||
    selectedLocation?.name ||
    "Coastal Waters";

  const activeTrace =
    messages.filter((m) => m.role === "assistant" && m.trace && m.trace.length > 0).slice(-1)[0]?.trace ||
    [];

  const activeEvidence =
    messages.filter((m) => m.role === "assistant" && m.evidence && m.evidence.length > 0).slice(-1)[0]?.evidence ||
    [];

  return (
    <div className="flex flex-col h-screen overflow-hidden bg-[var(--neutral)] text-[var(--ink)]">
      {/* ── Top Navigation Bar: Hairline-thin Nav ── */}
      <header className="h-14 px-4 sm:px-8 bg-[var(--surface)] border-b border-[var(--border)] flex items-center justify-between shrink-0 z-30 shadow-2xs">
        <div className="flex items-center gap-6 sm:gap-8">
          {/* Wordmark: tarang. in Instrument Serif linking back to landing route '/' */}
          <Link
            href="/"
            className="flex items-center gap-3 text-left group cursor-pointer"
            title="Return to Tarang Landing Page"
          >
            <span className="font-serif-display text-xl sm:text-2xl font-normal text-[var(--ink)] tracking-tight">
              tarang.
            </span>
            <span className="hidden md:inline-block text-xs text-[var(--ink-subtle)] font-normal border-l border-[var(--border)] pl-2.5">
              {t.appSubtitle}
            </span>
          </Link>

          {/* Nav Links */}
          <div className="hidden sm:flex items-center gap-6 font-mono-data text-[11px] text-[var(--ink-muted)]">
            <Link
              href="/#how-it-works"
              className="hover:text-[var(--current)] transition-colors tracking-editorial cursor-pointer uppercase"
            >
              PIPELINE
            </Link>
            <Link
              href="/#why-this-matters"
              className="hover:text-[var(--current)] transition-colors tracking-editorial cursor-pointer uppercase"
            >
              DATA & METRICS
            </Link>
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
          {/* Universal Dynamic Location Selector */}
          <LocationSelector />

          {/* Link back to landing */}
          <Link
            href="/"
            className="font-sans text-xs font-medium text-[var(--ink-muted)] hover:text-[var(--current)] px-3 py-1.5 rounded-full hover:bg-[var(--foam)] transition-colors hidden sm:inline-block cursor-pointer"
          >
            Home
          </Link>

          {/* Language Toggle (EN / हिं / த) */}
          <LanguageToggle
            currentLanguage={currentLanguage}
            onSelectLanguage={handleSelectLanguage}
            detectedBadge={detectedLanguage}
          />
        </div>
      </header>

      {/* ── Working Icon-Rail Layout (M9 Part 1) ── */}
      <div className="flex-1 flex overflow-hidden relative">
        {/* ── Icon Rail ── */}
        <IconRail
          activeTab={activeTab}
          onSelectTab={(tab) => setActiveTab(tab)}
          hasMapData={Boolean(mapGeoJson?.features?.length)}
          hasActiveAlert={Boolean(activeCycloneAlert) || Boolean(geofenceEvaluation?.is_breached)}
          hasTraceData={Boolean(activeTrace && activeTrace.length > 0)}
        />

        {/* ── Active View Container ── */}
        <main className="flex-1 flex flex-col h-full overflow-hidden relative">
          {/* High Priority Geofence Breach Emergency Alert Banner */}
          {!isBreachDismissed && geofenceEvaluation?.is_breached && (
            <BorderBreachAlert
              evaluation={geofenceEvaluation}
              onDismiss={() => setIsBreachDismissed(true)}
              userPhone={userPhone}
              onPhoneChange={setUserPhone}
            />
          )}

          {/* Destination 1: Chat View */}
          {activeTab === "chat" && (
            <div className="flex-1 flex flex-col h-full overflow-hidden bg-[var(--neutral)]">
              {/* Change Since Last Check (PRD §8, §10) */}
              {changeSummary?.has_changes && (
                <div className="px-4 pt-3 pb-0 max-w-5xl mx-auto w-full shrink-0">
                  <ChangeSinceLastCheck
                    changeSummary={changeSummary}
                    onDismiss={() => setChangeSummary(null)}
                  />
                </div>
              )}

              {/* Chat message stream */}
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

              {/* Quiet single status line */}
              <div className="px-4 py-2 bg-[var(--surface-muted)]/80 border-t border-[var(--border)] flex items-center justify-between text-xs font-mono-data text-[var(--ink-muted)] shrink-0 select-none">
                {isLoading ? (
                  <div className="flex items-center gap-2 text-[var(--current)] font-medium truncate">
                    <span className="w-2 h-2 rounded-full bg-[var(--current)] animate-ping shrink-0" />
                    <span className="truncate">
                      {progressSteps[progressSteps.length - 1]?.summary || "Analyzing coastal conditions..."}
                    </span>
                  </div>
                ) : messages.length === 0 ? (
                  <div className="flex items-center gap-2 truncate text-[var(--ink-muted)]">
                    <span className="w-2 h-2 rounded-full bg-teal-500 shrink-0" />
                    <span className="font-semibold text-[var(--ink)]">Tarang Marine Network</span>
                    <span>·</span>
                    <span className="text-[var(--ink-subtle)]">Enter a coastal harbour or tap GPS</span>
                  </div>
                ) : locationStatus === "inland" ? (
                  <div className="flex items-center gap-2 truncate text-[var(--ink-muted)]">
                    <span className="w-2 h-2 rounded-full bg-amber-500 shrink-0" />
                    <span className="font-semibold text-[var(--ink)]">Inland Location</span>
                    <span>·</span>
                    <span className="text-[var(--ink-subtle)]">Marine safety metrics not applicable</span>
                  </div>
                ) : locationStatus === "unresolved" ? (
                  <div className="flex items-center gap-2 truncate text-[var(--ink-muted)]">
                    <span className="w-2 h-2 rounded-full bg-slate-400 shrink-0" />
                    <span className="font-semibold text-[var(--ink)]">Location Unresolved</span>
                    <span>·</span>
                    <span className="text-[var(--ink-subtle)]">Specify an Indian coastal harbour or district</span>
                  </div>
                ) : (
                  <div className="flex items-center gap-2 truncate">
                    <span className="font-semibold text-[var(--ink)]">
                      {liveConditions?.locationName || "Coastal Waters"}
                    </span>
                    <span>·</span>
                    <span>
                      {liveConditions?.waveHeightM != null
                        ? `${liveConditions.waveHeightM.toFixed(1)}m wave`
                        : "Wave data n/a"}
                    </span>
                    <span>·</span>
                    <span
                      className={`font-semibold ${
                        currentRiskLabel === "HIGH"
                          ? "text-[#DC2626]"
                          : currentRiskLabel === "MODERATE"
                          ? "text-[#D97706]"
                          : currentRiskLabel === "UNKNOWN"
                          ? "text-amber-600"
                          : "text-[#1B8755]"
                      }`}
                    >
                      {currentRiskLabel} RISK
                    </span>
                  </div>
                )}

                <div className="flex items-center gap-2 text-[11px] text-[var(--ink-subtle)] shrink-0">
                  {userCoords ? (
                    <button
                      type="button"
                      onClick={() => requestBrowserLocation(true)}
                      className="hover:underline flex items-center gap-1 text-[var(--ink-muted)] cursor-pointer"
                      title="GPS coordinates recorded. Click to refresh."
                    >
                      <span>📍 {userCoords.lat.toFixed(2)}°N, {userCoords.lon.toFixed(2)}°E</span>
                    </button>
                  ) : (
                    <button
                      type="button"
                      onClick={() => requestBrowserLocation(true)}
                      className="px-2 py-0.5 rounded bg-[var(--foam)] text-[var(--current)] font-medium hover:bg-[var(--foam)]/80 transition-colors border border-[var(--current)]/20 cursor-pointer"
                      title="Click to allow GPS device location"
                    >
                      <span>📍 Enable GPS</span>
                    </button>
                  )}
                </div>
              </div>

              {/* Inline Geolocation notice banner if blocked in settings */}
              {geoNotice && (
                <div className="px-4 py-2 bg-amber-50 border-t border-amber-200 text-xs text-amber-800 flex items-center justify-between">
                  <span>{geoNotice}</span>
                  <button
                    type="button"
                    onClick={() => setGeoNotice(null)}
                    className="font-bold text-amber-900 hover:underline ml-2"
                  >
                    Dismiss
                  </button>
                </div>
              )}

              {/* Bottom Input Area */}
              <div className="p-3 sm:p-4 bg-[var(--surface)] border-t border-[var(--border)] shrink-0 z-10 shadow-xs pb-16 md:pb-4">
                <ChatInput
                  onSendMessage={handleSendMessage}
                  isLoading={isLoading}
                  language={currentLanguage}
                  onRequestLocation={() => requestBrowserLocation(true)}
                  hasLocation={Boolean(userCoords)}
                />
              </div>
            </div>
          )}

          {/* Destination 2: Marine Map */}
          {activeTab === "map" && (
            <div className="flex-1 h-full overflow-hidden p-2 sm:p-4 pb-16 md:pb-4 bg-[var(--neutral)]">
              <MarineMap
                geoJson={mapGeoJson}
                riskLabel={currentRiskLabel}
                locationName={activeLocationName}
                snapshot={marineSnapshot}
                onWhyThisResult={() => setIsWhyModalOpen(true)}
                className="w-full h-full rounded-2xl border border-[var(--border)] shadow-2xs overflow-hidden"
              />
            </div>
          )}

          {/* Destination 3: Fishing Zones */}
          {activeTab === "pfz" && (
            <div className="flex-1 h-full overflow-y-auto pb-16 md:pb-4 bg-[var(--neutral)]">
              <FishingZonesView
                geoJson={mapGeoJson}
                locationName={activeLocationName}
                locationStatus={locationStatus}
                onNavigateToMap={() => setActiveTab("map")}
                onNavigateToChat={() => setActiveTab("chat")}
                onPfzLoaded={(features) => {
                  setMapGeoJson((prev) => ({
                    type: "FeatureCollection",
                    features: [
                      ...(prev?.features?.filter((f) => f.properties?.feature_type !== "pfz_zone") || []),
                      ...features,
                    ],
                  }));
                }}
                language={currentLanguage}
                marineSnapshot={marineSnapshot}
              />
            </div>
          )}

          {/* Destination 4: Trip Planner */}
          {activeTab === "trip" && (
            <div className="flex-1 h-full overflow-y-auto pb-16 md:pb-4 bg-[var(--neutral)]">
              <TripPlannerView
                liveConditions={liveConditions}
                currentRiskLabel={currentRiskLabel}
                locationStatus={locationStatus}
                onNavigateToChat={() => setActiveTab("chat")}
                language={currentLanguage}
                marineSnapshot={marineSnapshot}
                onRecheck={handleRecheck}
                isRechecking={isLoading}
              />
            </div>
          )}

          {/* Destination: Safe Marine Route Optimizer */}
          {activeTab === "route" && (
            <div className="flex-1 h-full overflow-y-auto pb-16 md:pb-4 bg-[var(--neutral)]">
              <RoutePanel
                onRouteResult={(geojson) => {
                  setMapGeoJson(geojson);
                }}
                onNavigateToMap={() => setActiveTab("map")}
              />
            </div>
          )}

          {/* Destination 5: Hazard & Alerts View */}
          {activeTab === "alerts" && (
            <div className="flex-1 h-full overflow-y-auto pb-16 md:pb-4 bg-[var(--neutral)]">
              <AlertsView
                language={currentLanguage}
                onSelectLanguage={handleSelectLanguage}
                activeCycloneAlert={activeCycloneAlert}
                activeGeofenceBreach={geofenceEvaluation}
              />
            </div>
          )}

          {/* Evidence & Sources */}
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

      {/* Why This Result Explainability Modal (PRD §9) */}
      <WhyThisResultModal
        isOpen={isWhyModalOpen}
        onClose={() => setIsWhyModalOpen(false)}
        snapshot={marineSnapshot}
      />
    </div>
  );
}

export default function AppPage() {
  return (
    <Suspense
      fallback={
        <div className="flex h-screen items-center justify-center bg-[var(--neutral)] text-[var(--ink-muted)] font-mono-data text-xs">
          Loading Tarang Marine Workspace...
        </div>
      }
    >
      <AppWorkspace />
    </Suspense>
  );
}
