import React, { useState, useRef } from "react";
import { Mic, Send, Square, Loader2, AlertCircle } from "lucide-react";
import { LanguageCode } from "@/lib/types";
import { translations } from "@/lib/i18n";
import { transcribeAudio } from "@/lib/api";

interface Props {
  onSendMessage: (text: string) => void;
  isLoading: boolean;
  language: LanguageCode;
  className?: string;
  initialValue?: string;
}

export const ChatInput: React.FC<Props> = ({
  onSendMessage,
  isLoading,
  language,
  className = "",
  initialValue = "",
}) => {
  const [inputText, setInputText] = useState(initialValue);
  const [isRecording, setIsRecording] = useState(false);
  const [isTranscribing, setIsTranscribing] = useState(false);
  const [micError, setMicError] = useState<string | null>(null);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const t = translations[language] || translations.en;

  // Toggle voice recording
  const handleToggleVoice = async () => {
    setMicError(null);

    if (isRecording) {
      // Stop recording
      if (mediaRecorderRef.current && mediaRecorderRef.current.state !== "inactive") {
        mediaRecorderRef.current.stop();
      }
      setIsRecording(false);
      return;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });

      // Detect supported mimeType across Chrome, Firefox, Safari, and Edge
      let mimeType = "";
      if (typeof MediaRecorder !== "undefined") {
        if (MediaRecorder.isTypeSupported("audio/webm;codecs=opus")) {
          mimeType = "audio/webm;codecs=opus";
        } else if (MediaRecorder.isTypeSupported("audio/webm")) {
          mimeType = "audio/webm";
        } else if (MediaRecorder.isTypeSupported("audio/mp4")) {
          mimeType = "audio/mp4";
        }
      }

      const recorder = mimeType ? new MediaRecorder(stream, { mimeType }) : new MediaRecorder(stream);
      mediaRecorderRef.current = recorder;
      audioChunksRef.current = [];

      recorder.ondataavailable = (e) => {
        if (e.data && e.data.size > 0) {
          audioChunksRef.current.push(e.data);
        }
      };

      recorder.onstop = async () => {
        stream.getTracks().forEach((track) => track.stop());
        const finalType = recorder.mimeType || mimeType || "audio/webm";
        const audioBlob = new Blob(audioChunksRef.current, { type: finalType });

        if (audioBlob.size < 100) {
          setMicError("No voice captured. Please speak clearly into your microphone and try again.");
          return;
        }

        await processAudioTranscription(audioBlob);
      };

      recorder.start();
      setIsRecording(true);
    } catch (err: any) {
      console.error("Microphone access error:", err);
      if (err.name === "NotAllowedError" || err.name === "PermissionDeniedError") {
        setMicError("Microphone access was denied. Please grant microphone permission in your browser or type below.");
      } else {
        setMicError(`Microphone error (${err.name || "AccessError"}): ${err.message || "Could not open audio device"}`);
      }
      setIsRecording(false);
    }
  };

  const processAudioTranscription = async (blob: Blob) => {
    setIsTranscribing(true);
    try {
      const { transcript } = await transcribeAudio(blob);
      if (transcript && transcript.trim()) {
        setInputText(transcript.trim());
        // Auto-send or populate input for fisherman confirmation
        onSendMessage(transcript.trim());
        setInputText("");
      } else {
        setMicError("Could not hear clearly. Please try speaking again or type your query.");
      }
    } catch (err: any) {
      console.error("Transcription error:", err);
      setMicError(err.message || "Speech recognition failed. Please type your query instead.");
    } finally {
      setIsTranscribing(false);
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputText.trim() || isLoading || isTranscribing) return;
    onSendMessage(inputText.trim());
    setInputText("");
    setMicError(null);
  };

  return (
    <div className={`flex flex-col gap-2 ${className}`}>
      {/* Error / Fallback alert banner */}
      {micError && (
        <div className="p-2.5 bg-[#FEF3C7] border border-[#FDE68A] text-[#92400E] rounded-xl text-xs flex items-center justify-between animate-in fade-in duration-200">
          <div className="flex items-center gap-2">
            <AlertCircle className="w-4 h-4 text-[#D97706] shrink-0" />
            <span>{micError}</span>
          </div>
          <button
            type="button"
            onClick={() => setMicError(null)}
            className="text-xs font-bold text-[#92400E] hover:underline px-1"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Primary Voice & Input Control Row */}
      <form onSubmit={handleSubmit} className="flex items-center gap-2.5">
        {/* Dominant Primary 56px+ Voice Push-To-Talk Button (Part 1B #1) */}
        <button
          type="button"
          onClick={handleToggleVoice}
          disabled={isLoading || isTranscribing}
          className={`relative shrink-0 w-14 h-14 min-w-[56px] min-h-[56px] rounded-full flex items-center justify-center transition-all shadow-md focus:outline-hidden focus:ring-3 ${
            isRecording
              ? "bg-[var(--dawn)] text-white ring-4 ring-[var(--dawn)]/30 animate-mic-pulse"
              : isTranscribing
              ? "bg-[var(--surface-muted)] text-[var(--ink-muted)] border border-[var(--border)]"
              : "bg-[var(--current)] hover:bg-[var(--current-hover)] text-white hover:scale-105 active:scale-95"
          }`}
          title={isRecording ? t.stopAudio : isTranscribing ? t.transcribing : t.tapToSpeak}
          aria-label={isRecording ? t.stopAudio : t.tapToSpeak}
        >
          {isTranscribing ? (
            <Loader2 className="w-6 h-6 animate-spin text-[var(--current)]" />
          ) : isRecording ? (
            <Square className="w-6 h-6 fill-current text-white animate-pulse" />
          ) : (
            <Mic className="w-6 h-6 text-white" />
          )}

          {/* Sonar indicator badge */}
          {isRecording && (
            <span className="absolute -top-1 -right-1 flex h-3.5 w-3.5">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-3.5 w-3.5 bg-red-500"></span>
            </span>
          )}
        </button>

        {/* Text Input Container (Generous 48px height for outdoor touch target) */}
        <div className="relative flex-1 flex items-center">
          <input
            type="text"
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            disabled={isLoading || isTranscribing}
            placeholder={
              isRecording
                ? t.listening
                : isTranscribing
                ? t.transcribing
                : t.inputPlaceholder
            }
            className="w-full h-12 min-h-[48px] px-4 pr-12 bg-[var(--surface)] text-[var(--ink)] placeholder-[var(--ink-subtle)] rounded-full border border-[var(--border)] focus:border-[var(--current)] focus:ring-2 focus:ring-[var(--current)]/20 shadow-xs transition-all text-sm sm:text-base disabled:opacity-60"
            aria-label="Query input"
          />

          {/* Send Button inside Input (48px tap target) */}
          <button
            type="submit"
            disabled={!inputText.trim() || isLoading || isTranscribing}
            className="absolute right-1.5 w-10 h-10 min-w-[40px] min-h-[40px] rounded-full flex items-center justify-center bg-[var(--current)] hover:bg-[var(--current-hover)] text-white disabled:opacity-30 disabled:hover:bg-[var(--current)] transition-all shadow-xs"
            title="Send query"
            aria-label="Send query"
          >
            {isLoading ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Send className="w-4 h-4" />
            )}
          </button>
        </div>
      </form>
    </div>
  );
};
