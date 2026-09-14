import React, { useState } from "react";
import ReactMarkdown from "react-markdown";
import {
  Volume2,
  Square,
  Loader2,
  AlertCircle,
  FileCheck,
  Clock,
  ExternalLink,
  MapPin,
  CloudSun,
  Waves,
  Fish,
  AlertTriangle,
  Compass,
  HelpCircle,
  ShieldCheck,
} from "lucide-react";
import { RiskBadge } from "./RiskBadge";
import { Message, LanguageCode } from "@/lib/types";
import { translations } from "@/lib/i18n";
import { synthesizeSpeech } from "@/lib/api";

interface Props {
  message: Message;
  language: LanguageCode;
  onViewTrace?: () => void;
}

export const MessageBubble: React.FC<Props> = ({
  message,
  language,
  onViewTrace,
}) => {
  const [isPlaying, setIsPlaying] = useState(false);
  const [isLoadingAudio, setIsLoadingAudio] = useState(false);
  const [audioElement, setAudioElement] = useState<HTMLAudioElement | null>(null);

  const t = translations[language] || translations.en;
  const isUser = message.role === "user";

  const isSafetyAssessment =
    message.response_mode === "safety_assessment" ||
    message.answer_plan?.presentation_hint === "safety_card" ||
    message.parsed_intent?.intent_name === "MARINE_SAFETY_QUERY" ||
    message.parsed_intent?.intent_name === "TRIP_QUERY" ||
    (!message.answer_plan && message.parsed_intent?.query_type === "safety_check");

  const renderHeaderBadge = () => {
    if (message.isError) return null;

    if (isSafetyAssessment && message.risk_data?.risk_label) {
      return (
        <div className="pb-3 border-b border-[var(--border)] flex flex-wrap items-center justify-between gap-2">
          <RiskBadge
            label={message.risk_data.risk_label}
            score={message.risk_data.composite_score}
            size="lg"
            showScore={message.answer_plan?.show_score ?? false}
          />

          {message.risk_data.evidence_coverage && (
            <span className="text-xs text-[var(--ink-muted)] font-medium bg-[var(--surface-muted)] px-2.5 py-1 rounded-full border border-[var(--border)]">
              Risk inputs evaluated: {message.risk_data.evidence_coverage}
            </span>
          )}
        </div>
      );
    }

    const hint = message.answer_plan?.presentation_hint;
    const mode = message.response_mode || message.answer_plan?.response_mode;
    const intentName = message.parsed_intent?.intent_name || message.answer_plan?.intent_name;

    if (hint === "location_card" || intentName === "LOCATION_QUERY") {
      return (
        <div className="pb-3 border-b border-[var(--border)] flex items-center justify-between">
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200 shadow-2xs">
            <MapPin className="w-3.5 h-3.5 text-emerald-600" />
            Location Context
          </span>
          {message.location?.resolved && (
            <span className="text-[11px] text-[var(--ink-muted)] font-mono">
              {message.location.resolved.lat.toFixed(2)}°N, {message.location.resolved.lon.toFixed(2)}°E
            </span>
          )}
        </div>
      );
    }

    if (hint === "weather_card" || intentName === "WEATHER_QUERY" || intentName === "SEA_LEVEL_PRESSURE_QUERY") {
      return (
        <div className="pb-3 border-b border-[var(--border)] flex items-center justify-between">
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-sky-50 text-sky-700 border border-sky-200 shadow-2xs">
            <CloudSun className="w-3.5 h-3.5 text-sky-600" />
            Current & Forecast Weather
          </span>
          <span className="text-[11px] text-[var(--ink-muted)]">IMD / Open-Meteo</span>
        </div>
      );
    }

    if (hint === "ocean_card" || intentName === "TIDE_QUERY" || intentName === "WATER_LEVEL_QUERY") {
      return (
        <div className="pb-3 border-b border-[var(--border)] flex items-center justify-between">
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-blue-50 text-blue-700 border border-blue-200 shadow-2xs">
            <Waves className="w-3.5 h-3.5 text-blue-600" />
            Tide & Water Level Prediction
          </span>
          <span className="text-[11px] text-[var(--ink-muted)]">SOI Harmonic Datum</span>
        </div>
      );
    }

    if (hint === "pfz_card" || intentName === "PFZ_QUERY") {
      return (
        <div className="pb-3 border-b border-[var(--border)] flex items-center justify-between">
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-teal-50 text-teal-700 border border-teal-200 shadow-2xs">
            <Fish className="w-3.5 h-3.5 text-teal-600" />
            Fishing Potential Indicator
          </span>
          <span className="text-[11px] text-[var(--ink-muted)]">INCOIS Satellite</span>
        </div>
      );
    }

    if (hint === "hazard_card" || intentName === "HAZARD_QUERY" || intentName === "BOUNDARY_QUERY") {
      return (
        <div className="pb-3 border-b border-[var(--border)] flex items-center justify-between">
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-amber-50 text-amber-700 border border-amber-200 shadow-2xs">
            <AlertTriangle className="w-3.5 h-3.5 text-amber-600" />
            Coastal Hazard Advisory
          </span>
          <span className="text-[11px] text-[var(--ink-muted)]">INCOIS Alert</span>
        </div>
      );
    }

    if (mode === "applicability_explanation" || hint === "applicability_card") {
      return (
        <div className="pb-3 border-b border-[var(--border)] flex items-center justify-between">
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-indigo-50 text-indigo-700 border border-indigo-200 shadow-2xs">
            <Compass className="w-3.5 h-3.5 text-indigo-600" />
            Geographic Applicability Notice
          </span>
          <span className="text-[11px] text-indigo-600 font-medium">Inland Coordinate</span>
        </div>
      );
    }

    return null;
  };

  const handleToggleAudio = async () => {
    if (isPlaying && audioElement) {
      audioElement.pause();
      setIsPlaying(false);
      return;
    }

    if (audioElement) {
      audioElement.play();
      setIsPlaying(true);
      return;
    }

    try {
      setIsLoadingAudio(true);
      const audioBlob = await synthesizeSpeech(message.content, message.language || language || "en");
      console.log(`[TTS] Received audio blob (${audioBlob.size} bytes, type: ${audioBlob.type})`);
      
      const audioUrl = URL.createObjectURL(audioBlob);
      const audio = new Audio(audioUrl);

      audio.onended = () => {
        setIsPlaying(false);
        URL.revokeObjectURL(audioUrl);
      };
      audio.onerror = (e) => {
        console.error("Audio playback decoding error:", e);
        setIsPlaying(false);
        URL.revokeObjectURL(audioUrl);
      };

      setAudioElement(audio);
      await audio.play();
      setIsPlaying(true);
    } catch (err: any) {
      console.error("Failed to play TTS audio:", err);
      alert(`Could not play audio: ${err.message || "Please ensure Sarvam TTS API is accessible."}`);
    } finally {
      setIsLoadingAudio(false);
    }

  };

  if (isUser) {
    return (
      <div className="flex justify-end mb-4 animate-in fade-in duration-200">
        <div className="max-w-[85%] sm:max-w-[75%] rounded-2xl px-5 py-3.5 bg-[var(--ink)] text-white border border-[var(--border)] shadow-xs rounded-br-xs">
          <p className="whitespace-pre-wrap text-sm sm:text-base leading-relaxed">{message.content}</p>
          <div className="mt-1.5 flex items-center justify-end text-[10px] text-gray-300 opacity-80">
            {message.timestamp}
          </div>
        </div>
      </div>
    );
  }

  // Assistant message bubble
  return (
    <div className="flex justify-start mb-6 animate-in fade-in duration-200">
      <div className={`w-full max-w-[95%] sm:max-w-[88%] rounded-2xl px-5 py-5 bg-[var(--surface)] border ${message.isError ? "border-amber-200/80 bg-amber-50/20" : "border-[var(--border)]"} shadow-xs text-[var(--ink)] space-y-4`}>
        {/* Intent-aware Header Badge / Risk Badge Verdict */}
        {renderHeaderBadge()}

        {/* Markdown answer content */}
        <div className="prose prose-slate max-w-none text-sm sm:text-base leading-relaxed break-words font-sans selection:bg-[var(--foam)]">
          {message.content ? (
            <ReactMarkdown>{message.content}</ReactMarkdown>
          ) : message.isStreaming ? (
            <div className="flex items-center gap-2 text-[var(--ink-muted)] text-sm py-2">
              <Loader2 className="w-4 h-4 animate-spin text-[var(--current)]" />
              <span>{t.thinking}</span>
            </div>
          ) : (
            <span className="text-[var(--ink-subtle)]">No answer generated.</span>
          )}
        </div>

        {/* Inline Fallback / Proxy Disclosures (Only when critical marine safety sources relied on fallback) */}
        {!message.isError &&
          isSafetyAssessment &&
          message.risk_data?.risk_label !== "UNKNOWN" &&
          message.trace?.some(
            (tr) => (tr.agent_name === "weather_agent" || tr.agent_name === "hazard_agent") && tr.used_fallback
          ) && (
            <div className="p-3 bg-[#FEF3C7] border border-[#FDE68A] rounded-xl text-xs text-[#92400E] flex items-start gap-2.5">
              <AlertCircle className="w-4 h-4 text-[#D97706] shrink-0 mt-0.5" />
              <div className="space-y-0.5">
                <span className="font-semibold">{t.fallbackWarning}</span>
                <p className="text-[11px] text-[#B45309]">
                  Live marine weather or hazard source was temporarily unreachable. Assessment relied on validated fallback records.
                </p>
              </div>
            </div>
          )}

        {/* Footer Actions: Read Aloud TTS & Evidence Count */}
        <div className="pt-3 border-t border-[var(--border)] flex flex-wrap items-center justify-between gap-3 text-xs text-[var(--ink-muted)]">
          {!message.isError ? (
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={handleToggleAudio}
                disabled={isLoadingAudio || !message.content}
                className="inline-flex items-center gap-2 min-h-[44px] px-3.5 py-2 rounded-full bg-[var(--surface-muted)] hover:bg-[var(--foam)] text-[var(--ink)] border border-[var(--border)] hover:border-[var(--current)] transition-all font-medium disabled:opacity-50"
                aria-label={isPlaying ? t.stopAudio : t.readAloud}
              >
                {isLoadingAudio ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin text-[var(--current)]" />
                    <span>{t.synthesizingAudio}</span>
                  </>
                ) : isPlaying ? (
                  <>
                    <Square className="w-4 h-4 text-[#DC2626] fill-current" />
                    <span>{t.stopAudio}</span>
                  </>
                ) : (
                  <>
                    <Volume2 className="w-4 h-4 text-[var(--current)]" />
                    <span>{t.readAloud}</span>
                  </>
                )}
              </button>
            </div>
          ) : (
            <div />
          )}

          <div className="flex items-center gap-2">
            {!message.isError && onViewTrace && message.trace && message.trace.length > 0 && (
              <button
                type="button"
                onClick={onViewTrace}
                className="inline-flex items-center gap-1.5 min-h-[44px] px-3 py-2 rounded-full text-xs text-[var(--ink-muted)] hover:text-[var(--ink)] hover:bg-[var(--surface-muted)] transition-colors"
                title="View reasoning pipeline"
              >
                <FileCheck className="w-3.5 h-3.5 text-[var(--current)]" />
                <span>{message.trace.length} Reasoning Steps</span>
              </button>
            )}

            <span className="text-[11px] text-[var(--ink-subtle)] flex items-center gap-1">
              <Clock className="w-3 h-3" />
              {message.timestamp}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
};
