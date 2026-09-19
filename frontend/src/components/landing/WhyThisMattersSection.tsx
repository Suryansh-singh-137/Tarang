"use client";

import React, { useEffect, useRef, useState } from "react";
import { LanguageCode } from "@/lib/types";

interface Props {
  language: LanguageCode;
  className?: string;
}

interface StatDef {
  target: number;
  suffix?: string;
  prefix?: string;
  decimals?: number;
  label: string;
  title: string;
  description: string;
  source: string;
}

const STATS_DATA: Partial<Record<LanguageCode, StatDef[]>> = {
  en: [
    {
      target: 7516,
      suffix: " km",
      label: "COASTLINE MONITORED",
      title: "Active Coastal Perimeter",
      description: "Kilometres of Indian mainland and island coastline continuously analyzed across 9 maritime states and 4 union territories.",
      source: "Ministry of Ports, Shipping & Waterways",
    },
    {
      target: 1265,
      suffix: "+",
      label: "LANDING CENTRES",
      title: "Harbours & Fish Landing Sites",
      description: "Traditional fish landing centres and major fishing harbours mapped with real-time marine condition models.",
      source: "CMFRI Marine Fisheries Census",
    },
    {
      target: 6,
      label: "SPECIALIST AGENTS",
      title: "Domain Intelligence Units",
      description: "Dedicated analytical agents cross-verifying weather, swell, chlorophyll-a PFZ, cyclone alerts, and IMBL boundaries.",
      source: "Tarang Multi-Agent Ocean Architecture",
    },
    {
      target: 0,
      label: "FABRICATED CLAIMS",
      title: "Zero Hallucination Tolerance",
      description: "Responses are 100% deterministic and evidence-grounded. No large language model is permitted in the safety-critical path.",
      source: "Tarang Evidence Grounding Architecture",
    },
  ],
  hi: [
    {
      target: 7516,
      suffix: " किमी",
      label: "तटीय निगरानी",
      title: "सक्रिय समुद्री परिधि",
      description: "9 तटीय राज्यों और 4 केंद्र शासित प्रदेशों में भारत की मुख्य भूमि व द्वीपों की निरंतर विश्लेषण की जाने वाली तटरेखा।",
      source: "पत्तन, पोत परिवहन और जलमार्ग मंत्रालय",
    },
    {
      target: 1265,
      suffix: "+",
      label: "मत्स्य लैंडिंग केंद्र",
      title: "बंदरगाह और मत्स्य केंद्र",
      description: "पारंपरिक मछली लैंडिंग केंद्र और प्रमुख बंदरगाह जहां वास्तविक समय की समुद्री परिस्थितियों का आकलन किया जाता है।",
      source: "सीएमएफआरआई मत्स्य पालन जनगणना",
    },
    {
      target: 6,
      label: "विशेषज्ञ एजेंट्स",
      title: "डोमेन विश्लेषण इकाइयां",
      description: "छह स्वतंत्र एजेंट्स जो मौसम, लहरों, क्लोरोफिल क्षेत्र, चक्रवात और अंतर्राष्ट्रीय समुद्री सीमाओं की पुष्टि करते हैं।",
      source: "तरंग मल्टी-एजेंट प्रणाली",
    },
    {
      target: 0,
      label: "काल्पनिक दावे",
      title: "शून्य अनिश्चितता गारंटी",
      description: "हर उत्तर पूरी तरह वैज्ञानिक आंकड़ों पर आधारित है। सुरक्षा-संवेदनशील निर्णयों में किसी भी भाषा मॉडल को अनुमान लगाने की अनुमति नहीं है।",
      source: "तरंग प्रमाण सत्यापन मानक",
    },
  ],
  ta: [
    {
      target: 7516,
      suffix: " கி.மீ",
      label: "கடற்கரை கண்காணிப்பு",
      title: "செயலில் உள்ள கடல் சுற்றளவு",
      description: "9 கடலோர மாநிலங்கள் மற்றும் 4 யூனியன் பிரதேசங்களை உள்ளடக்கிய இந்தியக் கடற்கரையின் தொடர்ச்சியான பாதுகாப்பு பகுப்பாய்வு.",
      source: "துறைமுகங்கள் மற்றும் கப்பல் போக்குவரத்து அமைச்சகம்",
    },
    {
      target: 1265,
      suffix: "+",
      label: "மீன்பிடி மையங்கள்",
      title: "துறைமுகங்கள் & தளங்கள்",
      description: "பாரம்பரிய மீன் இறங்கு தளங்கள் மற்றும் முக்கிய மீன்பிடித் துறைமுகங்களின் நேரலை கடல்சார் நிலைமைகள்.",
      source: "சி.எம்.எஃப்.ஆர்.ஐ கடல் மீன்வளக் கணக்கெடுப்பு",
    },
    {
      target: 6,
      label: "பிரத்யேக முகவர்கள்",
      title: "ஆய்வு புலனாய்வுப் பிரிவுகள்",
      description: "வானிலை, அலைகள், மீன்பிடி பகுதிகள், புயல் எச்சரிக்கைகள் மற்றும் கடல் எல்லைகளைத் தனித்தனியாக உறுதிப்படுத்தும் 6 முகவர்கள்.",
      source: "தாரங் பல்துறை முகவர் கட்டமைப்பு",
    },
    {
      target: 0,
      label: "புனையப்பட்ட தகவல்கள்",
      title: "முழுமையான நம்பகத்தன்மை",
      description: "அனைத்து பதில்களும் 100% அறிவியல் தரவுகளுடன் உறுதி செய்யப்படுகின்றன. பாதுகாப்பு முடிவுகளில் எந்த அனுமானமும் அனுமதிக்கப்படாது.",
      source: "தாரங் ஆதாரச் சரிபார்ப்பு உத்தரவாதம்",
    },
  ],
};

// Custom animated counter component
const StatCounter: React.FC<{
  target: number;
  suffix?: string;
  prefix?: string;
  decimals?: number;
  trigger: boolean;
}> = ({ target, suffix = "", prefix = "", decimals = 0, trigger }) => {
  const [count, setCount] = useState(0);

  useEffect(() => {
    if (!trigger) return;

    // Check prefers-reduced-motion
    if (typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      setCount(target);
      return;
    }

    let startTime: number | null = null;
    const duration = 1000; // ms

    const step = (timestamp: number) => {
      if (!startTime) startTime = timestamp;
      const elapsed = timestamp - startTime;
      const progress = Math.min(elapsed / duration, 1);

      // Ease-out cubic
      const easeOut = 1 - Math.pow(1 - progress, 3);
      const currentVal = progress === 1 ? target : easeOut * target;

      setCount(currentVal);

      if (progress < 1) {
        requestAnimationFrame(step);
      }
    };

    const animId = requestAnimationFrame(step);
    return () => cancelAnimationFrame(animId);
  }, [trigger, target]);

  const formatted =
    decimals > 0
      ? count.toFixed(decimals)
      : Math.round(count).toLocaleString("en-IN");

  return (
    <span>
      {prefix}
      {formatted}
      {suffix}
    </span>
  );
};

export const WhyThisMattersSection: React.FC<Props> = ({
  language,
  className = "",
}) => {
  const sectionRef = useRef<HTMLElement>(null);
  const [hasEntered, setHasEntered] = useState(false);

  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            setHasEntered(true);
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

  const stats = STATS_DATA[language] || STATS_DATA.en!;

  return (
    <section
      ref={sectionRef}
      id="why-this-matters"
      className={`py-16 sm:py-20 lg:py-24 border-t border-[var(--border)] relative bg-[var(--surface-muted)]/50 ${className}`}
    >
      <div className="max-w-[1200px] mx-auto w-full px-6 sm:px-10 lg:px-16">
        {/* Eyebrow */}
        <div
          className={`font-mono-data text-[11px] text-[var(--ink-muted)] tracking-widest uppercase mb-4 transition-all duration-500 ${
            hasEntered ? "reveal-visible" : "reveal-init"
          }`}
        >
          WHY THIS MATTERS
        </div>

        {/* Section Headline */}
        <div
          className={`max-w-[720px] mb-12 sm:mb-16 transition-all duration-500 delay-100 ${
            hasEntered ? "reveal-visible" : "reveal-init"
          }`}
        >
          <h2 className="font-serif-display text-2xl sm:text-3xl lg:text-4xl font-normal text-[var(--ink)] tracking-tight leading-snug">
            Real scale, honest boundaries, zero fabricated claims.
          </h2>
          <p className="font-sans text-sm sm:text-base text-[var(--ink-muted)] mt-3 leading-relaxed">
            Every statistic and safety decision is backed by live satellite feeds, government marine census records, and deterministic safety rules.
          </p>
        </div>

        {/* 4 Stat Columns Grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-8 lg:gap-10 border-t border-[var(--border)] pt-10">
          {stats.map((stat, idx) => {
            const staggerDelay = `${(idx + 1) * 80}ms`;
            return (
              <div
                key={stat.label}
                style={{ transitionDelay: hasEntered ? staggerDelay : "0ms" }}
                className={`flex flex-col justify-between transition-all duration-500 ${
                  hasEntered ? "reveal-visible" : "reveal-init"
                }`}
              >
                <div>
                  {/* Large Numeral with Count-up */}
                  <div className="font-serif-display text-4xl sm:text-5xl lg:text-[3.25rem] text-[var(--ink)] font-normal tracking-tight leading-none mb-3">
                    <StatCounter
                      target={stat.target}
                      suffix={stat.suffix}
                      prefix={stat.prefix}
                      decimals={stat.decimals}
                      trigger={hasEntered}
                    />
                  </div>

                  {/* Micro-label */}
                  <div className="font-mono-data text-[11px] font-medium text-[var(--current)] uppercase tracking-wider mb-2">
                    {stat.label}
                  </div>

                  {/* Stat Title */}
                  <h3 className="font-serif-display text-lg text-[var(--ink)] font-normal mb-2 leading-snug">
                    {stat.title}
                  </h3>

                  {/* Honest narrative description */}
                  <p className="font-sans text-xs sm:text-sm text-[var(--ink-muted)] leading-relaxed mb-6">
                    {stat.description}
                  </p>
                </div>

                {/* Sourced small mono caption */}
                <div className="pt-3 border-t border-[var(--border)]/80 font-mono-data text-[10px] text-[var(--ink-subtle)] flex items-center gap-1.5">
                  <span className="w-1 h-1 rounded-full bg-[var(--ink-subtle)]" />
                  <span className="truncate">Source: {stat.source}</span>
                </div>
              </div>
            );
          })}
        </div>

        {/* Global verified sources citation footer banner */}
        <div
          className={`mt-14 pt-6 border-t border-[var(--border)] flex flex-col sm:flex-row sm:items-center justify-between gap-4 font-mono-data text-[11px] text-[var(--ink-subtle)] transition-all duration-500 delay-300 ${
            hasEntered ? "reveal-visible" : "reveal-init"
          }`}
        >
          <div className="flex items-center gap-2">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 shrink-0" />
            <span>All metrics verifiable against official national gazettes and Open Science repositories.</span>
          </div>
          <div className="text-[10px] tracking-wider uppercase text-[var(--ink-muted)]">
            EST. 2024 / PROVENANCE VERIFIED
          </div>
        </div>
      </div>
    </section>
  );
};
