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
      <div className="w-full max-w-[95%] sm:max-w-[88%] rounded-2xl px-5 py-5 bg-[var(--surface)] border border-[var(--border)] shadow-xs text-[var(--ink)] space-y-4">
        {/* Risk Badge Verdict prominently at top of answer */}
        {message.risk_data && message.risk_data.risk_label && (
          <div className="pb-3 border-b border-[var(--border)] flex flex-wrap items-center justify-between gap-2">
            <RiskBadge
              label={message.risk_data.risk_label}
              score={message.risk_data.composite_score}
              size="lg"
            />

            {message.risk_data.evidence_coverage && (
              <span className="text-xs text-[var(--ink-muted)] font-medium bg-[var(--surface-muted)] px-2.5 py-1 rounded-full border border-[var(--border)]">
                Signals: {message.risk_data.evidence_coverage}
              </span>
            )}
          </div>
        )}

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

        {/* Inline Fallback / Proxy Disclosures (Part 2) */}
        {message.trace?.some((tr) => tr.used_fallback) && (
          <div className="p-3 bg-[#FEF3C7] border border-[#FDE68A] rounded-xl text-xs text-[#92400E] flex items-start gap-2.5">
            <AlertCircle className="w-4 h-4 text-[#D97706] shrink-0 mt-0.5" />
            <div className="space-y-0.5">
              <span className="font-semibold">{t.fallbackWarning}</span>
              <p className="text-[11px] text-[#B45309]">
                Live satellite or marine data source was temporarily unreachable. Assessment relied on validated fallback records.
              </p>
            </div>
          </div>
        )}

        {/* Footer Actions: Read Aloud TTS & Evidence Count */}
        <div className="pt-3 border-t border-[var(--border)] flex flex-wrap items-center justify-between gap-3 text-xs text-[var(--ink-muted)]">
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

          <div className="flex items-center gap-2">
            {onViewTrace && message.trace && message.trace.length > 0 && (
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
