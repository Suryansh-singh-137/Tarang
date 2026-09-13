// i18n translation dictionary for English, Hindi, and Tamil UI chrome

import { LanguageCode } from "./types";

export type UIStrings = {
  appTitle: string;
  appSubtitle: string;
  landingEyebrow: string;
  landingHeroLine1: string;
  landingHeroLine2: string;
  landingHeadline: string;
  landingSubtitle: string;
  askTarangBtn: string;
  typeInstead: string;
  listening: string;
  transcribing: string;
  tapToSpeak: string;
  holdToSpeak: string;
  inputPlaceholder: string;
  readAloud: string;
  stopAudio: string;
  synthesizingAudio: string;
  thinking: string;
  evaluatingConditions: string;
  navChat: string;
  navMap: string;
  navTrace: string;
  navDashboard: string;
  liveConditions: string;
  activeAlerts: string;
  noActiveAlerts: string;
  quickLocations: string;
  suggestedQueries: string;
  dataSources: string;
  emergencyContacts: string;
  coastGuardEmergency: string;
  incoisHelpline: string;
  disclaimer: string;
  waveHeight: string;
  windSpeed: string;
  seaState: string;
  safetyScore: string;
  evidenceItems: string;
  reasoningTrace: string;
  agentStatus: string;
  viewMap: string;
  fallbackWarning: string;
  proxyWarning: string;
  noLocationFound: string;
  inlandLocationWarning: string;
  prompts: {
    safeTomorrow: string;
    pfzNear: string;
    cycloneCheck: string;
    seaConditions: string;
  };
};

export const translations: Record<LanguageCode, UIStrings> = {
  en: {
    appTitle: "Tarang",
    appSubtitle: "Marine Safety & Fisheries Intelligence",
    landingEyebrow: "SERIES 01 / LIVE SEA INTELLIGENCE",
    landingHeroLine1: "Your sea,",
    landingHeroLine2: "before you sail.",
    landingHeadline: "Ask about marine conditions, fishing zones, and safety — in your language.",
    landingSubtitle: "Decision support for coastal fishermen before venturing to sea.",
    askTarangBtn: "Ask Tarang",
    typeInstead: "type your query instead",
    listening: "Listening... speak now",
    transcribing: "Transcribing your voice...",
    tapToSpeak: "Tap to Speak",
    holdToSpeak: "Push to talk",
    inputPlaceholder: "Ask in English, Hindi, or Tamil (e.g. Is it safe to fish near Thoothukudi tomorrow?)",
    readAloud: "Read Aloud",
    stopAudio: "Stop",
    synthesizingAudio: "Synthesizing voice...",
    thinking: "Analyzing marine intelligence...",
    evaluatingConditions: "Checking weather, satellite PFZ, and hazard advisories...",
    navChat: "Chat",
    navMap: "Marine Map",
    navTrace: "Reasoning Trace",
    navDashboard: "Overview",
    liveConditions: "Live Conditions",
    activeAlerts: "Active Hazard Alert",
    noActiveAlerts: "No active cyclone or severe weather alerts reported nearby.",
    quickLocations: "Quick Coastal Places",
    suggestedQueries: "Try asking",
    dataSources: "Data Sources & Authority",
    emergencyContacts: "Emergency Numbers",
    coastGuardEmergency: "Coast Guard Search & Rescue: 1554",
    incoisHelpline: "INCOIS Coastal Information: 040-23895011",
    disclaimer: "Tarang is a decision-support tool. Always heed official Indian Coast Guard and IMD directives before sailing.",
    waveHeight: "Wave Height",
    windSpeed: "Wind Speed",
    seaState: "Sea State",
    safetyScore: "Safety Verdict",
    evidenceItems: "Evidence & Citations",
    reasoningTrace: "Agent Reasoning Steps",
    agentStatus: "Status",
    viewMap: "View on Map",
    fallbackWarning: "Using cached fallback data — live service temporarily unreachable.",
    proxyWarning: "Derived satellite indicator (Oceansat-2 chlorophyll), not an official advisory.",
    noLocationFound: "Please specify a recognized Indian coastal port or location.",
    inlandLocationWarning: "Requested location appears inland. Marine intelligence applies only to coastal waters.",
    prompts: {
      safeTomorrow: "Is it safe to go fishing near Thoothukudi tomorrow morning?",
      pfzNear: "Where are the nearest potential fishing zones near Chennai?",
      cycloneCheck: "Are there any active cyclone or storm warnings near Kochi?",
      seaConditions: "What are the wind and wave conditions near Diu today?",
    },
  },
  hi: {
    appTitle: "तरंग",
    appSubtitle: "समुद्री सुरक्षा एवं मत्स्य पालन आसूचना",
    landingEyebrow: "श्रृंखला 01 / लाइव समुद्री सूचना",
    landingHeroLine1: "आपका समुद्र,",
    landingHeroLine2: "नाव निकालने से पहले।",
    landingHeadline: "समुद्री स्थिति, मछली पकड़ने के क्षेत्र और सुरक्षा के बारे में अपनी भाषा में पूछें।",
    landingSubtitle: "समुद्र में जाने से पहले तटीय मछुआरों के लिए त्वरित निर्णय सहायता।",
    askTarangBtn: "तरंग से पूछें",
    typeInstead: "लिखकर पूछें",
    listening: "सुन रहे हैं... बोलिए",
    transcribing: "आवाज को शब्दों में बदला जा रहा है...",
    tapToSpeak: "बोलने के लिए दबाएं",
    holdToSpeak: "माइक दबाकर बोलें",
    inputPlaceholder: "हिंदी, तमिल या अंग्रेजी में पूछें (उदा. क्या कल सुबह तूतीकोरिन के पास जाना सुरक्षित है?)",
    readAloud: "आवाज में सुनें",
    stopAudio: "रोकें",
    synthesizingAudio: "आवाज तैयार हो रही है...",
    thinking: "समुद्री जानकारी की जांच हो रही है...",
    evaluatingConditions: "मौसम, उपग्रह मछली क्षेत्र और चेतावनियों का विश्लेषण जारी है...",
    navChat: "संवाद",
    navMap: "समुद्री मानचित्र",
    navTrace: "तर्क एवं प्रमाण",
    navDashboard: "वर्तमान स्थिति",
    liveConditions: "ताजा समुद्री स्थिति",
    activeAlerts: "सक्रिय समुद्री चेतावनी",
    noActiveAlerts: "आस-पास कोई सक्रिय चक्रवात या गंभीर मौसम चेतावनी नहीं है।",
    quickLocations: "प्रमुख तटीय स्थल",
    suggestedQueries: "सुझाए गए प्रश्न",
    dataSources: "डेटा स्रोत एवं प्रमाणिकता",
    emergencyContacts: "आपातकालीन संपर्क",
    coastGuardEmergency: "तटरक्षक खोज एवं बचाव: 1554",
    incoisHelpline: "INCOIS तटीय हेल्पलाइन: 040-23895011",
    disclaimer: "तरंग निर्णय-सहायता प्रणाली है। समुद्र में जाने से पहले तटरक्षक और IMD के आधिकारिक निर्देशों का पालन करें।",
    waveHeight: "लहरों की ऊंचाई",
    windSpeed: "हवा की गति",
    seaState: "समुद्र की स्थिति",
    safetyScore: "सुरक्षा निर्णय",
    evidenceItems: "तथ्य और प्रमाण",
    reasoningTrace: "एजेंट विश्लेषण चरण",
    agentStatus: "स्थिति",
    viewMap: "नक्शे पर देखें",
    fallbackWarning: "कैश्ड बैकअप डेटा प्रयुक्त — लाइव स्रोत अस्थायी रूप से अनुपलब्ध।",
    proxyWarning: "उपग्रह क्लोरोफिल सूचक (INCOIS), आधिकारिक परामर्श नहीं।",
    noLocationFound: "कृपया किसी भारतीय तटीय बंदरगाह या स्थल का नाम बताएं।",
    inlandLocationWarning: "यह स्थल अंतर्देशीय प्रतीत होता है। समुद्री सलाह केवल तटीय क्षेत्रों हेतु है।",
    prompts: {
      safeTomorrow: "क्या कल सुबह तूतीकोरिन के पास मछली पकड़ने जाना सुरक्षित है?",
      pfzNear: "चेन्नई के पास सबसे नजदीकी मछली पकड़ने का क्षेत्र कहाँ है?",
      cycloneCheck: "क्या कोच्चि के पास कोई चक्रवात या तूफान की चेतावनी है?",
      seaConditions: "दीव के पास आज हवा और लहरों की स्थिति कैसी रहेगी?",
    },
  },
  ta: {
    appTitle: "தரங்",
    appSubtitle: "கடல்சார் பாதுகாப்பு & மீன்பிடி வழிகாட்டி",
    landingEyebrow: "தொடர் 01 / நேரலை கடல் நுண்ணறிவு",
    landingHeroLine1: "உங்கள் கடல்,",
    landingHeroLine2: "நீங்கள் கடலுக்குச் செல்லும் முன்.",
    landingHeadline: "கடல் நிலை, மீன்பிடி பகுதிகள் மற்றும் பாதுகாப்பு பற்றி உங்கள் மொழியில் கேளுங்கள்.",
    landingSubtitle: "கடலுக்குச் செல்லும் முன் மீனவர்களுக்கான நம்பகமான பாதுகாப்பு வழிகாட்டல்.",
    askTarangBtn: "தரங்கிடம் கேளுங்கள்",
    typeInstead: "எழுதி கேட்க",
    listening: "கேட்கிறது... பேசுங்கள்",
    transcribing: "குரல் உரையாக மாற்றப்படுகிறது...",
    tapToSpeak: "பேச அழுத்தவும்",
    holdToSpeak: "அழுத்தி பேசவும்",
    inputPlaceholder: "தமிழ், இந்தி அல்லது ஆங்கிலத்தில் கேளுங்கள் (எ.கா. நாளை காலை தூத்துக்குடி செல்வது பாதுகாப்பானதா?)",
    readAloud: "கேட்க",
    stopAudio: "நிறுத்து",
    synthesizingAudio: "குரல் தயாராகிறது...",
    thinking: "கடல்சார் தரவுகள் ஆராயப்படுகின்றன...",
    evaluatingConditions: "வானிலை, மீன்பிடி மண்டலங்கள் மற்றும் எச்சரிக்கைகள் பரிசீலிக்கப்படுகின்றன...",
    navChat: "உரையாடல்",
    navMap: "கடல் வரைபடம்",
    navTrace: "காரண விளக்கம்",
    navDashboard: "கண்ணோட்டம்",
    liveConditions: "தற்போதைய கடல் நிலை",
    activeAlerts: "செயலில் உள்ள எச்சரிக்கை",
    noActiveAlerts: "அருகில் புயல் அல்லது தீவிர வானிலை எச்சரிக்கைகள் எதுவும் இல்லை.",
    quickLocations: "கடலோர இடங்கள்",
    suggestedQueries: "பரிந்துரைக்கப்பட்ட கேள்விகள்",
    dataSources: "தரவு மூலங்கள்",
    emergencyContacts: "அவசர எண்கள்",
    coastGuardEmergency: "கடலோர காவல்படை: 1554",
    incoisHelpline: "INCOIS உதவி எண்: 040-23895011",
    disclaimer: "தரங் ஒரு முடிவு ஆதரவு கருவி. கடலுக்குச் செல்வதற்கு முன் அதிகாரப்பூர்வ எச்சரிக்கைகளைப் பின்பற்றவும்.",
    waveHeight: "அலை உயரம்",
    windSpeed: "காற்றின் வேகம்",
    seaState: "கடல் நிலை",
    safetyScore: "பாதுகாப்பு தீர்ப்பு",
    evidenceItems: "ஆதாரங்கள்",
    reasoningTrace: "ஆய்வு படிகள்",
    agentStatus: "நிலை",
    viewMap: "வரைபடத்தில் காண்க",
    fallbackWarning: "சேமிக்கப்பட்ட காப்புப் பிரதி தரவு பயன்படுத்தப்படுகிறது.",
    proxyWarning: "செயற்கைக்கோள் குளோரோபில் குறியீடு (INCOIS).",
    noLocationFound: "தயவுசெய்து ஒரு இந்திய கடலோர துறைமுகம் அல்லது இடத்தை குறிப்பிடவும்.",
    inlandLocationWarning: "கோரப்பட்ட இடம் உள்நாட்டில் உள்ளது. கடல்சார் தகவல் கடலோரப் பகுதிகளுக்கு மட்டுமே பொருந்தும்.",
    prompts: {
      safeTomorrow: "நாளை காலை தூத்துக்குடி கடலில் மீன்பிடிக்க செல்வது பாதுகாப்பானதா?",
      pfzNear: "சென்னைக்கு அருகில் உள்ள மீன்பிடி மண்டலம் எங்கே உள்ளது?",
      cycloneCheck: "கொச்சிக்கு அருகில் ஏதேனும் புயல் எச்சரிக்கை உள்ளதா?",
      seaConditions: "டையூ அருகில் இன்றைய காற்றின் வேகம் மற்றும் அலை உயரம் என்ன?",
    },
  },
};
