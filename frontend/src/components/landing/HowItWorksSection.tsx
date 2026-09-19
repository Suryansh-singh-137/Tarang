"use client";

import React, { useEffect, useRef, useState } from "react";
import { LanguageCode } from "@/lib/types";

interface Props {
  language: LanguageCode;
  className?: string;
}

interface StepItem {
  num: string;
  tag: string;
  title: string;
  body: string;
  detail: string;
}

const STEPS: Partial<Record<LanguageCode, StepItem[]>> = {
  en: [
    {
      num: "01",
      tag: "INPUT & HARBOUR",
      title: "Ask in your language, by voice or text",
      body: "Speak naturally in Tamil, Hindi, or English. Tarang automatically resolves Indian coastal fishing harbours, fish landing centres, and coordinates.",
      detail: "Whisper speech-to-text · Multilingual intent resolver",
    },
    {
      num: "02",
      tag: "CROSS-VERIFICATION",
      title: "Specialized agents investigate in parallel",
      body: "Six domain agents simultaneously inspect live wave swell, wind vectors, INCOIS chlorophyll-a zones, GDACS cyclone advisories, and international maritime boundaries.",
      detail: "Open-Meteo · INCOIS Oceansat-2 · GDACS alerts",
    },
    {
      num: "03",
      tag: "SYNTHESIS & SAFETY",
      title: "Get an evidence-backed answer & verdict",
      body: "Review an honest, plain-spoken safety advisory with cited data sources, an interactive marine chart, and an unambiguous risk classification.",
      detail: "Deterministic risk engine · 100% cited provenance",
    },
  ],
  hi: [
    {
      num: "01",
      tag: "प्रश्न व बंदरगाह",
      title: "अपनी भाषा में बोलें या लिखें",
      body: "तमिल, हिंदी या अंग्रेजी में स्वाभाविक रूप से पूछें। तरंग भारतीय तटीय बंदरगाहों और मछली लैंडिंग केंद्रों को तुरंत पहचानता है।",
      detail: "व्हिस्पर वॉइस पहचान · बहुभाषी समझ",
    },
    {
      num: "02",
      tag: "सत्यापन प्रक्रिया",
      title: "विशेषज्ञ एजेंट्स एक साथ जांच करते हैं",
      body: "छह विशेष विश्लेषक लाइव लहरों, हवा, उपग्रह से संभावित मत्स्य क्षेत्रों, चक्रवात चेतावनियों और समुद्री सीमाओं की पड़ताल करते हैं।",
      detail: "ओपन-मेटियो · इनकोइस उपग्रह · जीडीएसीएस चेतावनी",
    },
    {
      num: "03",
      tag: "सुरक्षा निर्णय",
      title: "प्रमाणित उत्तर और स्पष्ट जोखिम स्तर",
      body: "समुद्र में जाने से पहले सटीक सलाह, वैज्ञानिक स्रोतों के संदर्भ, लाइव समुद्री मानचित्र और पारदर्शी सुरक्षा स्कोर प्राप्त करें।",
      detail: "नियम-आधारित सुरक्षा प्रणाली · पूर्ण प्रामाणिकता",
    },
  ],
  ta: [
    {
      num: "01",
      tag: "கேள்வி & துறைமுகம்",
      title: "உங்கள் மொழியில் பேசுங்கள் அல்லது தட்டச்சு செய்யுங்கள்",
      body: "தமிழ், இந்தி அல்லது ஆங்கிலத்தில் இயல்பாகப் பேசுங்கள். தாரங் இந்தியக் கடலோரத் துறைமுகங்களையும் மீன்பிடி மையங்களையும் துல்லியமாக அடையாளம் காண்கிறது.",
      detail: "குரல் வழி உள்ளீடு · பன்மொழி உணர்தல்",
    },
    {
      num: "02",
      tag: "ஆய்வு & சரிபார்ப்பு",
      title: "பிரத்யேக முகவர்கள் தீவிரமாக ஆராய்கின்றனர்",
      body: "ஆறு முகவர்கள் நேரலை அலை உயரம், காற்றின் வேகம், செயற்கைக்கோள் மீன்பிடி பகுதிகள், புயல் எச்சரிக்கைகள் மற்றும் எல்லைகளை ஒரே நேரத்தில் சரிபார்க்கின்றனர்.",
      detail: "ஓபன்-மீடியோ · இன்கோயிஸ் தரவு · ஜிடிஏசிஎஸ் எச்சரிக்கை",
    },
    {
      num: "03",
      tag: "பாதுகாப்பு முடிவு",
      title: "ஆதாரங்களுடன் கூடிய தெளிவான பாதுகாப்பு பதில்",
      body: "கடலுக்குச் செல்லும் முன் முழுமையான பாதுகாப்பு வழிகாட்டல், வரைபடக் குறிப்புகள் மற்றும் உத்தியோகபூர்வ தரவு ஆதாரங்களுடன் வெளிப்படையான பதில் கிடைக்கும்.",
      detail: "வெளிப்படையான இடர் மதிப்பீடு · நம்பகமான சான்றுகள்",
    },
  ],
};

export const HowItWorksSection: React.FC<Props> = ({
  language,
  className = "",
}) => {
  const sectionRef = useRef<HTMLElement>(null);
  const [isVisible, setIsVisible] = useState(false);

  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            setIsVisible(true);
            observer.disconnect();
          }
        });
      },
      { threshold: 0.15 }
    );

    if (sectionRef.current) {
      observer.observe(sectionRef.current);
    }

    return () => observer.disconnect();
  }, []);

  const steps = STEPS[language] || STEPS.en!;

  return (
    <section
      ref={sectionRef}
      id="how-it-works"
      className={`py-16 sm:py-20 lg:py-24 border-t border-[var(--border)] relative bg-[var(--neutral)] ${className}`}
    >
      <div className="max-w-[1200px] mx-auto w-full px-6 sm:px-10 lg:px-16">
        {/* Section mono eyebrow */}
        <div
          className={`font-mono-data text-[11px] text-[var(--ink-muted)] tracking-widest uppercase mb-4 transition-all duration-500 ${
            isVisible ? "reveal-visible" : "reveal-init"
          }`}
        >
          THE DECISION PIPELINE
        </div>

        {/* Editorial headline */}
        <div
          className={`max-w-[680px] mb-12 sm:mb-16 transition-all duration-500 delay-100 ${
            isVisible ? "reveal-visible" : "reveal-init"
          }`}
        >
          <h2 className="font-serif-display text-2xl sm:text-3xl lg:text-4xl font-normal text-[var(--ink)] tracking-tight leading-snug">
            From spoken question to verified sea verdict in seconds.
          </h2>
          <p className="font-sans text-sm sm:text-base text-[var(--ink-muted)] mt-3 leading-relaxed">
            No single model makes an unverified safety call. Every response follows a strict three-phase investigation pipeline.
          </p>
        </div>

        {/* 3 Sequential Step Columns */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-0 border-t border-b border-[var(--border)] divide-y md:divide-y-0 md:divide-x divide-[var(--border)]">
          {steps.map((step, index) => {
            const staggerDelay = `${(index + 1) * 90}ms`;
            return (
              <div
                key={step.num}
                style={{
                  transitionDelay: isVisible ? staggerDelay : "0ms",
                }}
                className={`p-6 sm:p-8 lg:p-10 flex flex-col justify-between transition-all duration-500 group ${
                  isVisible ? "reveal-visible" : "reveal-init"
                }`}
              >
                <div>
                  {/* Top numeral and tag row */}
                  <div className="flex items-center justify-between mb-6">
                    <span className="font-mono-data text-xs font-semibold text-[var(--current)] tracking-wider">
                      {step.num}
                    </span>
                    <span className="font-mono-data text-[10px] text-[var(--ink-subtle)] uppercase tracking-widest">
                      {step.tag}
                    </span>
                  </div>

                  {/* Step title */}
                  <h3 className="font-serif-display text-xl sm:text-2xl text-[var(--ink)] font-normal mb-3 leading-snug">
                    {step.title}
                  </h3>

                  {/* Step narrative description */}
                  <p className="font-sans text-sm text-[var(--ink-muted)] leading-relaxed mb-6">
                    {step.body}
                  </p>
                </div>

                {/* Sub-label / architecture tag */}
                <div className="pt-4 border-t border-[var(--border)] flex items-center gap-2 font-mono-data text-[11px] text-[var(--ink-subtle)]">
                  <span className="w-1.5 h-1.5 rounded-full bg-[var(--current)] opacity-60" />
                  <span className="truncate">{step.detail}</span>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
};
