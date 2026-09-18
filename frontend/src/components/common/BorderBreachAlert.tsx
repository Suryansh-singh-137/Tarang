"use client";

import React, { useState, useEffect } from "react";
import { GeofenceEvaluationResult, evaluateGeofenceApi } from "@/lib/api";

interface BorderBreachAlertProps {
  evaluation: GeofenceEvaluationResult | null;
  onDismiss?: () => void;
  onReevaluate?: () => void;
  userPhone?: string;
  onPhoneChange?: (phone: string) => void;
}

export const BorderBreachAlert: React.FC<BorderBreachAlertProps> = ({
  evaluation,
  onDismiss,
  onReevaluate,
  userPhone: initialPhone = "+919236454423",
  onPhoneChange,
}) => {
  const [isExpanded, setIsExpanded] = useState(true);
  const [phone, setPhone] = useState(initialPhone || "+919236454423");
  const [isSendingAlert, setIsSendingAlert] = useState(false);
  const [whatsAppResult, setWhatsAppResult] = useState<any>(evaluation?.whatsapp_result || null);
  const [smsResult, setSmsResult] = useState<any>(evaluation?.sms_result || null);
  const [feedbackMsg, setFeedbackMsg] = useState<string | null>(null);

  // Sync phone when initialPhone changes or from localStorage on mount
  useEffect(() => {
    if (initialPhone) {
      setPhone(initialPhone);
    } else if (typeof window !== "undefined") {
      const saved = localStorage.getItem("tarang_user_phone");
      if (saved) {
        setPhone(saved);
      }
    }
  }, [initialPhone]);

  useEffect(() => {
    if (evaluation?.whatsapp_result) {
      setWhatsAppResult(evaluation.whatsapp_result);
    }
    if (evaluation?.sms_result) {
      setSmsResult(evaluation.sms_result);
    }
  }, [evaluation]);

  if (!evaluation || !evaluation.is_breached) {
    return null;
  }

  const handlePhoneSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!phone.trim()) return;

    if (typeof window !== "undefined") {
      localStorage.setItem("tarang_user_phone", phone.trim());
    }
    onPhoneChange?.(phone.trim());

    setIsSendingAlert(true);
    setFeedbackMsg(null);

    try {
      const res = await evaluateGeofenceApi(
        evaluation.coordinates.lat,
        evaluation.coordinates.lon,
        phone.trim(),
        evaluation.boundary_name,
        true,
        true
      );

      const msgs: string[] = [];

      if (res?.whatsapp_result) {
        setWhatsAppResult(res.whatsapp_result);
        if (res.whatsapp_result.success) {
          msgs.push(
            res.whatsapp_result.simulated
              ? "📱 WhatsApp alert simulated"
              : "📱 WhatsApp alert dispatched"
          );
        } else {
          const errDetail = res.whatsapp_result.error ? `: ${res.whatsapp_result.error}` : "";
          msgs.push(`📱 WhatsApp unconfirmed${errDetail}`);
        }
      }

      if (res?.sms_result) {
        setSmsResult(res.sms_result);
        if (res.sms_result.success) {
          msgs.push(
            res.sms_result.simulated
              ? "💬 SMS alert simulated"
              : "💬 SMS alert dispatched"
          );
        } else {
          const errDetail = res.sms_result.error ? `: ${res.sms_result.error}` : "";
          msgs.push(`💬 SMS unconfirmed${errDetail}`);
        }
      }

      setFeedbackMsg(msgs.join(" · ") || "Alerts dispatched.");
    } catch (err: any) {
      setFeedbackMsg("Failed to dispatch alerts: " + (err?.message || "network error"));
    } finally {
      setIsSendingAlert(false);
    }
  };

  return (
    <div
      role="alert"
      aria-live="assertive"
      className="relative z-50 bg-linear-to-r from-red-600 via-rose-600 to-red-700 text-white shadow-xl border-b-2 border-red-900 transition-all duration-300"
    >
      {/* Top Banner Row */}
      <div className="max-w-7xl mx-auto px-4 py-2.5 sm:py-3 flex flex-wrap items-center justify-between gap-3">
        {/* Urgent Icon + Headline */}
        <div className="flex items-center gap-2.5 min-w-0">
          <span className="relative flex h-3.5 w-3.5 shrink-0">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-yellow-300 opacity-75" />
            <span className="relative inline-flex rounded-full h-3.5 w-3.5 bg-yellow-400" />
          </span>

          <span className="font-bold tracking-wide uppercase text-xs sm:text-sm bg-red-950/70 px-2 py-0.5 rounded text-yellow-300 flex items-center gap-1.5 shrink-0">
            <span>🚨</span>
            <span>GEOFENCE BREACH</span>
          </span>

          <div className="truncate text-xs sm:text-sm font-semibold">
            <span>You have crossed into foreign waters: </span>
            <span className="underline decoration-yellow-300 font-bold">
              {evaluation.boundary_name}
            </span>
            <span className="hidden md:inline text-red-100 ml-2">
              (Penetration: {evaluation.distance_km.toFixed(1)} km)
            </span>
          </div>
        </div>

        {/* Action Controls */}
        <div className="flex items-center gap-2 text-xs shrink-0 ml-auto">
          {/* Quick Compass Pill */}
          <div className="hidden sm:flex items-center gap-1.5 bg-red-950/60 px-2.5 py-1 rounded-md border border-red-400/30 text-yellow-200 font-mono">
            <span>🧭 Turn</span>
            <span className="font-bold text-white">
              {evaluation.bearing_cardinal} ({Math.round(evaluation.bearing_to_safety)}°)
            </span>
            <span className="text-[11px] opacity-80">to safety</span>
          </div>

          <a
            href={`tel:${evaluation.coastguard_number}`}
            className="inline-flex items-center gap-1 px-2.5 py-1 rounded bg-yellow-400 text-red-950 font-bold hover:bg-yellow-300 transition-colors shadow-xs"
            title="Call Indian Coast Guard Emergency Hotline"
          >
            <span>📞 Call {evaluation.coastguard_number}</span>
          </a>

          <button
            type="button"
            onClick={() => setIsExpanded(!isExpanded)}
            className="px-2 py-1 bg-red-800/80 hover:bg-red-800 rounded text-red-100 transition-colors cursor-pointer text-xs"
          >
            {isExpanded ? "Collapse ▲" : "Details ▼"}
          </button>

          {onDismiss && (
            <button
              type="button"
              onClick={onDismiss}
              className="p-1 hover:bg-red-800 rounded text-red-200 hover:text-white transition-colors cursor-pointer"
              title="Dismiss warning bar"
            >
              ✕
            </button>
          )}
        </div>
      </div>

      {/* Expandable Emergency Details & Alert Dispatch */}
      {isExpanded && (
        <div className="bg-red-950/90 backdrop-blur-xs border-t border-red-800/60 px-4 py-3 sm:py-4 text-xs sm:text-sm text-red-50">
          <div className="max-w-7xl mx-auto grid grid-cols-1 lg:grid-cols-3 gap-4 items-start">
            {/* Column 1: Immediate Nautical Action Instructions */}
            <div className="space-y-1.5">
              <div className="font-bold text-yellow-300 flex items-center gap-1.5 text-xs uppercase tracking-wider">
                <span>⚠️ Immediate Nautical Instructions</span>
              </div>
              <p className="text-red-100 leading-relaxed text-xs">
                Your GPS position ({evaluation.coordinates.lat.toFixed(3)}°N,{" "}
                {evaluation.coordinates.lon.toFixed(3)}°E) indicates penetration of{" "}
                <strong className="text-white">{evaluation.distance_km.toFixed(1)} km</strong> beyond the{" "}
                {evaluation.boundary_name}. Foreign naval arrest risk is high.
              </p>
              <div className="p-2 bg-red-900/60 rounded border border-red-700/50 flex items-center justify-between text-xs">
                <div>
                  <div className="text-red-300 text-[11px]">Recommended Escape Course:</div>
                  <div className="font-bold text-white text-sm">
                    Steer {evaluation.bearing_cardinal} ({Math.round(evaluation.bearing_to_safety)}°)
                  </div>
                </div>
                <div className="text-right">
                  <div className="text-red-300 text-[11px]">Sector:</div>
                  <div className="font-semibold text-yellow-200">{evaluation.sector}</div>
                </div>
              </div>
            </div>

            {/* Column 2: Distress Communications & Contacts */}
            <div className="space-y-1.5">
              <div className="font-bold text-yellow-300 flex items-center gap-1.5 text-xs uppercase tracking-wider">
                <span>📡 Distress & Radio Channels</span>
              </div>
              <ul className="space-y-1 text-xs text-red-100">
                <li className="flex items-center justify-between p-1.5 rounded bg-red-900/40">
                  <span>Indian Coast Guard (ICG):</span>
                  <a href="tel:1554" className="font-bold text-yellow-300 underline">
                    Toll-Free 1554
                  </a>
                </li>
                <li className="flex items-center justify-between p-1.5 rounded bg-red-900/40">
                  <span>Marine VHF Distress:</span>
                  <span className="font-bold text-white">Channel 16 (156.8 MHz)</span>
                </li>
                <li className="flex items-center justify-between p-1.5 rounded bg-red-900/40">
                  <span>Standard Protocol:</span>
                  <span className="text-yellow-200">Broadcast boat registration & coordinates</span>
                </li>
              </ul>
            </div>

            {/* Column 3: WhatsApp + SMS Emergency Dispatch */}
            <div className="space-y-2 bg-red-900/50 p-3 rounded-lg border border-red-700/40">
              <div className="font-bold text-yellow-300 flex items-center justify-between text-xs uppercase tracking-wider">
                <span>📲 Emergency Alert Dispatch</span>
                <div className="flex items-center gap-1.5">
                  {whatsAppResult && (
                    <span className="text-[10px] lowercase px-1.5 py-0.5 rounded bg-emerald-800/80 text-emerald-200 flex items-center gap-0.5">
                      <span>📱</span>
                      {whatsAppResult.simulated ? "WA Sim" : "WA Sent"}
                    </span>
                  )}
                  {smsResult && (
                    <span className="text-[10px] lowercase px-1.5 py-0.5 rounded bg-blue-800/80 text-blue-200 flex items-center gap-0.5">
                      <span>💬</span>
                      {smsResult.simulated ? "SMS Sim" : "SMS Sent"}
                    </span>
                  )}
                </div>
              </div>

              <p className="text-[11px] text-red-200 leading-snug">
                Deliver this breach warning via both <strong className="text-white">WhatsApp</strong> and{" "}
                <strong className="text-white">SMS</strong> to your phone or onshore fleet manager.
              </p>

              <form onSubmit={handlePhoneSubmit} className="flex gap-2 items-center">
                <input
                  type="tel"
                  placeholder="+91 98765 43210"
                  value={phone}
                  onChange={(e) => setPhone(e.target.value)}
                  className="flex-1 bg-red-950 border border-red-700 rounded px-2 py-1.5 text-xs text-white placeholder-red-400 focus:outline-hidden focus:border-yellow-400"
                />
                <button
                  type="submit"
                  disabled={isSendingAlert || !phone.trim()}
                  className="px-3 py-1.5 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white font-bold text-xs rounded transition-colors cursor-pointer shrink-0"
                >
                  {isSendingAlert ? "Sending..." : "Send Alert"}
                </button>
              </form>

              {feedbackMsg && (
                <div className="text-[11px] text-yellow-200 mt-1">{feedbackMsg}</div>
              )}

              {/* WhatsApp preview */}
              {whatsAppResult?.message_preview && (
                <details className="text-[10px] text-red-300 mt-1 cursor-pointer">
                  <summary className="hover:text-white">📱 View dispatched WhatsApp text preview</summary>
                  <pre className="mt-1 p-2 bg-black/40 rounded whitespace-pre-wrap font-mono text-[10px] text-red-100 max-h-24 overflow-y-auto">
                    {whatsAppResult.message_preview}
                  </pre>
                </details>
              )}

              {/* SMS preview */}
              {smsResult?.message_preview && (
                <details className="text-[10px] text-blue-300 mt-1 cursor-pointer">
                  <summary className="hover:text-white">💬 View dispatched SMS text preview</summary>
                  <pre className="mt-1 p-2 bg-black/40 rounded whitespace-pre-wrap font-mono text-[10px] text-blue-100 max-h-24 overflow-y-auto">
                    {smsResult.message_preview}
                  </pre>
                </details>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
