import React, { useRef, useEffect } from "react";
import { MessageBubble } from "./MessageBubble";
import { StepIndicator } from "../common/StepIndicator";
import { EmptyStateHorizon } from "../illustrations/EmptyStateHorizon";
import { Message, LanguageCode, ProgressEventData } from "@/lib/types";
import { translations } from "@/lib/i18n";

interface Props {
  messages: Message[];
  isLoading: boolean;
  progressSteps: ProgressEventData[];
  language: LanguageCode;
  onSelectPrompt: (prompt: string) => void;
  onViewTrace?: () => void;
  className?: string;
}

export const ChatPanel: React.FC<Props> = ({
  messages,
  isLoading,
  progressSteps,
  language,
  onSelectPrompt,
  onViewTrace,
  className = "",
}) => {
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const t = translations[language] || translations.en;

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, progressSteps, isLoading]);

  return (
    <div className={`flex flex-col h-full overflow-y-auto px-4 py-4 space-y-4 ${className}`}>
      {messages.length === 0 ? (
        // Empty State: Hero Horizon moment (Part 3)
        <div className="flex-1 flex flex-col items-center justify-center text-center p-6 space-y-6 max-w-lg mx-auto">
          {/* Unboxed linework illustration bleeding directly into background with soft radial wash */}
          <div className="w-64 sm:w-72 relative">
            <div
              className="absolute inset-0 bg-[var(--foam)] rounded-full blur-2xl opacity-40 -z-10 pointer-events-none"
              aria-hidden="true"
            />
            <EmptyStateHorizon />
          </div>

          <div className="space-y-2">
            <h2 className="font-display text-2xl font-bold text-[var(--ink)] tracking-tight">
              {t.appTitle}
            </h2>
            <p className="text-sm text-[var(--ink-muted)] leading-relaxed max-w-md">
              {t.landingHeadline}
            </p>
          </div>

          {/* Quick suggested prompt chips */}
          <div className="w-full space-y-2 pt-2">
            <span className="text-xs font-semibold text-[var(--ink-subtle)] uppercase tracking-wider block">
              {t.suggestedQueries}
            </span>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              {Object.values(t.prompts).map((prompt, idx) => (
                <button
                  key={idx}
                  type="button"
                  onClick={() => onSelectPrompt(prompt)}
                  className="p-3 text-left rounded-xl bg-[var(--surface)] hover:bg-[var(--foam)] border border-[var(--border)] hover:border-[var(--current)] text-xs text-[var(--ink)] transition-all line-clamp-2 shadow-xs"
                >
                  "{prompt}"
                </button>
              ))}
            </div>
          </div>
        </div>
      ) : (
        // Message thread
        <div className="space-y-4">
          {messages.map((msg) => (
            <MessageBubble
              key={msg.id}
              message={msg}
              language={language}
              onViewTrace={onViewTrace}
            />
          ))}

          {/* Live SSE progress step indicator when query is running */}
          {isLoading && (
            <div className="py-2 animate-in fade-in duration-300">
              <StepIndicator
                activeStep={progressSteps[progressSteps.length - 1]?.agent_name}
                completedSteps={progressSteps}
              />
            </div>
          )}
        </div>
      )}

      <div ref={messagesEndRef} />
    </div>
  );
};
