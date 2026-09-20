"use client";

import React, { useEffect, useRef, useState } from "react";
import { LanguageCode } from "@/lib/types";
import { translations } from "@/lib/i18n";

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

const STEPS: Record<LanguageCode, StepItem[]> = {
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
  gu: [
    {
      num: "01",
      tag: "પ્રશ્ન અને બંદર",
      title: "તમારી ભાષામાં બોલીને અથવા લખીને પૂછો",
      body: "ગુજરાતી, હિન્દી કે અંગ્રેજીમાં સહજતાથી પૂછો. તરંગ ભારતીય દરિયાઈ બંદરો અને મત્સ્ય ઉતરાણ કેન્દ્રોને આપમેળે ઓળખે છે.",
      detail: "વ્હીસ્પર અવાજ ઓળખ · બહુભાષી વિશ્લેષણ",
    },
    {
      num: "02",
      tag: "ચકાસણી પ્રક્રિયા",
      title: "વિશેષજ્ઞ એજન્ટો એકસાથે તપાસ કરે છે",
      body: "છ સ્વતંત્ર એજન્ટો લાઈવ મોજાં, પવન, સેટેલાઇટ મત્સ્ય વિસ્તારો અને વાવાઝોડાની ચેતવણીઓની ચકાસણી કરે છે.",
      detail: "ઓપન-મેટિઓ · INCOIS ઉપગ્રહ · GDACS ચેતવણીઓ",
    },
    {
      num: "03",
      tag: "સુરક્ષા નિર્ણય",
      title: "પુરાવા આધારિત જવાબ અને સ્પષ્ટ માર્ગદર્શન",
      body: "દરિયામાં જતાં પહેલાં સત્તાવાર સરકારી સ્ત્રોતોના સંદર્ભ, લાઈવ દરિયાઈ નકશો અને વિશ્વસનીય જોખમ સ્કોર મેળવો.",
      detail: "નિયમ આધારિત રિસ્ક એન્જિન · ૧૦૦% પ્રમાણિત પુરાવા",
    },
  ],
  bn: [
    {
      num: "01",
      tag: "প্রশ্ন ও বন্দর",
      title: "আপনার ভাষায় বলুন বা লিখে জিজ্ঞাসা করুন",
      body: "বাংলা, হিন্দি বা ইংরেজিতে স্বাভাবিকভাবে বলুন। তরঙ্গ দ্রুত ভারতীয় উপকূলবর্তী বন্দর ও মাছ ধরার কেন্দ্র শনাক্ত করে।",
      detail: "হুইস্পার ভয়েস শনাক্তকরণ · বহুভাষিক সমাধান",
    },
    {
      num: "02",
      tag: "যাচাইকরণ প্রক্রিয়া",
      title: "বিশেষজ্ঞ এজেন্টরা একসাথে পরীক্ষা করে",
      body: "ছয়জন বিশেষজ্ঞ এজেন্ট রিয়েল-টাইম ঢেউ, বাতাস, স্যাটেলাইট মাছের সম্ভাব্য অঞ্চল ও ঘূর্ণিঝড়ের সতর্কতা খতিয়ে দেখে।",
      detail: "ওপেন-মেটিও · INCOIS স্যাটেলাইট · GDACS সতর্কতা",
    },
    {
      num: "03",
      tag: "সুরক্ষা রায়",
      title: "প্রমাণভিত্তিক উত্তর ও স্পষ্ট ঝুঁকি মূল্যায়ন",
      body: "সমুদ্রে যাওয়ার আগে সরকারি ডেটা সূত্র, রিয়েল-টাইম চার্ট এবং স্বচ্ছ সুরক্ষা স্কোর সহ একটি সৎ পরামর্শ পান।",
      detail: "নিয়ম-ভিত্তিক ঝুঁকি ইঞ্জিন · ১০০% বিশ্বস্ত প্রমাণ",
    },
  ],
  te: [
    {
      num: "01",
      tag: "ప్రశ్న & రేవు",
      title: "మీ భాషలో అడగండి, మాట్లాడి లేదా రాసి",
      body: "తెలుగు, తమిళం, హిందీ లేదా ఇంగ్లీషులో సహజంగా అడగండి. తరంగ్ భారతీయ తీరప్రాంత రేవులు మరియు ఫిషింగ్ ల్యాండింగ్ కేంద్రాలను గుర్తిస్తుంది.",
      detail: "విస్పర్ వాయిస్ గుర్తింపు · బహుభాషా విశ్లేషణ",
    },
    {
      num: "02",
      tag: "సరిచూసే ప్రక్రియ",
      title: "నిపుణ ఏజెంట్లు ఏకకాలంలో దర్యాప్తు చేస్తారు",
      body: "ఆరు ప్రత్యేక ఏజెంట్లు ప్రత్యక్ష అలల ఎత్తు, గాలి వేగం, ఉపగ్రహ క్లోరోఫిల్ చేపల మండలాలు, తుఫాను హెచ్చరికలను పరిశీలిస్తారు.",
      detail: "ఓపెన్-మెటియో · INCOIS ఉపగ్రహం · GDACS హెచ్చరికలు",
    },
    {
      num: "03",
      tag: "భద్రతా తీర్పు",
      title: "ఆధారాలతో కూడిన సమాధానం మరియు నిర్ణయం",
      body: "సముద్రంలోకి వెళ్ళే ముందు అధికారిక డేటా మూలాలు, ప్రత్యక్ష సముద్ర మ్యాప్ మరియు స్పష్టమైన భద్రతా నివేదికను పొందండి.",
      detail: "నియమ ఆధారిత రిస్క్ ఇంజిన్ · 100% నిరూపిత ఆధారాలు",
    },
  ],
  ml: [
    {
      num: "01",
      tag: "ചോദ്യം & തുറമുഖം",
      title: "നിങ്ങളുടെ ഭാഷയിൽ ചോദിക്കുക, ശബ്ദത്തിലോ എഴുത്തിലോ",
      body: "മലയാളം, തമിഴ്, ഹിന്ദി അല്ലെങ്കിൽ ഇംഗ്ലീഷിൽ സംസാരിക്കുക. തരംഗ് തുറമുഖങ്ങളും മത്സ്യ ലാൻഡിംഗ് കേന്ദ്രങ്ങളും തത്സമയം തിരിച്ചറിയുന്നു.",
      detail: "വിസ്പർ ശബ്ദ തിരിച്ചറിയൽ · ബഹുഭാഷാ നിർണ്ണയം",
    },
    {
      num: "02",
      tag: "പരിശോധന & പഠനം",
      title: "വിദഗ്ദ്ധ ഏജന്റുകൾ ഒരേസമയം പരിശോധിക്കുന്നു",
      body: "ആറ് സ്വതന്ത്ര ഏജന്റുകൾ തത്സമയ തിരമാലകൾ, കാറ്റ്, ഉപഗ്രഹ മത്സ്യ മേഖലകൾ, ചുഴലിക്കാറ്റ് മുന്നറിയിപ്പുകൾ എന്നിവ വിശകലനം ചെയ്യുന്നു.",
      detail: "ഓപ്പൺ-മെറ്റിയോ · INCOIS ഉപഗ്രഹം · GDACS മുന്നറിയിപ്പ്",
    },
    {
      num: "03",
      tag: "സുരക്ഷാ വിധി",
      title: "തെളിവുകൾ അടിസ്ഥാനമാക്കിയുള്ള വ്യക്തമായ ഉത്തരം",
      body: "കടലിൽ പോകുന്നതിന് മുൻപ് ഔദ്യോഗിക വിവരങ്ങൾ, ലൈവ് മാപ്പ്, സുതാര്യമായ സുരക്ഷാ സ്കോർ എന്നിവ നേടുക.",
      detail: "കൃത്യമായ സുരക്ഷാ സംവിധാനം · 100% അടിസ്ഥാനരേഖകൾ",
    },
  ],
  mr: [
    {
      num: "01",
      tag: "प्रश्न आणि बंदर",
      title: "आपल्या भाषेत बोला किंवा टाईप करा",
      body: "मराठी, हिंदी किंवा इंग्रजीत विचारा. तरंग आपोआप भारतीय सागरी बंदरे आणि मासळी उतरवण केंद्रे ओळखतो.",
      detail: "व्हिस्पर व्हॉइस ओळख · बहुभाषिक समज",
    },
    {
      num: "02",
      tag: "तपासणी प्रक्रिया",
      title: "विशेषज्ञ एजंट्स एकाच वेळी तपासणी करतात",
      body: "सहा तज्ञ एजंट थेट लाटांची उंची, वाऱ्याचा वेग, उपग्रह मासेमारी क्षेत्रे आणि चक्रीवादळ सूचना तपासतात.",
      detail: "ओपन-मेटिओ · INCOIS उपग्रह · GDACS इशारे",
    },
    {
      num: "03",
      tag: "सुरक्षा निर्णय",
      title: "पुरावे-आधारित उत्तर आणि स्पष्ट धोका पातळी",
      body: "समुद्रात जाण्यापूर्वी अधिकृत माहिती स्रोत, थेट सागरी नकाशा आणि पारदर्शक सुरक्षा अहवाल मिळवा.",
      detail: "नियम-आधारित सुरक्षा इंजिन · १००% सत्य पुरावे",
    },
  ],
  od: [
    {
      num: "01",
      tag: "ପ୍ରଶ୍ନ ଓ ବନ୍ଦର",
      title: "ନିଜ ଭାଷାରେ କୁହନ୍ତୁ ବା ଲେଖି ପଚାରନ୍ତୁ",
      body: "ଓଡ଼ିଆ, ହିନ୍ଦୀ ବା ଇଂରାଜୀରେ ପଚାରନ୍ତୁ। ତରଙ୍ଗ ସ୍ୱୟଂଚାଳିତ ଭାବେ ଭାରତୀୟ ଉପକୂଳ ବନ୍ଦର ଓ ମତ୍ସ୍ୟ ଅବତରଣ କେନ୍ଦ୍ରଗୁଡ଼ିକୁ ଚିହ୍ନଟ କରେ।",
      detail: "ହୁଇସ୍ପର ଭଏସ୍ ଚିହ୍ନଟ · ବହୁଭାଷୀ ବିଶ୍ଳେଷଣ",
    },
    {
      num: "02",
      tag: "ଯାଞ୍ଚ ପ୍ରକ୍ରିୟା",
      title: "ବିଶେଷଜ୍ଞ ଏଜେଣ୍ଟମାନେ ଏକକାଳୀନ ଅନୁସନ୍ଧାନ କରନ୍ତି",
      body: "ଛଅ ଜଣ ବିଶେଷଜ୍ଞ ଏଜେଣ୍ଟ ପ୍ରତ୍ୟକ୍ଷ ଢେଉ, ପବନର ଗତି, ଉପଗ୍ରହ ମତ୍ସ୍ୟ କ୍ଷେତ୍ର ଓ ବାତ୍ୟା ଚେତାବନୀ ଯାଞ୍ଚ କରନ୍ତି।",
      detail: "ଓପନ-ମେଟିଓ · INCOIS ଉପଗ୍ରହ · GDACS ସତର୍କତା",
    },
    {
      num: "03",
      tag: "ସୁରକ୍ଷା ନିଷ୍ପତ୍ତି",
      title: "ପ୍ରମାଣ-ଆଧାରିତ ଉତ୍ତର ଓ ସ୍ପଷ୍ଟ ସୁରକ୍ଷା ମୂଲ୍ୟାୟନ",
      body: "ସମୁଦ୍ରକୁ ଯିବା ପୂର୍ବରୁ ସରକାରୀ ତଥ୍ୟ ଆଧାର, ଲାଇଭ ସାମୁଦ୍ରିକ ମାନଚିତ୍ର ଏବଂ ନିର୍ଭୁଲ ବିପଦ ସ୍ତର ପ୍ରାପ୍ତ କରନ୍ତୁ।",
      detail: "ନିୟମ-ଆଧାରିତ ସୁରକ୍ଷା ବ୍ୟବସ୍ଥା · ୧୦୦% ପ୍ରମାଣିତ ତଥ୍ୟ",
    },
  ],
};

export const HowItWorksSection: React.FC<Props> = ({
  language,
  className = "",
}) => {
  const t = translations[language] || translations.en;
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

  const steps = STEPS[language] || STEPS.en;

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
          {t.howItWorksEyebrow}
        </div>

        {/* Editorial headline */}
        <div
          className={`max-w-[680px] mb-12 sm:mb-16 transition-all duration-500 delay-100 ${
            isVisible ? "reveal-visible" : "reveal-init"
          }`}
        >
          <h2 className="font-serif-display text-2xl sm:text-3xl lg:text-4xl font-normal text-[var(--ink)] tracking-tight leading-snug">
            {t.howItWorksHeadline}
          </h2>
          <p className="font-sans text-sm sm:text-base text-[var(--ink-muted)] mt-3 leading-relaxed">
            {t.howItWorksSub}
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
