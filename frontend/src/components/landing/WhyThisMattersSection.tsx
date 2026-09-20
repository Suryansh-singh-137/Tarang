"use client";

import React, { useEffect, useRef, useState } from "react";
import { LanguageCode } from "@/lib/types";
import { translations } from "@/lib/i18n";

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

const STATS_DATA: Record<LanguageCode, StatDef[]> = {
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
  gu: [
    {
      target: 7516,
      suffix: " કિમી",
      label: "દરિયાકાંઠાની દેખરેખ",
      title: "સક્રિય તટીય પરિમિતિ",
      description: "૯ તટીય રાજ્યો અને ૪ કેન્દ્રશાસિત પ્રદેશોમાં ભારતીય મુખ્ય ભૂમિ અને ટાપુઓના દરિયાકાંઠાનું સતત વિશ્લેષણ.",
      source: "બંદરો, શિપિંગ અને જળમાર્ગ મંત્રાલય",
    },
    {
      target: 1265,
      suffix: "+",
      label: "ઉતરાણ કેન્દ્રો",
      title: "બંદરો અને મત્સ્ય ઉતરાણ સ્થળો",
      description: "વાસ્તવિક સમયના દરિયાઈ સ્થિતિ મૉડલ સાથે નકશા પર દર્શાવેલ પરંપરાગત મત્સ્ય કેન્દ્રો અને મુખ્ય બંદરો.",
      source: "CMFRI દરિયાઈ મત્સ્યજનગણના",
    },
    {
      target: 6,
      label: "વિશેષજ્ઞ એજન્ટો",
      title: "ડોમેન ઈન્ટેલિજન્સ યુનિટ્સ",
      description: "હવામાન, મોજાં, ક્લોરોફિલ PFZ, વાવાઝોડાની ચેતવણીઓ અને આંતરરાષ્ટ્રીય દરિયાઈ સીમાઓની પુષ્ટિ કરતા વિશેષજ્ઞ એજન્ટો.",
      source: "તરંગ મલ્ટી-એજન્ટ મહાસાગર પ્રણાલી",
    },
    {
      target: 0,
      label: "ખોટા દાવા",
      title: "શૂન્ય ભ્રમ સહિષ્ણુતા",
      description: "બધા જવાબો ૧૦૦% પ્રમાણિત અને વૈજ્ઞાનિક પુરાવા પર આધારિત છે. સુરક્ષા-સંવેદનશીલ નિર્ણયોમાં કોઈ અનુમાન નહીં.",
      source: "તરંગ પુરાવા ચકાસણી માળખું",
    },
  ],
  bn: [
    {
      target: 7516,
      suffix: " কিমি",
      label: "উপকূলীয় পর্যবেক্ষণ",
      title: "সক্রিয় উপকূলীয় পরিধি",
      description: "৯টি উপকূলীয় রাজ্য এবং ৪টি কেন্দ্রশাসিত অঞ্চল জুড়ে ভারতীয় মূল ভূখণ্ড ও দ্বীপপুঞ্জের উপকূলরেখা ক্রমাগত বিশ্লেষিত।",
      source: "বন্দর, জাহাজ ও জলপথ মন্ত্রণালয়",
    },
    {
      target: 1265,
      suffix: "+",
      label: "ল্যান্ডিং কেন্দ্র",
      title: "বন্দর ও মাছ ধরার কেন্দ্র",
      description: "রিয়েল-টাইম সমুদ্র পরিস্থিতির মডেল সহ ঐতিহ্যবাহী মাছ ধরার ঘাট ও প্রধান বন্দর মানচিত্রায়িত।",
      source: "CMFRI সামুদ্রিক মৎস্য শুমারি",
    },
    {
      target: 6,
      label: "বিশেষজ্ঞ এজেন্ট",
      title: "ডোমেন বিশ্লেষণ ইউনিট",
      description: "আবহাওয়া, ঢেউ, ক্লোরোফিল পিএফজেড, ঘূর্ণিঝড় এবং আন্তর্জাতিক সামুদ্রিক সীমানা যাচাইকারী বিশেষ এজেন্ট।",
      source: "তরঙ্গ মাল্টি-এজেন্ট ব্যবস্থা",
    },
    {
      target: 0,
      label: "ভিত্তিহীন দাবি",
      title: "শূন্য অনিশ্চয়তা নিশ্চয়তা",
      description: "সমস্ত উত্তর শতভাগ সুনির্দিষ্ট এবং সরকারি তথ্যে প্রমাণিত। নিরাপত্তাজনিত সিদ্ধান্তে কোনো কাল্পনিক অনুমানের স্থান নেই।",
      source: "তরঙ্গ প্রমাণ যাচাইকরণ কাঠামো",
    },
  ],
  te: [
    {
      target: 7516,
      suffix: " కి.మీ",
      label: "తీరప్రాంత పర్యవేక్షణ",
      title: "క్రియాశీల తీర పరిధి",
      description: "9 తీరప్రాంత రాష్ట్రాలు, 4 కేంద్రపాలిత ప్రాంతాలలో భారత ప్రధాన భూభాగం మరియు ద్వీప తీరప్రాంతం నిరంతర విశ్లేషణ.",
      source: "నౌకాశ్రయాలు, షిప్పింగ్ మరియు జలమార్గాల మంత్రిత్వ శాఖ",
    },
    {
      target: 1265,
      suffix: "+",
      label: "ల్యాండింగ్ కేంద్రాలు",
      title: "రేవులు మరియు చేపల ల్యాండింగ్ ప్రాంతాలు",
      description: "నిజ-సమయ సముద్ర పరిస్థితుల నమూనాలతో మ్యాప్ చేయబడిన సంప్రదాయ చేపల ల్యాండింగ్ కేంద్రాలు మరియు ప్రధాన రేవులు.",
      source: "CMFRI సముద్ర మత్స్య గణన",
    },
    {
      target: 6,
      label: "నిపుణ ఏజెంట్లు",
      title: "రంగ నిఘా విభాగాలు",
      description: "వాతావరణం, అలలు, క్లోరోఫిల్ PFZ, తుఫాను హెచ్చరికలు మరియు అంతర్జాతీయ సముద్ర సరిహద్దులను ధృవీకరించే ప్రత్యేక ఏజెంట్లు.",
      source: "తరంగ్ మల్టీ-ఏజెంట్ మహాసముద్ర వ్యవస్థ",
    },
    {
      target: 0,
      label: "కల్పిత వాదనలు",
      title: "సున్నా భ్రమ సహనం",
      description: "ప్రతి సమాధానం 100% ఖచ్చితమైనది మరియు నిరూపిత ఆధారాలతో కూడినది. భద్రతా మార్గంలో ఊహాగానాలకు తావులేదు.",
      source: "తరంగ్ నిరూపిత ఆధారాల నిర్మాణం",
    },
  ],
  ml: [
    {
      target: 7516,
      suffix: " കി.മീ",
      label: "തീരദേശ നിരീക്ഷണം",
      title: "സജീവ തീരദേശ ചുറ്റളവ്",
      description: "9 തീരദേശ സംസ്ഥാനങ്ങളിലെയും 4 കേന്ദ്രഭരണ പ്രദേശങ്ങളിലെയും ഇന്ത്യൻ തീരപ്രദേശങ്ങളുടെ നിരന്തരമായ സുരക്ഷാ വിശകലനം.",
      source: "തുറമുഖ, കപ്പൽ ഗതാഗത മന്ത്രാലയം",
    },
    {
      target: 1265,
      suffix: "+",
      label: "ലാൻഡിംഗ് കേന്ദ്രങ്ങൾ",
      title: "തുറമുഖങ്ങളും ഫിഷ് ലാൻഡിംഗ് കേന്ദ്രങ്ങളും",
      description: "തത്സമയ കടൽ അവസ്ഥാ മോഡലുകൾ ഉപയോഗിച്ച് മാപ്പ് ചെയ്ത പരമ്പരാഗത ഫിഷ് ലാൻഡിംഗ് കേന്ദ്രങ്ങളും പ്രധാന തുറമുഖങ്ങളും.",
      source: "CMFRI മറൈൻ ഫിഷറീസ് സെൻസസ്",
    },
    {
      target: 6,
      label: "വിദഗ്ദ്ധ ഏജന്റുകൾ",
      title: "ഡൊമെയ്ൻ ഇന്റലിജൻസ് യൂണിറ്റുകൾ",
      description: "കാലാവസ്ഥ, തിരമാലകൾ, ക്ലോറോഫിൽ PFZ, ചുഴലിക്കാറ്റ് മുന്നറിയിപ്പുകൾ, അന്താരാഷ്ട്ര സമുദ്ര അതിർത്തികൾ എന്നിവ പരിശോധിക്കുന്ന ഏജന്റുകൾ.",
      source: "തരംഗ് മൾട്ടി-ഏജന്റ് സിസ്റ്റം",
    },
    {
      target: 0,
      label: "വ്യാജ അവകാശവാദങ്ങൾ",
      title: "പൂർണ്ണ കൃത്യത",
      description: "എല്ലാ ഉത്തരങ്ങളും 100% ശാസ്ത്രീയ ഡാറ്റയെ അടിസ്ഥാനമാക്കിയുള്ളതാണ്. സുരക്ഷാ തീരുമാനങ്ങളിൽ ഊഹങ്ങൾക്ക് സ്ഥാനമില്ല.",
      source: "തരംഗ് എവിഡൻസ് വെരിഫിക്കേഷൻ",
    },
  ],
  mr: [
    {
      target: 7516,
      suffix: " किमी",
      label: "किनारपट्टी देखरेख",
      title: "सक्रिय सागरी परिमिती",
      description: "९ किनारी राज्ये आणि ४ केंद्रशासित प्रदेशांमध्ये भारताची मुख्य भूमी व बेटांच्या किनारपट्टीचे सातत्यपूर्ण विश्लेषण.",
      source: "बंदरे, नौवहन आणि जलमार्ग मंत्रालय",
    },
    {
      target: 1265,
      suffix: "+",
      label: "लँडिंग केंद्रे",
      title: "बंदरे आणि मासळी उतरवण केंद्रे",
      description: "थेट सागरी परिस्थितीच्या मॉडेल्ससह नकाशावर आणलेली पारंपरिक मासळी उतरवण केंद्रे आणि प्रमुख मासेमारी बंदरे.",
      source: "CMFRI सागरी मत्स्यव्यवसाय जनगणना",
    },
    {
      target: 6,
      label: "विशेषज्ञ एजंट्स",
      title: "डोमेन विश्लेषण युनिट्स",
      description: "हवामान, लाटा, क्लोरोफिल मासेमारी क्षेत्र, चक्रीवादळ इशारे आणि सागरी सीमा यांची खातरजमा करणारे सहा स्वतंत्र एजंट्स.",
      source: "तरंग मल्टी-एजंट प्रणाली",
    },
    {
      target: 0,
      label: "खोटे दावे",
      title: "शून्य अनिश्चितता हमी",
      description: "प्रत्येक उत्तर १००% वस्तुनिष्ठ आणि वैज्ञानिक पुराव्यांवर आधारित आहे. सुरक्षिततेच्या मार्गात अनुमानांना थारा नाही.",
      source: "तरंग पुरावा पडताळणी रचना",
    },
  ],
  od: [
    {
      target: 7516,
      suffix: " କି.ମି",
      label: "ଉପକୂଳ ନିରୀକ୍ଷଣ",
      title: "ସକ୍ରିୟ ଉପକୂଳ ପରିଧି",
      description: "୯ଟି ଉପକୂଳ ରାଜ୍ୟ ଓ ୪ଟି କେନ୍ଦ୍ରଶାସିତ ଅଞ୍ଚଳରେ ଭାରତୀୟ ମୁଖ୍ୟ ଭୂମି ଏବଂ ଦ୍ୱୀପପୁଞ୍ଜର ଉପକୂଳ ନିରନ୍ତର ବିଶ୍ଳେଷିତ।",
      source: "ବନ୍ଦର, ଜାହାଜ ଚଳାଚଳ ଏବଂ ଜଳପଥ ମନ୍ତ୍ରଣାଳୟ",
    },
    {
      target: 1265,
      suffix: "+",
      label: "ମତ୍ସ୍ୟ ଅବତରଣ କେନ୍ଦ୍ର",
      title: "ବନ୍ଦର ଓ ମାଛ ଅବତରଣ ସ୍ଥଳ",
      description: "ପ୍ରତ୍ୟକ୍ଷ ସାମୁଦ୍ରିକ ସ୍ଥିତି ମଡେଲ ସହିତ ମାନଚିତ୍ରିତ ପାରମ୍ପରିକ ମାଛ ଅବତରଣ କେନ୍ଦ୍ର ଓ ପ୍ରମୁଖ ମାଛଧରା ବନ୍ଦର।",
      source: "CMFRI ସାମୁଦ୍ରିକ ମତ୍ସ୍ୟ ଗଣନା",
    },
    {
      target: 6,
      label: "ବିଶେଷଜ୍ଞ ଏଜେଣ୍ଟ",
      title: "ବିଶ୍ଳେଷଣ ୟୁନିଟ୍",
      description: "ପାଣିପାଗ, ଢେଉ, କ୍ଲୋରୋଫିଲ୍ PFZ, ବାତ୍ୟା ସତର୍କତା ଓ ଆନ୍ତର୍ଜାତୀୟ ସାମୁଦ୍ରିକ ସୀମା ଯାଞ୍ଚ କରୁଥିବା ୬ଟି ଏଜେଣ୍ଟ।",
      source: "ତରଙ୍ଗ ମଲ୍ଟି-ଏଜେଣ୍ଟ ମହାସାଗର ବ୍ୟବସ୍ଥା"
    },
    {
      target: 0,
      label: "କଳ୍ପିତ ଦାବି",
      title: "ଶୂନ୍ୟ ଭ୍ରାନ୍ତି ସହନଶୀଳତା",
      description: "ସମସ୍ତ ଉତ୍ତର ୧୦୦% ନିର୍ଦ୍ଦିଷ୍ଟ ଏବଂ ପ୍ରମାଣ-ଆଧାରିତ। ସୁରକ୍ଷା ନିଷ୍ପତ୍ତିରେ କୌଣସି କାଳ୍ପନିକ ଅନୁମାନ ନାହିଁ।",
      source: "ତରଙ୍ଗ ପ୍ରମାଣ ଯାଞ୍ଚ ବ୍ୟବସ୍ଥା"
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

  const t = translations[language] || translations.en;
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
          {t.whyMattersEyebrow}
        </div>

        {/* Section Headline */}
        <div
          className={`max-w-[720px] mb-12 sm:mb-16 transition-all duration-500 delay-100 ${
            hasEntered ? "reveal-visible" : "reveal-init"
          }`}
        >
          <h2 className="font-serif-display text-2xl sm:text-3xl lg:text-4xl font-normal text-[var(--ink)] tracking-tight leading-snug">
            {t.whyMattersHeadline}
          </h2>
          <p className="font-sans text-sm sm:text-base text-[var(--ink-muted)] mt-3 leading-relaxed">
            {t.whyMattersSub}
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
            <span>{t.whyMattersFooter}</span>
          </div>
          <div className="text-[10px] tracking-wider uppercase text-[var(--ink-muted)]">
            {t.whyMattersVerified}
          </div>
        </div>
      </div>
    </section>
  );
};
