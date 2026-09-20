"use client";

import React, { useState, useRef, useEffect } from "react";
import {
  Send,
  Bot,
  User,
  Sparkles,
  RotateCcw,
  Loader2,
  HelpCircle,
  TrendingDown,
  Waves,
  Thermometer,
  Fish,
  CheckCircle2,
  FileText,
} from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { chatResearcherEcosystemApi } from "@/lib/api";

interface Props {
  regionId: string;
  regionName: string;
  dominantSpecies?: string[];
  className?: string;
}

interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: string;
}

const QUICK_RESEARCH_PROMPTS = [
  {
    label: "Why has fish productivity declined here?",
    query: "Why has fish productivity declined in this coastal region? Analyze the empirical drivers.",
    icon: "📉",
  },
  {
    label: "Analyze Marine Heatwave impacts",
    query: "What caused the marine heatwave episodes and how did they impact pelagic shoals?",
    icon: "🌡️",
  },
  {
    label: "Explain Chlorophyll-Catch correlation",
    query: "Explain the statistical correlation between Chlorophyll-a and reported fish catch in this region.",
    icon: "🌿",
  },
  {
    label: "CMFRI Policy Recommendations",
    query: "What evidence-based management and policy interventions does CMFRI recommend for this fishery?",
    icon: "📋",
  },
];

export const ResearcherChatbot: React.FC<Props> = ({
  regionId,
  regionName,
  dominantSpecies = [],
  className = "",
}) => {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom of conversation
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  // Clear conversation when region changes
  useEffect(() => {
    setMessages([]);
  }, [regionId]);

  const handleSendMessage = async (textToSend?: string) => {
    const query = (textToSend || input).trim();
    if (!query || isLoading) return;

    const userMsg: ChatMessage = {
      id: "user-" + Date.now(),
      role: "user",
      content: query,
      timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
    };

    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setIsLoading(true);

    const historyPayload = messages.map((m) => ({
      role: m.role,
      content: m.content,
    }));

    try {
      const res = await chatResearcherEcosystemApi(regionId, query, historyPayload);
      const assistantReply =
        res && res.trim()
          ? res
          : "Unable to synthesize bio-oceanographic analysis. Please verify your backend connection.";

      const botMsg: ChatMessage = {
        id: "asst-" + Date.now(),
        role: "assistant",
        content: assistantReply,
        timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
      };

      setMessages((prev) => [...prev, botMsg]);
    } catch (err) {
      console.error("Researcher chat failed:", err);
      const errorMsg: ChatMessage = {
        id: "err-" + Date.now(),
        role: "assistant",
        content: "⚠️ An error occurred while communicating with the Bio-Oceanographic AI. Please try again.",
        timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
      };
      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleClearHistory = () => {
    setMessages([]);
  };

  return (
    <div className={`bg-[var(--surface)] border border-[var(--border)] rounded-2xl shadow-xs overflow-hidden flex flex-col ${className}`}>
      {/* Chatbot Header */}
      <div className="p-4 bg-gradient-to-r from-slate-900 via-slate-800 to-teal-950 text-white flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-teal-500/20 border border-teal-400/30 flex items-center justify-center text-teal-300 shadow-xs">
            <Bot className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h3 className="font-bold text-sm tracking-tight text-white flex items-center gap-1.5">
                Bio-Oceanographic AI Research Fellow
              </h3>
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
            </div>
            <p className="text-[11px] text-teal-200/80">
              Active Regional Scope: <strong className="text-white">{regionName}</strong>
              {dominantSpecies.length > 0 && ` · ${dominantSpecies.slice(0, 2).join(", ")}`}
            </p>
          </div>
        </div>

        {/* Header Action: Reset Chat */}
        {messages.length > 0 && (
          <button
            type="button"
            onClick={handleClearHistory}
            className="flex items-center gap-1 px-2.5 py-1 text-[11px] rounded-lg bg-white/10 hover:bg-white/20 text-slate-200 transition-colors cursor-pointer border border-white/10"
            title="Reset conversation"
          >
            <RotateCcw className="w-3 h-3" />
            <span>Clear</span>
          </button>
        )}
      </div>

      {/* Messages Stream Container */}
      <div className="p-4 sm:p-5 flex-1 min-h-[320px] max-h-[460px] overflow-y-auto space-y-4 bg-[var(--surface)]">
        {messages.length === 0 ? (
          /* Empty State / Welcome Screen with Quick Research Prompts */
          <div className="h-full flex flex-col items-center justify-center text-center py-6 px-4 space-y-4">
            <div className="w-12 h-12 rounded-2xl bg-teal-50 dark:bg-teal-950/50 border border-teal-200 dark:border-teal-800 flex items-center justify-center text-teal-600 dark:text-teal-400 shadow-2xs">
              <Sparkles className="w-6 h-6" />
            </div>
            <div className="max-w-md space-y-1">
              <h4 className="text-sm font-bold text-[var(--ink)]">
                Ask Questions on {regionName} Ecosystem Dynamics
              </h4>
              <p className="text-xs text-[var(--ink-muted)] leading-relaxed">
                Consult with the Bio-Oceanographic AI grounded in INCOIS satellite ocean color,
                OISST thermal anomalies, and ICAR-CMFRI commercial catch datasets.
              </p>
            </div>

            {/* Quick Prompt Chips */}
            <div className="w-full max-w-lg grid grid-cols-1 sm:grid-cols-2 gap-2 pt-2">
              {QUICK_RESEARCH_PROMPTS.map((item, idx) => (
                <button
                  key={idx}
                  type="button"
                  onClick={() => handleSendMessage(item.query)}
                  className="p-3 text-left rounded-xl bg-[var(--surface-muted)] hover:bg-teal-50/60 dark:hover:bg-teal-950/40 border border-[var(--border)] hover:border-teal-300 dark:hover:border-teal-700 transition-all text-xs text-[var(--ink)] cursor-pointer flex items-center gap-2 shadow-2xs group"
                >
                  <span className="text-base shrink-0">{item.icon}</span>
                  <span className="font-medium line-clamp-2 text-[11.5px] group-hover:text-teal-800 dark:group-hover:text-teal-300">
                    {item.label}
                  </span>
                </button>
              ))}
            </div>
          </div>
        ) : (
          /* Active Message History */
          messages.map((msg) => (
            <div
              key={msg.id}
              className={`flex gap-3 ${msg.role === "user" ? "justify-end" : "justify-start"}`}
            >
              {msg.role === "assistant" && (
                <div className="w-7 h-7 rounded-lg bg-teal-700 text-white flex items-center justify-center shrink-0 mt-1 shadow-2xs">
                  <Bot className="w-4 h-4" />
                </div>
              )}

              <div
                className={`rounded-2xl px-4 py-3 max-w-[88%] text-xs sm:text-[13px] leading-relaxed shadow-2xs ${
                  msg.role === "user"
                    ? "bg-[#0C6E8C] text-white rounded-br-xs font-medium"
                    : "bg-[var(--surface-muted)] border border-[var(--border)] text-[var(--ink)] rounded-bl-xs"
                }`}
              >
                {msg.role === "user" ? (
                  <p>{msg.content}</p>
                ) : (
                  <div className="space-y-2 text-slate-800">
                    <ReactMarkdown
                      remarkPlugins={[remarkGfm]}
                      components={{
                        h1: ({ children }) => <h1 className="text-sm font-bold text-slate-900 mt-2 mb-1">{children}</h1>,
                        h2: ({ children }) => <h2 className="text-xs font-bold text-slate-900 uppercase tracking-wide mt-2 mb-1">{children}</h2>,
                        h3: ({ children }) => <h3 className="text-xs font-bold text-slate-900 mt-1.5 mb-1">{children}</h3>,
                        h4: ({ children }) => <h4 className="text-xs font-bold text-slate-900 mt-1 mb-0.5">{children}</h4>,
                        p: ({ children }) => <p className="text-xs leading-relaxed text-slate-800 mb-1.5 last:mb-0">{children}</p>,
                        strong: ({ children }) => <strong className="font-bold text-slate-900">{children}</strong>,
                        ul: ({ children }) => <ul className="list-disc list-inside space-y-1 my-1.5 text-xs text-slate-800">{children}</ul>,
                        ol: ({ children }) => <ol className="list-decimal list-inside space-y-1 my-1.5 text-xs text-slate-800">{children}</ol>,
                        li: ({ children }) => <li className="text-xs text-slate-800 leading-normal">{children}</li>,
                        hr: () => <hr className="border-slate-300 my-2.5" />,
                        blockquote: ({ children }) => (
                          <blockquote className="border-l-3 border-teal-600 pl-3 py-1 text-xs italic text-slate-700 my-2 bg-teal-50 rounded-r-md">
                            {children}
                          </blockquote>
                        ),
                        table: ({ children }) => (
                          <div className="overflow-x-auto my-2 rounded-lg border border-slate-300 bg-white">
                            <table className="w-full text-left text-xs border-collapse">{children}</table>
                          </div>
                        ),
                        thead: ({ children }) => <thead className="bg-slate-100 text-slate-900 border-b border-slate-300">{children}</thead>,
                        tbody: ({ children }) => <tbody className="divide-y divide-slate-200 bg-white">{children}</tbody>,
                        tr: ({ children }) => <tr className="hover:bg-slate-50 transition-colors">{children}</tr>,
                        th: ({ children }) => <th className="px-2.5 py-1.5 text-xs font-bold text-slate-900 border-r border-slate-200 last:border-none">{children}</th>,
                        td: ({ children }) => <td className="px-2.5 py-1.5 text-xs text-slate-800 border-r border-slate-200 last:border-none">{children}</td>,
                        code: ({ children }) => <code className="font-mono text-[11px] bg-slate-200/80 text-slate-900 px-1 py-0.5 rounded">{children}</code>,
                      }}
                    >
                      {msg.content}
                    </ReactMarkdown>
                  </div>
                )}
                <div
                  className={`text-[9px] mt-1.5 flex items-center gap-1 ${
                    msg.role === "user" ? "text-cyan-100 justify-end" : "text-[var(--ink-subtle)]"
                  }`}
                >
                  <span>{msg.timestamp}</span>
                </div>
              </div>

              {msg.role === "user" && (
                <div className="w-7 h-7 rounded-lg bg-[#0C6E8C]/20 border border-[#0C6E8C]/30 text-[#0C6E8C] flex items-center justify-center shrink-0 mt-1">
                  <User className="w-4 h-4" />
                </div>
              )}
            </div>
          ))
        )}

        {/* Loading Spinner Indicator */}
        {isLoading && (
          <div className="flex items-center gap-3">
            <div className="w-7 h-7 rounded-lg bg-teal-700 text-white flex items-center justify-center shrink-0 shadow-2xs">
              <Bot className="w-4 h-4" />
            </div>
            <div className="bg-[var(--surface-muted)] border border-[var(--border)] rounded-2xl rounded-bl-xs px-4 py-3 flex items-center gap-2 text-xs text-[var(--ink-muted)]">
              <Loader2 className="w-3.5 h-3.5 animate-spin text-[#0C6E8C]" />
              <span>Analyzing longitudinal ocean color and CMFRI landing time-series...</span>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input Form Bar */}
      <form
        onSubmit={(e) => {
          e.preventDefault();
          handleSendMessage();
        }}
        className="p-3 border-t border-[var(--border)] bg-[var(--surface)] flex items-center gap-2"
      >
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder={`Ask bio-oceanographer about ${regionName} fisheries decline or anomalies...`}
          disabled={isLoading}
          className="flex-1 bg-[var(--surface-muted)] border border-[var(--border)] rounded-xl px-3.5 py-2.5 text-xs text-[var(--ink)] placeholder:text-[var(--ink-muted)] focus:outline-none focus:ring-2 focus:ring-[#0C6E8C]/30 focus:border-[#0C6E8C] transition-all font-medium disabled:opacity-50"
        />
        <button
          type="submit"
          disabled={!input.trim() || isLoading}
          className="px-4 py-2.5 bg-[#0C6E8C] hover:bg-[#09576F] disabled:opacity-40 text-white rounded-xl text-xs font-semibold flex items-center gap-1.5 transition-all shadow-xs cursor-pointer disabled:cursor-not-allowed"
        >
          <span>Ask</span>
          <Send className="w-3.5 h-3.5" />
        </button>
      </form>
    </div>
  );
};
