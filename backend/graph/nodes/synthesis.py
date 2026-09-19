"""
synthesis node
--------------
The only node that produces user-facing text.

Milestone 2 additions:
  - Evidence section: lists source attribution for each data stream
  - Data-status section: ✓ Live / ⚠️ Fallback per agent
  - Fallback disclosure: explicit when any agent used cached data
  - PFZ proxy attribution: clarifies chlorophyll-based PFZ indicator
  - Hazard limitation: notes that cyclone advisories require IMD/INCOIS check

Milestone 3 additions:
  - data_quality third-state: Live / Fallback / Historical Proxy per agent
  - PFZ proxy label hardened: always disclosed as chlorophyll-based historical proxy
  - Synthesis MUST NOT emit unqualified "it is safe" or "it is not safe";
    all risk assessments must be qualified as decision-support only.
  - Top risk contributors named immediately after the risk badge (M4).

Explainability contract (PRD §4.3):
  - Every sentence in final_answer_text MUST be attributable to a source
    in trace[].
  - If a specialist agent returned status "error", explicitly state what
    could NOT be determined.
  - If no hazard warning was found, phrase it as "no relevant warning found
    in the available data", NOT as a safety guarantee.
  - Synthesis MUST NOT invent measurements, timestamps, or sources.
  - Synthesis MUST NOT emit unqualified 'it is safe' or 'it is not safe'.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
import json
import re
import logging

import config
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate

from graph.state import AgentResult, EvidenceItem, ORCAState, AnswerPlan

# ---------------------------------------------------------------------------
# Language-specific phrase tables
# ---------------------------------------------------------------------------

_PHRASES: dict[str, dict[str, str]] = {
    "en": {
        "preamble": "Here is Tarang's marine safety assessment for {location} ({time_window}):",
        "weather_intro": "🌊 Marine Weather Conditions",
        "pfz_intro": "🐟 Fishing Potential Indicator (Chlorophyll Proxy)",
        "hazard_intro": "⚠️ Weather Condition Hazard Indicators",
        "geofence_intro": "🗺️ Maritime Boundary",
        "risk_intro": "📊 Overall Risk Assessment",
        "evidence_intro": "📋 Data Sources & Evidence",
        "data_status_intro": "📡 Data Freshness & Quality",
        "skipped": "ℹ️ {aspect} not applicable or not requested for this query.",
        "error": "Live {aspect} data is currently unavailable for this location.",
        "fallback_note": "⚠️ **Cached data in use**: {agents}. Live source(s) were temporarily unreachable; results reflect the latest available verified dataset.",
        "pfz_proxy_note": (
            "ℹ️ **Data Quality Note**: Fishing potential zones above are derived from INCOIS Oceansat-2 "
            "chlorophyll-a historical satellite data — this is a scientific proxy indicator, "
            "not a real-time official INCOIS PFZ advisory. "
            "For official PFZ advisories, consult the INCOIS portal at incois.gov.in."
        ),
        "cyclone_note": "ℹ️ **Cyclone advisory**: Real-time cyclone warnings require direct consultation with IMD (imd.gov.in) or INCOIS (incois.gov.in). The above represents weather-condition hazard indicators only.",
        "disclaimer": (
            "⚠️ **Disclaimer**: This is a decision-support assessment, not an official safety clearance. "
            "Tarang assesses available conditions as a navigational aid — always follow "
            "advisories from IMD, INCOIS, and the Indian Coast Guard before departing."
        ),
    },
    "hi": {
        "preamble": "{location} के लिए Tarang का समुद्री सुरक्षा आकलन ({time_window}):",
        "weather_intro": "🌊 समुद्री स्थिति",
        "pfz_intro": "🐟 मछली पकड़ने के क्षेत्र सूचक (क्लोरोफिल आधारित)",
        "hazard_intro": "⚠️ मौसम संबंधी खतरे के संकेतक",
        "geofence_intro": "🗺️ समुद्री सीमा",
        "risk_intro": "📊 कुल जोखिम आकलन",
        "evidence_intro": "📋 डेटा स्रोत और साक्ष्य",
        "data_status_intro": "📡 डेटा की ताज़गी और गुणवत्ता",
        "skipped": "ℹ️ {aspect} इस प्रश्न के लिए लागू या आवश्यक नहीं है।",
        "error": "इस स्थान के लिए लाइव {aspect} डेटा वर्तमान में उपलब्ध नहीं है।",
        "fallback_note": "⚠️ **कैश्ड डेटा उपयोग में है**: {agents}। लाइव स्रोत अस्थायी रूप से अनुपलब्ध है।",
        "pfz_proxy_note": (
            "ℹ️ **डेटा गुणवत्ता नोट**: मछली पकड़ने के क्षेत्र INCOIS Oceansat-2 "
            "क्लोरोफिल-a ऐतिहासिक उपग्रह डेटा पर आधारित वैज्ञानिक सूचक हैं — "
            "यह आधिकारिक INCOIS PFZ परामर्श नहीं है।"
        ),
        "cyclone_note": "ℹ️ **चक्रवात परामर्श**: वास्तविक समय की चक्रवात चेतावनियों के लिए IMD/INCOIS से सीधे जाँचें।",
        "disclaimer": (
            "⚠️ **अस्वीकरण**: यह एक निर्णय-सहायता आकलन है, आधिकारिक सुरक्षा मंजूरी नहीं। "
            "IMD, INCOIS और भारतीय तटरक्षक बल की सलाह का पालन करें।"
        ),
    },
    "ta": {
        "preamble": "{location} க்கான Tarang கடல் பாதுகாப்பு மதிப்பீடு ({time_window}):",
        "weather_intro": "🌊 கடல் நிலைகள்",
        "pfz_intro": "🐟 மீன்பிடி திறன் சுட்டி (குளோரோஃபில் அடிப்படை)",
        "hazard_intro": "⚠️ வானிலை ஆபத்து சுட்டிகள்",
        "geofence_intro": "🗺️ கடல் எல்லை",
        "risk_intro": "📊 ஒட்டுமொத்த ஆபத்து மதிப்பீடு",
        "evidence_intro": "📋 தரவு மூலங்கள்",
        "data_status_intro": "📡 தரவு புதுமை மற்றும் தரம்",
        "skipped": "ℹ️ {aspect} இந்தக் கேள்விக்கு பொருந்தாது அல்லது கோரப்படவில்லை.",
        "error": "இந்த இடத்திற்கான நேரடி {aspect} தரவு தற்போது கிடைக்கவில்லை.",
        "fallback_note": "⚠️ **தற்காலிக சேமிக்கப்பட்ட தரவு பயன்படுத்தப்படுகிறது**: {agents}.",
        "pfz_proxy_note": (
            "Data quality note: Fishing potential zones are derived from INCOIS Oceansat-2 satellite proxy."
        ),
        "cyclone_note": "Cyclone advisory: Real-time warnings require consultation with IMD or INCOIS.",
        "disclaimer": (
            "Disclaimer: This is a decision-support assessment, not an official safety clearance."
        ),
    },
    "gu": {
        "preamble": "{location} માટે Tarang દરિયાઈ સુરક્ષા આકલન ({time_window}):",
        "weather_intro": "🌊 દરિયાઈ હવામાન સ્થિતિ",
        "pfz_intro": "🐟 સંભવિત માછીમારી ક્ષેત્ર (સેટેલાઇટ ક્લોરોફિલ)",
        "hazard_intro": "⚠️ હવામાન જોખમ સૂચકાંકો",
        "geofence_intro": "🗺️ દરિયાઈ સીમા",
        "risk_intro": "📊 એકંદર જોખમ મૂલ્યાંકન",
        "evidence_intro": "📋 ડેટા સ્ત્રોત અને પુરાવા",
        "data_status_intro": "📡 ડેટા તાજગી અને ગુણવત્તા",
        "skipped": "ℹ️ {aspect} આ પ્રશ્ન માટે લાગુ નથી.",
        "error": "આ સ્થળ માટે લાઈવ {aspect} ડેટા હાલ ઉપલબ્ધ નથી.",
        "fallback_note": "⚠️ **કેશ્ડ ડેટા વપરાઈ રહ્યો છે**: {agents}.",
        "pfz_proxy_note": "ડેટા ગુણવત્તા નોંધ: સંભવિત માછીમારી ક્ષેત્રો INCOIS Oceansat-2 સેટેલાઇટ પ્રોક્સી આધારિત છે.",
        "cyclone_note": "વાવાઝોડા સલાહ: રીઅલ-ટાઇમ ચેતવણીઓ માટે IMD અથવા INCOIS નો સંપર્ક કરો.",
        "disclaimer": "અસ્વીકરણ: આ એક નિર્ણય સહાય આકલન છે, સત્તાવાર સુરક્ષા મંજૂરી નથી.",
    },
    "bn": {
        "preamble": "{location}-এর জন্য Tarang সামুদ্রিক সুরক্ষা মূল্যায়ন ({time_window}):",
        "weather_intro": "🌊 সামুদ্রিক আবহাওয়া পরিস্থিতি",
        "pfz_intro": "🐟 মৎস্য সম্ভাবনাময় অঞ্চল (উপগ্রহ ক্লোরোফিল নির্দেশক)",
        "hazard_intro": "⚠️ আবহাওয়া বিপদ নির্দেশক",
        "geofence_intro": "🗺️ আন্তর্জাতিক সামুদ্রিক সীমানা",
        "risk_intro": "📊 সামগ্রিক ঝুঁকি মূল্যায়ন",
        "evidence_intro": "📋 উপাত্ত উৎস ও প্রমাণ",
        "data_status_intro": "📡 তথ্যের নির্ভরযোগ্যতা ও মান",
        "skipped": "ℹ️ {aspect} এই প্রশ্নের জন্য প্রযোজ্য নয়।",
        "error": "এই অবস্থানের জন্য লাইভ {aspect} তথ্য বর্তমানে উপলব্ধ নেই।",
        "fallback_note": "⚠️ **ক্যাশ তথ্য ব্যবহৃত হচ্ছে**: {agents}।",
        "pfz_proxy_note": "তথ্য মান নোট: মৎস্য সম্ভাবনাময় অঞ্চল INCOIS Oceansat-2 উপগ্রহ প্রক্সি ভিত্তিক।",
        "cyclone_note": "ঘূর্ণিঝড় পরামর্শ: তাৎক্ষণিক সতর্কতার জন্য IMD বা INCOIS-এর সাথে যোগাযোগ করুন।",
        "disclaimer": "সতর্কবার্তা: এটি একটি সিদ্ধান্ত সহায়তা ব্যবস্থা, কোনো সরকারি অনুমোদন নয়।",
    },
    "te": {
        "preamble": "{location} కోసం Tarang సముద్ర భద్రత అంచనా ({time_window}):",
        "weather_intro": "🌊 సముద్ర వాతావరణ పరిస్థితులు",
        "pfz_intro": "🐟 సంభావ్య చేపల వేట ప్రాంతం (క్లోరోఫిల్ ఆధారితం)",
        "hazard_intro": "⚠️ వాతావరణ ప్రమాద సూచికలు",
        "geofence_intro": "🗺️ సముద్ర సరిహద్దు",
        "risk_intro": "📊 మొత్తం ప్రమాద అంచనా",
        "evidence_intro": "📋 సమాచార వనరులు & ఆధారాలు",
        "data_status_intro": "📡 సమాచార తాజాదనం",
        "skipped": "ℹ️ {aspect} ఈ ప్రశ్నకు వర్తించదు.",
        "error": "ఈ ప్రదేశానికి ప్రత్యక్ష {aspect} సమాచారం అందుబాటులో లేదు.",
        "fallback_note": "⚠️ **కాష్ సమాచారం ఉపయోగించబడింది**: {agents}.",
        "pfz_proxy_note": "సమాచార గమనిక: చేపల వేట ప్రాంతాలు INCOIS Oceansat-2 ఉపగ్రహ డేటా ఆధారితం.",
        "cyclone_note": "తుఫాను హెచ్చరిక: తాజా హెచ్చరికల కోసం IMD లేదా INCOIS ను సంప్రదించండి.",
        "disclaimer": "గమనిక: ఇది సహాయక నిర్ణయ సాధనం మాత్రమే, అధికారిక అనుమతి కాదు.",
    },
    "ml": {
        "preamble": "{location} സംബന്ധിച്ച Tarang സമുദ്ര സുരക്ഷാ വിലയിരുത്തൽ ({time_window}):",
        "weather_intro": "🌊 സമുദ്ര കാലാവസ്ഥ",
        "pfz_intro": "🐟 മത്സ്യ ലഭ്യത സൂചന (ക്ലോറോഫിൽ അധിഷ്ഠിതം)",
        "hazard_intro": "⚠️ കാലാവസ്ഥാ മുന്നറിയിപ്പുകൾ",
        "geofence_intro": "🗺️ സമുദ്ര അതിർത്തി",
        "risk_intro": "📊 മൊത്തം അപകടസാധ്യത വിലയിരുത്തൽ",
        "evidence_intro": "📋 വിവര സ്രോതസ്സുകൾ",
        "data_status_intro": "📡 വിവര നിലവാരം",
        "skipped": "ℹ️ {aspect} ഈ ചോദ്യത്തിന് ബാധകമല്ല.",
        "error": "ഈ സ്ഥലത്തെ തത്സമയ {aspect} വിവരങ്ങൾ ലഭ്യമല്ല.",
        "fallback_note": "⚠️ **കാഷെ വിവരങ്ങൾ ഉപയോഗിക്കുന്നു**: {agents}.",
        "pfz_proxy_note": "വിവരക്കുറിപ്പ്: മത്സ്യബന്ധന മേഖലകൾ INCOIS Oceansat-2 സാറ്റലൈറ്റ് ഡാറ്റയെ അടിസ്ഥാനമാക്കിയുള്ളതാണ്.",
        "cyclone_note": "ചുഴലിക്കാറ്റ് മുന്നറിയിപ്പ്: തത്സമയ മുന്നറിയിപ്പുകൾക്കായി IMD അല്ലെങ്കിൽ INCOIS പരിശോധിക്കുക.",
        "disclaimer": "ശ്രദ്ധിക്കുക: ഇത് ഒരു തീരുമാന സഹായ സംവിധാനമാണ്, ഔദ്യോഗിക അനുമതിയല്ല.",
    },
    "mr": {
        "preamble": "{location} साठी Tarang सागरी सुरक्षा मूल्यांकन ({time_window}):",
        "weather_intro": "🌊 सागरी हवामान स्थिती",
        "pfz_intro": "🐟 संभाव्य मासेमारी क्षेत्र (उपग्रह क्लोरोफिल सूचक)",
        "hazard_intro": "⚠️ हवामान धोका निर्देशांक",
        "geofence_intro": "🗺️ सागरी सीमा",
        "risk_intro": "📊 एकूण धोका मूल्यांकन",
        "evidence_intro": "📋 डेटा स्रोत आणि पुरावे",
        "data_status_intro": "📡 डेटा ताजेपणा आणि गुणवत्ता",
        "skipped": "ℹ️ {aspect} या प्रश्नासाठी लागू नाही.",
        "error": "या स्थानासाठी थेट {aspect} डेटा सध्या उपलब्ध नाही.",
        "fallback_note": "⚠️ **कॅश केलेला डेटा वापरला जात आहे**: {agents}.",
        "pfz_proxy_note": "डेटा गुणवत्ता नोंद: संभाव्य मासेमारी क्षेत्र INCOIS Oceansat-2 उपग्रह डेटावर आधारित आहेत.",
        "cyclone_note": "वादळ सल्ला: रिअल-टाइम चेतावणीसाठी IMD किंवा INCOIS चा सल्ला घ्या.",
        "disclaimer": "अस्वीकरण: हे निर्णय-सहाय्य मूल्यांकन आहे, अधिकृत सुरक्षा मंजुरी नाही.",
    },
    "od": {
        "preamble": "{location} ପାଇଁ Tarang ସାମୁଦ୍ରିକ ସୁରକ୍ଷା ଆକଳନ ({time_window}):",
        "weather_intro": "🌊 ସାମୁଦ୍ରିକ ପାଣିପାଗ ସ୍ଥିତି",
        "pfz_intro": "🐟 ସମ୍ଭାବ୍ୟ ମତ୍ସ୍ୟ କ୍ଷେତ୍ର (ଉପଗ୍ରହ କ୍ଲୋରୋଫିଲ ସୂଚକ)",
        "hazard_intro": "⚠️ ପାଣିପାଗ ବିପଦ ସୂଚକ",
        "geofence_intro": "🗺️ ସାମୁଦ୍ରିକ ସୀମା",
        "risk_intro": "📊 ସମୁଦାୟ ବିପଦ ମୂଲ୍ୟାଙ୍କନ",
        "evidence_intro": "📋 ତଥ୍ୟ ଉତ୍ସ ଓ ପ୍ରମାଣ",
        "data_status_intro": "📡 ତଥ୍ୟର ସତେଜତା ଓ ଗୁଣବତ୍ତା",
        "skipped": "ℹ️ {aspect} ଏହି ପ୍ରଶ୍ନ ପାଇଁ ଲାଗୁ ନୁହେଁ।",
        "error": "ଏହି ସ୍ଥାନ ପାଇଁ ଲାଇଭ {aspect} ତଥ୍ୟ ବର୍ତ୍ତମାନ ଉପଲବ୍ଧ ନାହିଁ।",
        "fallback_note": "⚠️ **କ୍ୟାସ୍ ତଥ୍ୟ ବ୍ୟବହୃତ ହେଉଛି**: {agents}।",
        "pfz_proxy_note": "ତଥ୍ୟ ନୋଟ୍: ମତ୍ସ୍ୟ କ୍ଷେତ୍ରଗୁଡ଼ିକ INCOIS Oceansat-2 ଉପଗ୍ରହ ତଥ୍ୟ ଉପରେ ଆଧାରିତ।",
        "cyclone_note": "ବାତ୍ୟା ସୂଚନା: ତତ୍କାଳ ଚେତାବନୀ ପାଇଁ IMD କିମ୍ବା INCOIS ସହିତ ଯୋଗାଯୋଗ କରନ୍ତୁ।",
        "disclaimer": "ଦାୟିତ୍ୱହୀନତା: ଏହା ଏକ ନିଷ୍ପତ୍ତି ସହାୟତା ମୂଲ୍ୟାଙ୍କନ, ସରକାରୀ ଅନୁମତି ନୁହେଁ।",
    },
}

_TIME_LABELS: dict[str, dict[str, str]] = {
    "en": {
        "tomorrow_morning": "tomorrow morning",
        "tomorrow_evening": "tomorrow evening",
        "tomorrow": "tomorrow",
        "now": "now",
        "today": "today",
        "next_24h": "next 24 hours",
        "morning": "morning",
        "evening": "evening",
    },
    "hi": {
        "tomorrow_morning": "कल सुबह",
        "tomorrow_evening": "कल शाम",
        "tomorrow": "कल",
        "now": "अभी",
        "today": "आज",
        "next_24h": "अगले 24 घंटे",
        "morning": "सुबह",
        "evening": "शाम",
    },
    "ta": {
        "tomorrow_morning": "நாளை காலை",
        "tomorrow_evening": "நாளை மாலை",
        "tomorrow": "நாளை",
        "now": "இப்போது",
        "today": "இன்று",
        "next_24h": "அடுத்த 24 மணி நேரம்",
        "morning": "காலை",
        "evening": "மாலை",
    },
    "gu": {
        "tomorrow_morning": "આવતીકાલે સવારે",
        "tomorrow_evening": "આવતીકાલે સાંજે",
        "tomorrow": "આવતીકાલે",
        "now": "હમણાં",
        "today": "આજે",
        "next_24h": "આગામી 24 કલાક",
        "morning": "સવારે",
        "evening": "સાંજે",
    },
    "bn": {
        "tomorrow_morning": "কাল সকালে",
        "tomorrow_evening": "কাল সন্ধ্যায়",
        "tomorrow": "কাল",
        "now": "এখন",
        "today": "আজ",
        "next_24h": "পরবর্তী ২৪ ঘণ্টা",
        "morning": "সকালে",
        "evening": "সন্ধ্যায়",
    },
    "te": {
        "tomorrow_morning": "రేపు ఉదయం",
        "tomorrow_evening": "రేపు సాయంత్రం",
        "tomorrow": "రేపు",
        "now": "ఇప్పుడు",
        "today": "ఈ రోజు",
        "next_24h": "తదుపరి 24 గంటలు",
        "morning": "ఉదయం",
        "evening": "సాయంత్రం",
    },
    "ml": {
        "tomorrow_morning": "നാളെ രാവിലെ",
        "tomorrow_evening": "നാളെ വൈകുന്നേരം",
        "tomorrow": "നാളെ",
        "now": "ഇപ്പോൾ",
        "today": "ഇന്ന്",
        "next_24h": "അടുത്ത 24 മണിക്കൂർ",
        "morning": "രാവിലെ",
        "evening": "വൈകുന്നേരം",
    },
    "mr": {
        "tomorrow_morning": "उद्या सकाळी",
        "tomorrow_evening": "उद्या संध्याकाळी",
        "tomorrow": "उद्या",
        "now": "आता",
        "today": "आज",
        "next_24h": "पुढील २४ तास",
        "morning": "सकाळी",
        "evening": "संध्याकाळी",
    },
    "od": {
        "tomorrow_morning": "କାଲି ସକାଳେ",
        "tomorrow_evening": "କାଲି ସନ୍ଧ୍ୟାରେ",
        "tomorrow": "କାଲି",
        "now": "ଏବେ",
        "today": "ଆଜି",
        "next_24h": "ଆଗାମୀ ୨୪ ଘଣ୍ଟା",
        "morning": "ସକାଳେ",
        "evening": "ସନ୍ଧ୍ୟାରେ",
    },
}


def _deg_to_compass(deg: Optional[float]) -> str:
    if deg is None:
        return "—"
    dirs = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
            "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
    return dirs[round(deg / 22.5) % 16]


def _render_template(
    lang: str,
    location: str,
    time_window: str,
    weather: Optional[AgentResult],
    pfz: Optional[AgentResult],
    hazard: Optional[AgentResult],
    geofence: Optional[AgentResult],
    risk: Optional[AgentResult],
    evidence: list[EvidenceItem],
    ocean: Optional[AgentResult] = None,
) -> str:
    p = _PHRASES.get(lang, _PHRASES["en"])

    # PRD §3.1, §6.1, §8: If risk assessment was computed successfully, output fisherman-friendly Layer 1
    if risk and risk.get("status") == "success" and risk.get("data"):
        d = risk["data"]
        label = str(d.get("risk_label", "LOW")).upper()

        if lang == "hi":
            badge_map = {
                "LOW": "🟢 अभी कम जोखिम है।",
                "MODERATE": "🟡 अभी मध्यम जोखिम है (सावधानी आवश्यक)।",
                "HIGH": "🔴 अभी उच्च जोखिम है।",
                "EXTREME": "🔴 समुद्र में जाना अभी खतरनाक है।",
            }
            badge = badge_map.get(label, f"जोखिम स्तर: {label}")
        elif lang == "ta":
            badge_map = {
                "LOW": "🟢 தற்போது குறைந்த ஆபத்து.",
                "MODERATE": "🟡 தற்போது நடுத்தர ஆபத்து (எச்சரிக்கை தேவை).",
                "HIGH": "🔴 தற்போது அதிக ஆபத்து.",
                "EXTREME": "🔴 கடலுக்குச் செல்வது ஆபத்தானது.",
            }
            badge = badge_map.get(label, f"ஆபத்து நிலை: {label}")
        else:
            badge_map = {
                "LOW": "🟢 Low risk right now.",
                "MODERATE": "🟡 Moderate risk right now.",
                "HIGH": "🔴 High risk right now.",
                "EXTREME": "🔴 Dangerous conditions right now.",
            }
            badge = badge_map.get(label, f"Conditions rated {label} risk.")

        cond_parts = []
        if weather and weather.get("status") == "success" and weather.get("data"):
            wd = weather["data"]
            wave = wd.get("wave_height_m", 1.0)
            wind = wd.get("wind_speed_kmh", 15.0)
            if wave <= 1.25 and wind <= 20.0:
                if lang == "hi":
                    cond_parts.append("समुद्र काफी शांत है, लहरें छोटी हैं और हवा हल्की है।")
                elif lang == "ta":
                    cond_parts.append("கடல் அமைதியாக உள்ளது, சிறிய அலைகள் மற்றும் லேசான காற்று வீசுகிறது.")
                else:
                    cond_parts.append("The sea is fairly calm, with small waves and light wind.")
            elif wave <= 2.2 and wind <= 35.0:
                if lang == "hi":
                    cond_parts.append("मध्यम लहरें और हवा उपस्थित हैं, समुद्र की स्थिति पर नज़र रखें।")
                elif lang == "ta":
                    cond_parts.append("நடுத்தர அலைகள் மற்றும் காற்று வீசுகிறது, கடல் நிலையை கவனிக்கவும்.")
                else:
                    cond_parts.append("Moderate sea conditions are present, with manageable waves and breeze.")
            else:
                if lang == "hi":
                    cond_parts.append("तेज़ लहरें या तेज़ हवा सक्रिय हैं।")
                elif lang == "ta":
                    cond_parts.append("உயர்ந்த அலைகள் அல்லது பலத்த காற்று வீசுகிறது.")
                else:
                    cond_parts.append("Rough seas with elevated waves or strong winds are present.")

        if hazard and hazard.get("status") in ("success", "partial") and hazard.get("data"):
            hd = hazard["data"]
            active = hd.get("active_warnings", [])
            level = hd.get("overall_hazard_level", "none")
            if not active or level == "none":
                if lang == "hi":
                    cond_parts.append("कोई बड़ी मौसम चेतावनी सक्रिय नहीं है।")
                elif lang == "ta":
                    cond_parts.append("பெரிய வானிலை எச்சரிக்கை எதுவும் இல்லை.")
                else:
                    cond_parts.append("No major weather warning is active.")
            else:
                warn_str = ", ".join(str(w) for w in active)
                if lang == "hi":
                    cond_parts.append(f"सक्रिय मौसम चेतावनी: {warn_str}।")
                elif lang == "ta":
                    cond_parts.append(f"செயலில் உள்ள எச்சரிக்கை: {warn_str}.")
                else:
                    cond_parts.append(f"Active weather advisory: {warn_str}.")

        # Cached data disclosure (PRD §12 & §26)
        if pfz and (pfz.get("data_quality") in ("fallback", "historical_proxy") or pfz.get("used_fallback")):
            if lang == "hi":
                cond_parts.append("ℹ️ मछली पकड़ने के क्षेत्र का डेटा लाइव डेटा के बजाय नवीनतम उपलब्ध डेटासेट से है।")
            elif lang == "ta":
                cond_parts.append("ℹ️ மீன்பிடி மண்டலத் தரவு நேரடித் தரவை விட சமீபத்திய கிடைக்கக்கூடிய தொகுப்பிலிருந்து பெறப்பட்டது.")
            else:
                cond_parts.append("ℹ️ Some fishing-zone data is from the latest available dataset rather than live data.")

        # Safety recommendation (PRD §8)
        rec = d.get("recommendation")
        if not rec:
            rec_map = {
                "LOW": "Conditions are currently rated low risk by Tarang. Check the latest official advisory before leaving shore.",
                "MODERATE": "Conditions need caution. Check the latest advisory and sea conditions before leaving shore.",
                "HIGH": "Conditions are risky right now. Avoid going out until conditions improve and official advisories allow it.",
                "EXTREME": "Conditions are dangerous right now. Avoid going out until conditions improve and official advisories allow it.",
            }
            rec = rec_map.get(label, "Check the latest official advisory before leaving shore.")

        return f"{badge}\n{' '.join(cond_parts)}\n{rec}"

    # Fallback when risk is not present or failed (status mapping compatibility)
    lines: list[str] = [p["preamble"].format(location=location, time_window=time_window), ""]

    if weather is None or weather.get("status") in ("error", "insufficient_data") or weather.get("execution_status") == "failed" or weather.get("data_status") == "unavailable" or not weather.get("data"):
        lines.append(p["error"].format(aspect="marine weather"))
    elif weather.get("status") == "skipped":
        lines.append(p["skipped"].format(aspect="Weather conditions"))

    if pfz and (pfz.get("status") in ("error", "insufficient_data") or pfz.get("execution_status") == "failed" or pfz.get("data_status") == "unavailable"):
        lines.append(p["error"].format(aspect="fishing zone (PFZ)"))
        lines.append("Fishing-zone suitability could not be assessed because PFZ data is unavailable.")
        lines.append("Partial Assessment: Showing available weather assessment.")

    if hazard and (hazard.get("status") in ("error", "insufficient_data") or hazard.get("execution_status") == "failed" or hazard.get("data_status") == "unavailable"):
        lines.append(p["error"].format(aspect="hazard warning"))

    if not any(lines[2:]):
        lines.append("Tarang does not have enough reliable data to assess the trip safely right now (conditions unknown, critical data unavailable).")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# GeoJSON builder
# ---------------------------------------------------------------------------

def _build_geojson(
    intent_lat: float,
    intent_lon: float,
    location_name: str,
    pfz: Optional[AgentResult],
    geofence: Optional[AgentResult],
    risk: Optional[AgentResult],
) -> dict:
    """
    Build a GeoJSON FeatureCollection for the map panel.
    GeoJSON coordinate order: [longitude, latitude] (RFC 7946).
    """
    features: list[dict] = []

    # 1) Query point — coloured by risk level
    risk_color = "#22c55e"  # green = LOW
    risk_label = "LOW"
    if risk and risk["status"] == "success":
        level = risk["data"]["risk_label"]
        risk_label = level
        risk_color = {
            "LOW":     "#22c55e",
            "MODERATE":"#f59e0b",
            "HIGH":    "#ef4444",
            "EXTREME": "#7c3aed",
        }.get(level, "#6b7280")

    features.append({
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [intent_lon, intent_lat]},
        "properties": {
            "feature_type": "query_point",
            "name": location_name,
            "risk_label": risk_label,
            "risk_color": risk_color,
            "risk_score": risk["data"]["composite_score"] if risk and risk["status"] == "success" else None,
        },
    })

    # 2) PFZ zones — [lon, lat] coordinate order per RFC 7946
    if pfz and pfz["status"] == "success":
        for zone in pfz["data"].get("zones", []):
            features.append({
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [zone["lon"], zone["lat"]],   # [lon, lat]
                },
                "properties": {
                    "feature_type": "pfz_zone",
                    "zone_id": zone.get("zone_id", "PFZ"),
                    "description": zone.get("description", ""),
                    "distance_km": zone.get("distance_km"),
                    "chlorophyll_mg_m3": zone.get("chlorophyll_mg_m3"),
                    "source": zone.get("source", "INCOIS ERDDAP"),
                },
            })

    # 3) IMBL boundary line
    from tools.boundary_geo import load_imbl_waypoints
    boundary_coords = [[lon, lat] for lat, lon in load_imbl_waypoints()]
    if boundary_coords:
        features.append({
            "type": "Feature",
            "geometry": {"type": "LineString", "coordinates": boundary_coords},
            "properties": {
                "feature_type": "imbl_boundary",
                "name": "India–Sri Lanka Maritime Boundary Line (IMBL)",
                "color": "#ef4444",
                "dash": True,
            },
        })

    return {"type": "FeatureCollection", "features": features}


# ---------------------------------------------------------------------------
# Intent-specific response formatters (Section 16, 17, 39-43)
# ---------------------------------------------------------------------------

logger = logging.getLogger(__name__)


def _extract_numbers(text: str) -> set[float]:
    """Extract all numbers from text as floats for grounding checks."""
    matches = re.findall(r'\b\d+(?:\.\d+)?\b', text)
    nums = set()
    for m in matches:
        try:
            nums.add(float(m))
        except ValueError:
            pass
    return nums


def _render_location_response(lang: str, resolved: Optional[dict]) -> str:
    if not resolved:
        return "Unable to determine your location. Please provide a place name or enable device location access."
    name = resolved.get("name", "Unknown")
    lat = resolved.get("lat", 0.0)
    lon = resolved.get("lon", 0.0)
    is_coastal = resolved.get("coastal", False)

    if lang == "hi":
        status_hi = "तटीय क्षेत्र" if is_coastal else "अंतर्देशीय क्षेत्र"
        return f"आप वर्तमान में **{name}** में हैं।\n\n• **स्थान**: {name}\n• **अनुमानित निर्देशांक**: {lat:.2f}°N, {lon:.2f}°E\n• **प्रकार**: {status_hi}"
    elif lang == "ta":
        status_ta = "கடலோர பகுதி" if is_coastal else "உள்நாட்டு பகுதி"
        return f"நீங்கள் தற்போது **{name}** இல் உள்ளீர்கள்.\n\n• **இருப்பிடம்**: {name}\n• **ஆயத்தொலைவுகள்**: {lat:.2f}°N, {lon:.2f}°E\n• **வகை**: {status_ta}"
    else:
        status_en = "coastal location" if is_coastal else "inland location"
        return f"You're currently in **{name}**.\n\n• **Location**: {name}\n• **Approximate coordinates**: {lat:.2f}°N, {lon:.2f}°E\n• **Area type**: {status_en}"


def _render_inland_ocean_applicability(lang: str, resolved: Optional[dict]) -> str:
    name = resolved.get("name", "your location") if resolved else "your location"
    if lang == "hi":
        return (
            f"आपकी वर्तमान स्थिति **{name}** अंतर्देशीय (inland) है, इसलिए यहाँ स्थानीय ज्वार-भाटा या समुद्री जल स्तर का माप लागू नहीं होता है।\n\n"
            f"समुद्री जल स्तर या ज्वार की स्थिति देखने के लिए किसी तटीय बंदरगाह का नाम बताएं:\n"
            f"• **मुंबई (Mumbai)**\n• **कोच्चि (Kochi)**\n• **चेन्नई (Chennai)**\n• **विशाखापट्टनम (Visakhapatnam)**"
        )
    elif lang == "ta":
        return (
            f"உங்கள் தற்போதைய இருப்பிடம் **{name}** உள்நாட்டுப் பகுதியாகும், எனவே உள்ளூர் கடல் அலை அல்லது கடல் நீர்மட்ட அளவீடு இங்கு பொருந்தாது.\n\n"
            f"கடல் அலை அல்லது நீர்மட்ட தகவல்களை அறிய கடலோர இடத்தை முயற்சிக்கவும்:\n"
            f"• **மும்பை (Mumbai)**\n• **கொச்சி (Kochi)**\n• **சென்னை (Chennai)**\n• **விசாகப்பட்டினம் (Visakhapatnam)**"
        )
    else:
        return (
            f"Your current location is inland in **{name}**, so a local tide or sea-water level measurement is not applicable here.\n\n"
            f"{name} is inland and has no direct marine tidal coastline. I can check the tide or water level for a coastal location instead.\n\n"
            f"Try a coastal location:\n"
            f"• **Mumbai**\n• **Kochi**\n• **Chennai**\n• **Visakhapatnam**"
        )


def _render_weather_response(
    lang: str,
    resolved: Optional[dict],
    time_window: str,
    weather: Optional[AgentResult],
) -> str:
    loc_name = resolved.get("name", "your location") if resolved else "your location"
    tw = _TIME_LABELS.get(lang, _TIME_LABELS["en"]).get(time_window, time_window)

    lines = []
    if lang == "hi":
        lines.append(f"🌤 **{loc_name} — वर्तमान एवं पूर्वानुमानित मौसम ({tw})**\n")
    elif lang == "ta":
        lines.append(f"🌤 **{loc_name} — தற்போதைய மற்றும் முன்னறிவிப்பு வானிலை ({tw})**\n")
    else:
        lines.append(f"🌤 **Current & Forecast Weather — {loc_name} ({tw}):**\n")

    if not weather or weather.get("status") in ("error", "insufficient_data") or not weather.get("data"):
        lines.append("Live weather data is currently unavailable for this location.")
    else:
        d = weather.get("data", {})
        temp = d.get("temperature_c") or d.get("air_temperature_c")
        wind = d.get("wind_speed_kmh")
        wind_dir = _deg_to_compass(d.get("wind_direction_deg"))
        pressure = d.get("pressure_msl_hpa")
        wave = d.get("wave_height_m")
        sea = d.get("sea_state")

        conds = []
        if temp is not None:
            conds.append(f"Temperature is around {temp}°C")
        if wind is not None:
            conds.append(f"wind is {wind} km/h from {wind_dir}")
        if wave is not None:
            conds.append(f"wave height is {wave} m")
        if sea:
            conds.append(f"sea state is {sea}")
        if conds:
            lines.append("• " + ", ".join(conds) + ".")
        if pressure is not None:
            lines.append(f"• Air pressure: **{pressure} hPa** (MSL)")
        if d.get("visibility_km"):
            lines.append(f"• Visibility: {d['visibility_km']} km")

        src = weather.get("source", "Open-Meteo Marine + Forecast")
        lines.append(f"\n*(Source: {src})*")
    return "\n".join(lines)


def _render_ocean_response(
    lang: str,
    resolved: Optional[dict],
    ocean: Optional[AgentResult],
) -> str:
    loc_name = resolved.get("name", "coastal waters") if resolved else "coastal waters"
    lines = []
    if lang == "hi":
        lines.append(f"🌊 **{loc_name} — ज्वार एवं जल स्तर का पूर्वानुमान (Chart Datum)**\n")
    elif lang == "ta":
        lines.append(f"🌊 **{loc_name} — கடல் அலை மற்றும் நீர்மட்ட முன்னறிவிப்பு (Chart Datum)**\n")
    else:
        lines.append(f"🌊 **Tide & Water Level Prediction — {loc_name} (Chart Datum)**\n")

    if not ocean or ocean.get("status") in ("error", "insufficient_data") or not ocean.get("data"):
        lines.append("Live tide and ocean water level data is currently unavailable for this location.")
    else:
        od = ocean.get("data", {})
        wl = od.get("water_level_m", 0.0)
        phase = od.get("current_phase", "Normal")
        lines.append(f"• The current water level at **{loc_name}** is about **{wl:.2f} m** above chart datum.")
        lines.append(f"• Tide status: **{phase}** right now.")
        if od.get("next_high_tide"):
            ht = od["next_high_tide"]
            lines.append(f"• Next High Tide: **{ht.get('time_ist')}** ({ht.get('height_m')} m CD)")
        if od.get("next_low_tide"):
            lt = od["next_low_tide"]
            lines.append(f"• Next Low Tide: **{lt.get('time_ist')}** ({lt.get('height_m')} m CD)")
        lines.append(f"\n*(Source: {ocean.get('source', 'INCOIS ERDDAP')} • Type: Harmonic tidal prediction model)*")
    return "\n".join(lines)


def _render_pressure_response(
    lang: str,
    resolved: Optional[dict],
    weather: Optional[AgentResult],
) -> str:
    loc_name = resolved.get("name", "your location") if resolved else "your location"
    lines = [f"🌡 **Air Pressure (MSL) — {loc_name}**\n"]
    if weather and weather.get("status") == "success" and weather.get("data", {}).get("pressure_msl_hpa"):
        p = weather["data"]["pressure_msl_hpa"]
        lines.append(f"• Air pressure: **{p} hPa** (mean sea level datum)")
        lines.append(f"\n*(Source: {weather.get('source', 'Open-Meteo')})*")
    else:
        lines.append("Atmospheric surface pressure data is currently unavailable for this location.")
    return "\n".join(lines)


def _render_pfz_response(
    lang: str,
    resolved: Optional[dict],
    pfz: Optional[AgentResult],
) -> str:
    loc_name = resolved.get("name", "waters") if resolved else "waters"
    lines = [f"🐟 **Fishing Potential Indicator — {loc_name}**\n"]
    if pfz and pfz.get("status") == "success" and pfz.get("data"):
        d = pfz["data"]
        nearest = d.get("nearest_zone_km", 104)
        n_zones = len(d.get("zones", []))
        productivity = d.get("overall_productivity", "moderate")
        lines.append("🐟 Fishing indicator found.")
        if isinstance(nearest, (int, float)):
            lines.append(f"The nearest indicator zone is about **{nearest:.0f} km** away.")
        lines.append("It is based on satellite chlorophyll data and is only an indicator, not a guarantee of fish.")
        if n_zones > 1:
            lines.append(f"Total indicator zones identified: {n_zones} (general productivity: {productivity}).")
        lines.append(f"\n*(Source: {pfz.get('source', 'INCOIS Oceansat-2')} • Type: Satellite chlorophyll proxy)*")
    else:
        lines.append("Live fishing-zone data is currently unavailable for this location.")
    return "\n".join(lines)


def _render_sst_response(
    lang: str,
    resolved: Optional[dict],
    sst: Optional[AgentResult],
) -> str:
    loc_name = resolved.get("name", "coastal waters") if resolved else "coastal waters"
    lines = []
    if lang == "hi":
        lines.append(f"🌡 **{loc_name} — समुद्र की सतह का तापमान (SST)**\n")
    elif lang == "ta":
        lines.append(f"🌡 **{loc_name} — கடல் மேற்பரப்பு வெப்பநிலை (SST)**\n")
    else:
        lines.append(f"🌡 **Sea Surface Temperature (SST) — {loc_name}:**\n")

    if not sst or sst.get("status") in ("error", "insufficient_data") or not sst.get("data") or sst.get("data", {}).get("sst_celsius") is None:
        if lang == "hi":
            lines.append(f"इस स्थान ({loc_name}) के लिए INCOIS ERDDAP से लाइव SST डेटा वर्तमान में उपलब्ध नहीं है।")
            lines.append("\n*नोट: समुद्र की सतह का तापमान केवल तापीय स्थिति दर्शाता है और मछली की उपस्थिति की गारंटी नहीं देता है।*")
        elif lang == "ta":
            lines.append(f"இந்த இடத்திற்கான INCOIS ERDDAP நேரடி SST தரவு தற்போது கிடைக்கவில்லை.")
            lines.append("\n*குறிப்பு: கடல் மேற்பரப்பு வெப்பநிலை வெப்பநிலையை மட்டுமே குறிக்கிறது, மீன் இருப்பதை உறுதிப்படுத்தாது.*")
        else:
            lines.append(f"Live SST observation data is currently unavailable from INCOIS ERDDAP for {loc_name}.")
            lines.append("\n*Note: Sea surface temperature (SST) indicates physical thermal conditions only and does not guarantee fish presence.*")
    else:
        sd = sst.get("data", {})
        temp = sd.get("sst_celsius")
        anom = sd.get("sst_anomaly_c")
        obs_time = sd.get("observation_time", "")
        src = sst.get("source", "INCOIS ERDDAP (NOAA AVHRR/AMSR SST)")

        if lang == "hi":
            lines.append(f"• समुद्र की सतह का तापमान: **{temp:.2f}°C**")
            if anom is not None:
                lines.append(f"• थर्मल विसंगति (Anomaly): **{anom:+.2f}°C**")
            if obs_time:
                lines.append(f"• अवलोकन समय: {obs_time}")
            lines.append("\n*नोट: समुद्र की सतह का तापमान केवल तापीय रुझान दर्शाता है और मछली की उपस्थिति की गारंटी नहीं देता है।*")
        elif lang == "ta":
            lines.append(f"• கடல் மேற்பரப்பு வெப்பநிலை: **{temp:.2f}°C**")
            if anom is not None:
                lines.append(f"• வெப்ப முரண்பாடு (Anomaly): **{anom:+.2f}°C**")
            if obs_time:
                lines.append(f"• கவனிப்பு நேரம்: {obs_time}")
            lines.append("\n*குறிப்பு: கடல் மேற்பரப்பு வெப்பநிலை வெப்பநிலையை மட்டுமே குறிக்கிறது, மீன் இருப்பதை உறுதிப்படுத்தாது.*")
        else:
            lines.append(f"• Sea surface temperature: **{temp:.2f}°C**")
            if anom is not None:
                lines.append(f"• Temperature anomaly: **{anom:+.2f}°C** relative to baseline")
            if obs_time:
                lines.append(f"• Latest observation time: {obs_time}")
            lines.append("\n*Note: Sea surface temperature (SST) and thermal anomalies reflect physical oceanographic conditions only and do not guarantee fish presence.*")

        lines.append(f"\n*(Source: {src})*")

    return "\n".join(lines)


def _render_multi_intent_response(
    lang: str,
    resolved: Optional[dict],
    intent_groups: Optional[list[dict]],
    weather: Optional[AgentResult],
    ocean: Optional[AgentResult],
    pfz: Optional[AgentResult],
    hazard: Optional[AgentResult],
    risk: Optional[AgentResult],
) -> str:
    """PRD §16: Seamlessly blends multiple requested aspects into a natural conversational response."""
    loc_name = resolved.get("name", "the requested location") if resolved else "the requested location"
    groups = intent_groups or []
    intent_types = set()
    for g in groups:
        if isinstance(g, dict):
            if "intent" in g:
                intent_types.add(g["intent"])
            if "name" in g:
                intent_types.add(g["name"])
        elif isinstance(g, str):
            intent_types.add(g)

    sections: list[str] = []

    # 1. Location (if explicitly queried)
    if "LOCATION_QUERY" in intent_types:
        lat = resolved.get("lat", 0.0) if resolved else 0.0
        lon = resolved.get("lon", 0.0) if resolved else 0.0
        if lang == "hi":
            sections.append(f"📍 आप वर्तमान में **{loc_name}** ({lat:.2f}°N, {lon:.2f}°E) में हैं।")
        elif lang == "ta":
            sections.append(f"📍 நீங்கள் தற்போது **{loc_name}** ({lat:.2f}°N, {lon:.2f}°E) இல் உள்ளீர்கள்.")
        else:
            sections.append(f"📍 **Location**: Currently at **{loc_name}** ({lat:.2f}°N, {lon:.2f}°E).")

    # 2. Ocean / Water Level / Tide
    if (
        "WATER_LEVEL_QUERY" in intent_types
        or "TIDE_QUERY" in intent_types
        or (not intent_types and ocean and ocean.get("status") == "success")
    ):
        if resolved and not resolved.get("coastal", True):
            if lang == "hi":
                sections.append(f"🌊 **जल स्तर / ज्वार**: {loc_name} एक अंतर्देशीय क्षेत्र है, इसलिए यहाँ समुद्री ज्वार-भाटा लागू नहीं होता।")
            elif lang == "ta":
                sections.append(f"🌊 **நீர்மட்டம் / அலை**: {loc_name} உள்நாட்டுப் பகுதியாகும், எனவே கடல் அலை அளவீடு பொருந்தாது.")
            else:
                sections.append(f"🌊 **Water Level / Tide**: {loc_name} is inland and has no direct marine tidal coastline.")
        elif ocean and ocean.get("status") == "success" and ocean.get("data"):
            od = ocean["data"]
            wl = od.get("water_level_m", 0.0)
            phase = od.get("current_phase", "Normal")
            ht = od.get("next_high_tide")
            ht_str = f" (Next High Tide: {ht.get('time_ist')} at {ht.get('height_m')} m)" if ht else ""
            if lang == "hi":
                sections.append(f"🌊 **जल स्तर**: {loc_name} में वर्तमान जल स्तर चार्ट डेटम से लगभग {wl:.2f} मीटर ऊपर है और ज्वार {phase} स्थिति में है।{ht_str}")
            elif lang == "ta":
                sections.append(f"🌊 **நீர்மட்டம்**: {loc_name} இல் தற்போதைய நீர்மட்டம் சுமார் {wl:.2f} மீ, அலை நிலை {phase}.{ht_str}")
            else:
                sections.append(f"🌊 **Water Level & Tide**: Water level at {loc_name} is about **{wl:.2f} m** above chart datum (tide status: **{phase}**){ht_str}.")
        elif ocean and ocean.get("status") in ("error", "insufficient_data"):
            sections.append(f"🌊 **Water Level / Tide**: Tide and water level prediction data is currently unavailable for {loc_name}.")

    # 3. Weather / Wind / Sea conditions
    if (
        "WEATHER_QUERY" in intent_types
        or "SEA_LEVEL_PRESSURE_QUERY" in intent_types
        or any("wind" in str(t).lower() for t in intent_types)
        or (not intent_types and weather and weather.get("status") == "success")
    ):
        if weather and weather.get("status") == "success" and weather.get("data"):
            wd = weather["data"]
            temp = wd.get("temperature_c") or wd.get("air_temperature_c")
            wind = wd.get("wind_speed_kmh")
            wind_dir = _deg_to_compass(wd.get("wind_direction_deg"))
            wave = wd.get("wave_height_m")
            sea = wd.get("sea_state")

            w_parts = []
            if temp is not None:
                w_parts.append(f"Temperature: {temp}°C")
            if wind is not None:
                w_parts.append(f"Wind: {wind} km/h ({wind_dir})")
            if wave is not None:
                w_parts.append(f"Wave height: {wave} m")
            if sea:
                w_parts.append(f"Sea: {sea}")

            w_summary = ", ".join(w_parts) if w_parts else "Moderate conditions"
            if lang == "hi":
                sections.append(f"🌤 **मौसम एवं हवा**: {loc_name} में {w_summary}।")
            elif lang == "ta":
                sections.append(f"🌤 **வானிலை & காற்று**: {loc_name} இல் {w_summary}.")
            else:
                sections.append(f"🌤 **Weather & Wind**: {w_summary} at {loc_name}.")
        elif weather and weather.get("status") in ("error", "insufficient_data"):
            sections.append(f"🌤 **Weather**: Weather data is currently unavailable for {loc_name}.")

    # 4. Fishing Potential Indicator (PFZ)
    if (
        "PFZ_QUERY" in intent_types
        or any("fish" in str(t).lower() or "pfz" in str(t).lower() for t in intent_types)
        or (not intent_types and pfz and pfz.get("status") == "success")
    ):
        if pfz and pfz.get("status") == "success" and pfz.get("data"):
            pd = pfz["data"]
            dist = pd.get("nearest_zone_km")
            n_zones = len(pd.get("zones", []))
            dist_str = f"about **{dist:.0f} km** away" if dist is not None else "identified in coastal waters"
            if lang == "hi":
                sections.append(f"🐟 **मछली पकड़ने का संभावित क्षेत्र (PFZ)**: सबसे निकटतम संकेतक क्षेत्र लगभग {dist_str} है (उपग्रह क्लोरोफिल सूचक, मछली की गारंटी नहीं)।")
            elif lang == "ta":
                sections.append(f"🐟 **மீன்பிடி சாத்தியக்கூறு மண்டலம் (PFZ)**: அருகிலுள்ள பகுதி சுமார் {dist_str} தொலைவில் உள்ளது (செயற்கைக்கோள் குளோரோபில் குறியீடு).")
            else:
                sections.append(f"🐟 **Fishing Potential Indicator (PFZ)**: Nearest indicator zone is {dist_str} ({n_zones} zones detected; satellite chlorophyll proxy, not a fish guarantee).")
        elif pfz and pfz.get("status") in ("error", "insufficient_data"):
            sections.append(f"🐟 **Fishing Potential (PFZ)**: Fishing zone indicator data is currently unavailable for {loc_name}.")

    # 5. Hazard Advisories
    if (
        "HAZARD_QUERY" in intent_types
        or any("hazard" in str(t).lower() or "alert" in str(t).lower() or "warn" in str(t).lower() for t in intent_types)
        or (not intent_types and hazard and hazard.get("status") == "success")
    ):
        if hazard and hazard.get("status") == "success" and hazard.get("data"):
            hd = hazard["data"]
            active = hd.get("active_warnings", [])
            level = hd.get("overall_hazard_level", "none")
            if active:
                warn_str = ", ".join(str(w) for w in active)
                if lang == "hi":
                    sections.append(f"⚠️ **खतरे की चेतावनी**: सक्रिय अलर्ट: **{warn_str}** (स्तर: {level.upper()})।")
                elif lang == "ta":
                    sections.append(f"⚠️ **ஆபத்து எச்சரிக்கை**: செயலில் உள்ள எச்சரிக்கைகள்: **{warn_str}** ({level.upper()}).")
                else:
                    sections.append(f"⚠️ **Hazard Advisories**: Active warnings: **{warn_str}** (Hazard Level: {level.upper()}).")
            else:
                if lang == "hi":
                    sections.append(f"⚠️ **खतरे की चेतावनी**: {loc_name} के लिए कोई बड़ा गंभीर मौसम अलर्ट सक्रिय नहीं है।")
                elif lang == "ta":
                    sections.append(f"⚠️ **ஆபத்து எச்சரிக்கை**: {loc_name} க்கான பெரிய தீவிர வானிலை எச்சரிக்கை எதுவும் இல்லை.")
                else:
                    sections.append(f"⚠️ **Hazard Advisories**: No major severe weather warnings are active for {loc_name}.")
        elif hazard and hazard.get("status") in ("error", "insufficient_data"):
            sections.append(f"⚠️ **Hazard Advisories**: Hazard advisory data is currently unavailable for {loc_name}.")

    # 6. Marine Safety / Overall Trip Risk
    if (
        "MARINE_SAFETY_QUERY" in intent_types
        or any("safe" in str(t).lower() or "risk" in str(t).lower() for t in intent_types)
        or (not sections and risk and risk.get("status") == "success")
    ):
        if risk and risk.get("status") == "success":
            rd = risk["data"]
            label = str(rd.get("risk_label", "LOW")).upper()
            badge_map = {
                "LOW": "🟢 Low risk",
                "MODERATE": "🟡 Caution advised",
                "HIGH": "🔴 High risk",
                "EXTREME": "🔴 Dangerous conditions",
            }
            badge = badge_map.get(label, f"{label} risk")
            rec = rd.get("recommendation", "Check the latest official advisory before leaving shore.")
            if lang == "hi":
                sections.append(f"📊 **समग्र सुरक्षा आकलन**: {badge}। {rec}")
            elif lang == "ta":
                sections.append(f"📊 **ஒட்டுமொத்த பாதுகாப்பு**: {badge}. {rec}")
            else:
                sections.append(f"📊 **Overall Safety Assessment**: Rated **{badge}**. {rec}")

    if sections:
        header = f"Here is the assessment for **{loc_name}** covering your requested queries:\n\n" if lang == "en" else f"**{loc_name}** के लिए आपके सभी प्रश्नों की जानकारी:\n\n" if lang == "hi" else f"**{loc_name}** க்கான தகவல்:\n\n"
        return header + "\n\n".join(sections)
    else:
        return _render_template(lang, loc_name, "now", weather, pfz, hazard, None, risk, [])


def _render_hazard_response(
    lang: str,
    resolved: Optional[dict],
    hazard: Optional[AgentResult],
) -> str:
    loc_name = resolved.get("name", "monitored area") if resolved else "monitored area"
    p = _PHRASES.get(lang, _PHRASES["en"])
    lines = [f"⚠️ **Weather Condition Hazard Indicators — {loc_name}**\n"]
    if hazard and hazard.get("status") == "success" and hazard.get("data"):
        d = hazard["data"]
        active = d.get("active_warnings", [])
        level = d.get("overall_hazard_level", "none")
        if not active:
            lines.append(f"No active high-severity hazard was detected for {loc_name} in the available data. This does not guarantee absence of hazard.")
        else:
            lines.append(f"⚠️ **Hazard Level: {level.upper()}**")
            for h in d.get("hazards", []):
                lines.append(f"• **{h['title']}** ({h.get('severity', 'advisory')}): {h.get('detail', '')}")
        lines.append(f"\n*(Source: {hazard.get('source', 'IMD / Open-Meteo')})*")
        lines.append(f"\n{p['cyclone_note']}")
    else:
        lines.append("Live hazard warning data is currently unavailable for this location.")
    return "\n".join(lines)


def _validate_response(
    text: str,
    answer_plan: Optional[AnswerPlan],
    resolved: Optional[dict],
) -> tuple[bool, str]:
    """Lightweight response validator (Section 32, 33, 34)."""
    if not answer_plan:
        return True, "OK"

    intent = answer_plan.get("intent", "")
    text_lower = text.lower()

    # 0. Global safety and presentation invariants (PRD §5.1, §8)
    unauthorized = [
        "proceed with standard safety precautions",
        "safe to proceed",
        "authorized to depart",
        "clear to depart",
        "safe to depart",
    ]
    if any(u in text_lower for u in unauthorized):
        return False, "DEPARTURE_AUTHORIZATION_LEAK"

    internal_leaks = [
        "weather_agent", "ocean_agent", "hazard_agent", "pfz_agent", "geofence_agent", "risk_agent",
        "execution_status", "data_quality", "points contribution", "pts contribution"
    ]
    if any(t in text_lower for t in internal_leaks):
        return False, "INTERNAL_TERM_LEAK"

    # 1. Location query validation: must not contain unprompted marine safety jargon
    if intent == "LOCATION_QUERY":
        banned = [
            "pfz", "chlorophyll", "composite score", "marine safety assessment",
            "high risk", "moderate risk", "extreme risk", "fishing assessment",
            "fishing potential", "imbl",
        ]
        if any(b in text_lower for b in banned):
            return False, "IRRELEVANT_CONTENT"

    # 2. Inland tide/water-level query: must not fabricate numbers or give fishing risk
    if intent in ("WATER_LEVEL_QUERY", "TIDE_QUERY") and resolved and not resolved.get("coastal"):
        banned = ["composite score", "risk score", "high risk", "moderate risk", "marine safety assessment"]
        if any(b in text_lower for b in banned):
            return False, "IRRELEVANT_CONTENT"

    # 3. Pure weather query: must not contain unprompted PFZ or fishing risk verdict
    if intent == "WEATHER_QUERY":
        banned = ["chlorophyll", "pfz proxy", "fishing potential indicator", "composite score", "overall risk assessment", "fishing assessment"]
        if any(b in text_lower for b in banned):
            return False, "IRRELEVANT_CONTENT"

    return True, "OK"


def _build_marine_snapshot(
    resolved: Optional[dict] = None,
    location_name: str = "Unknown",
    lat: float = 0.0,
    lon: float = 0.0,
    is_coastal: bool = True,
    weather: Optional[AgentResult] = None,
    ocean: Optional[AgentResult] = None,
    pfz: Optional[AgentResult] = None,
    sst: Optional[AgentResult] = None,
    hazard: Optional[AgentResult] = None,
    geofence: Optional[AgentResult] = None,
    risk: Optional[AgentResult] = None,
    evidence: list = None,
    overall_data_status: str = "live",
    change_summary: Optional[dict] = None,
) -> dict:
    """Constructs the canonical MarineSnapshot shared across all product surfaces (PRD §17)."""
    w_data = weather.get("data", {}) if weather and weather.get("status") == "success" else {}
    o_data = ocean.get("data", {}) if ocean and ocean.get("status") == "success" else {}
    p_data = pfz.get("data", {}) if pfz and pfz.get("status") == "success" else {}
    s_data = sst.get("data", {}) if sst and (sst.get("status") in ("success", "ok") or sst.get("execution_status") in ("success", "ok")) else {}
    h_data = hazard.get("data", {}) if hazard and hazard.get("status") == "success" else {}
    g_data = geofence.get("data", {}) if geofence and geofence.get("status") == "success" else {}
    r_data = risk.get("data", {}) if risk and risk.get("status") == "success" else {}

    now_iso = datetime.now(timezone.utc).isoformat()
    loc_name = (resolved.get("name") if resolved else None) or location_name
    latitude = (resolved.get("lat") if resolved else None) or lat
    longitude = (resolved.get("lon") if resolved else None) or lon
    coastal = resolved.get("coastal") if resolved and "coastal" in resolved else is_coastal

    return {
        "location": {
            "name": loc_name,
            "lat": latitude,
            "lon": longitude,
            "coastal": coastal,
            "state": resolved.get("state") if resolved else None,
            "district": resolved.get("district") if resolved else None,
        },
        "generated_at": now_iso,
        "weather": {
            "wave_height_m": w_data.get("wave_height_m"),
            "wind_speed_kmh": w_data.get("wind_speed_kmh"),
            "wind_direction_deg": w_data.get("wind_direction_deg"),
            "sea_state": w_data.get("sea_state", "slight"),
            "temperature_c": w_data.get("temperature_c") or w_data.get("air_temperature_c"),
            "pressure_msl_hpa": w_data.get("pressure_msl_hpa"),
            "source": weather.get("source", "Open-Meteo ERA5 / Live Marine") if weather else "Open-Meteo",
            "data_quality": weather.get("data_quality", "live") if weather else "unavailable",
            "timestamp": weather.get("timestamp", now_iso) if weather else "",
        },
        "ocean": {
            "water_level_m": o_data.get("water_level_m"),
            "current_phase": o_data.get("current_phase", "Normal"),
            "next_high_tide": o_data.get("next_high_tide"),
            "next_low_tide": o_data.get("next_low_tide"),
            "source": ocean.get("source", "INCOIS / Survey of India") if ocean else "INCOIS",
            "data_quality": ocean.get("data_quality", "live") if ocean else "unavailable",
            "timestamp": ocean.get("timestamp", now_iso) if ocean else "",
        },
        "pfz": {
            "zones": p_data.get("zones", []),
            "nearest_zone_km": p_data.get("nearest_zone_km"),
            "overall_productivity": p_data.get("overall_productivity", "moderate"),
            "source": pfz.get("source", "INCOIS Oceansat-2 (satellite proxy)") if pfz else "INCOIS Oceansat-2",
            "is_proxy": True,
            "dataset_date": p_data.get("dataset_date", "2026-09-14"),
            "data_quality": pfz.get("data_quality", "historical_proxy") if pfz else "unavailable",
            "disclaimer": "Proxy indicator based on satellite chlorophyll-a, not an official INCOIS PFZ advisory.",
        },
        "sst": {
            "sst_celsius": s_data.get("sst_celsius"),
            "sst_anomaly_c": s_data.get("sst_anomaly_c"),
            "observation_time": s_data.get("observation_time"),
            "source": sst.get("source", "INCOIS ERDDAP (NOAA AVHRR/AMSR SST)") if sst else "INCOIS ERDDAP",
            "data_status": sst.get("data_status", sst.get("data_quality", "live")) if sst else "unavailable",
            "disclaimer": "Sea surface temperature (SST) and thermal anomalies indicate ocean surface temperature trends only and do not guarantee fish presence.",
        },
        "hazards": {
            "overall_hazard_level": h_data.get("overall_hazard_level", "none"),
            "active_warnings": h_data.get("active_warnings", []),
            "hazards": h_data.get("hazards", []),
            "source": hazard.get("source", "Current Weather Advisory / IMD") if hazard else "Weather Advisory",
            "checked_at": hazard.get("timestamp", now_iso) if hazard else now_iso,
            "data_quality": hazard.get("data_quality", "live") if hazard else "unavailable",
        },
        "geofence": {
            "imbl_distance_km": g_data.get("imbl_distance_km"),
            "boundary_risk": g_data.get("boundary_risk", "low"),
            "source": geofence.get("source", "Tarang Geofence Engine") if geofence else "Tarang Geofence Engine",
        },
        "risk": {
            "composite_score": r_data.get("composite_score"),
            "risk_label": r_data.get("risk_label", "UNKNOWN"),
            "final_level": r_data.get("risk_label", "UNKNOWN"),
            "components": r_data.get("components", []),
            "recommendation": r_data.get("recommendation", ""),
            "override_reason": r_data.get("override_reason"),
            "top_factor": r_data.get("components", [{}])[0].get("label") if r_data.get("components") else None,
        },
        "data_quality": {
            "overall_status": overall_data_status,
        },
        "evidence": evidence,
        "change_summary": change_summary,
    }


def _render_risk_explanation_response(
    lang: str,
    raw_query: str,
    intent_subtype: Optional[str],
    resolved: Optional[dict],
    risk: Optional[AgentResult],
    hazard: Optional[AgentResult],
    weather: Optional[AgentResult],
    change_summary: Optional[dict],
    risk_explanation_data: Optional[dict],
    previous_marine_assessment: Optional[dict],
) -> str:
    """Synthesize plain-language explanation for fine-grained sub-intents (PRD §6, §9, §10)."""
    loc_name = (resolved.get("name") if resolved else None) or "your coastal area"
    rd = (risk.get("data") if risk and risk.get("status") == "success" else None) or previous_marine_assessment or {}
    label = rd.get("risk_label", "LOW")
    score = rd.get("composite_score", 0.0)
    components = rd.get("components", [])
    top_comp = components[0].get("label", "sea conditions") if components else "sea conditions"

    active_warnings = (hazard.get("data") or {}).get("active_warnings", []) if hazard else []
    if not active_warnings and rd.get("inputs", {}).get("active_warnings"):
        active_warnings = rd["inputs"]["active_warnings"]

    subtype = intent_subtype or "WHY_THIS_RISK"

    # Sub-intent 1: COMPARE_WITH_PREVIOUS (PRD §10)
    if subtype == "COMPARE_WITH_PREVIOUS":
        if change_summary and change_summary.get("has_changes"):
            lines = ["📊 **Changed Since Your Last Check**\n"]
            for ch in change_summary.get("changes", []):
                lines.append(f"• **{ch['factor']}**: {ch['from']} → {ch['to']}")
            lines.append(f"\nOverall Risk: **{change_summary.get('previous_risk')}** → **{change_summary.get('current_risk')}**")
            return "\n".join(lines)
        else:
            return f"Conditions near **{loc_name}** are unchanged since your previous check. Wave height, wind, and hazard levels have remained steady at **{label} Risk**."

    # Sub-intent 2: WHAT_DOES_THIS_LEVEL_MEAN (PRD §6)
    if subtype == "WHAT_DOES_THIS_LEVEL_MEAN":
        raw_lower = raw_query.lower()
        if "didn't ask" in raw_lower or "didnt ask" in raw_lower or "i didn't" in raw_lower or "what do you mean" in raw_lower:
            return (
                f"Tarang evaluated conditions near **{loc_name}** as **{label} Risk** to provide automatic marine safety context for this coastline, not because you asked for departure clearance. "
                f"You can ask me about weather, wave heights, tides, or fishing indicators anytime."
            )
        else:
            return (
                f"**{label} Risk** means Tarang is detecting conditions that make venturing out to sea unsafe or unsuitable right now. "
                f"Always consult official advisories from IMD and local port authorities before planning a trip."
            )

    # Sub-intent 3: HAZARD_IMPACT (PRD §6)
    if subtype == "HAZARD_IMPACT":
        if active_warnings:
            warn_str = ", ".join(active_warnings)
            return (
                f"An active **{warn_str}** warning is present for **{loc_name}**. "
                f"In Tarang's safety engine, active severe weather warnings act as an automatic override that elevates risk to protect small craft, even if surface wind and waves are moderate."
            )
        else:
            return f"No severe weather warnings are active for **{loc_name}**, so hazard alerts are not currently elevating the risk score."

    # Sub-intent 4: WHAT_CAUSED_THIS_RISK (PRD §6)
    if subtype == "WHAT_CAUSED_THIS_RISK":
        lines = [f"Here are the primary factors contributing to the **{label} Risk** rating for **{loc_name}**:\n"]
        for comp in components:
            lines.append(f"• **{comp.get('label')}**: measured at {comp.get('raw_value')} {comp.get('raw_unit')} (contribution: {comp.get('contribution', 0.0):.1f} pts)")
        lines.append(f"\nTotal decision score: **{score:.1f}/100** ({label}).")
        return "\n".join(lines)

    # Sub-intent 5: WHY_THIS_RISK (default)
    factor_lines = []
    if components:
        factor_lines.append("\n\nHere is a breakdown of how Tarang calculated the risk score:")
        for comp in components:
            raw_val = comp.get("raw_value")
            raw_unit = comp.get("raw_unit", "")
            comp_score = comp.get("score", 0.0)
            weight_pct = comp.get("weight", 0.25) * 100
            contrib = comp.get("contribution", 0.0)
            lbl = comp.get("label", "")
            factor_lines.append(f"• **{lbl}** — measured at **{raw_val} {raw_unit}** → component score {comp_score:.0f}/100 × weight {weight_pct:.0f}% = **{contrib:.1f}** points contribution")

    factors_str = "\n".join(factor_lines) if factor_lines else ""

    if active_warnings:
        warn_str = ", ".join(active_warnings)
        return (
            f"The risk is **{label}** mainly because an active **{warn_str}** warning is present near **{loc_name}**. "
            f"Even though current wind and waves are moderate, the warning increases the overall risk and makes conditions unsuitable for departure.{factors_str}"
        )
    elif label == "LOW":
        return f"The risk is **LOW** near **{loc_name}** because the sea is fairly calm right now. Waves are small, wind is light, and no major hazard warning is active.{factors_str}"
    else:
        return f"The risk is **{label}** near **{loc_name}** mainly due to {top_comp.lower()}. Monitor official local advisories before leaving shore.{factors_str}"


# ---------------------------------------------------------------------------
# Location clarification fallback for synthesis early-exit
# ---------------------------------------------------------------------------

def _get_location_clarification_fallback(lang: str) -> str:
    """Return clarification text when synthesis is reached with no resolved location."""
    if lang == "hi":
        return "कृपया बताएं कि आप किस तटीय क्षेत्र या बंदरगाह के पास मछली पकड़ने की योजना बना रहे हैं (जैसे कोच्चि, रामेश्वरम, मुंबई, या विशाखापट्टनम), ताकि मैं सही जानकारी दे सकूँ।"
    elif lang == "ta":
        return "நீங்கள் எந்த கடலோரப் பகுதி அல்லது துறைமுகத்தில் மீன்பிடிக்கத் திட்டமிட்டுள்ளீர்கள் என்று குறிப்பிடவும் (எ.கா. கொச்சி, ராமேஸ்வரம், மும்பை)."
    else:
        return "Please specify which coastal area or harbour you are asking about (e.g. Kochi, Rameswaram, Mumbai, or Visakhapatnam) so I can provide accurate information."


# ---------------------------------------------------------------------------
# Public node function (LLM Path - Milestone 6 & PRD §3)
# ---------------------------------------------------------------------------

def synthesis(state: ORCAState) -> dict:
    """
    LangGraph node: universal final synthesis gate (PRD §3, §4).
    Assembles the canonical MarineSnapshot and produces the final user-facing text.
    """
    lang = state.get("detected_language", "en")
    intent = state.get("parsed_intent")
    answer_plan = state.get("answer_plan") or (intent.get("answer_plan") if intent else None)
    intent_name = (answer_plan.get("intent") if answer_plan else None) or (intent.get("intent") if intent else None) or "MARINE_SAFETY_QUERY"
    intent_subtype = (answer_plan.get("intent_subtype") if answer_plan else None) or (intent.get("intent_subtype") if intent else None) or state.get("intent_subtype")
    response_mode = (answer_plan.get("answer_type") if answer_plan else None) or state.get("response_mode") or "DECISION_ASSESSMENT"
    raw_query = state.get("raw_query", "").strip()
    resolved = state.get("resolved_location")
    req_id = state.get("request_id", "")
    conv_id = state.get("conversation_id", "")

    location = (resolved.get("name") if resolved else None) or (intent.get("location_name") if intent else None) or "the requested location"
    lat = (resolved["lat"] if resolved else None) or (intent.get("lat") if intent else None) or 8.7642
    lon = (resolved["lon"] if resolved else None) or (intent.get("lon") if intent else None) or 78.1348
    is_coastal = resolved.get("coastal", True) if resolved else True
    area_type = "coastal" if is_coastal else "inland"

    weather = state.get("weather_result")
    pfz = state.get("pfz_result")
    sst = state.get("sst_result")
    ocean = state.get("ocean_result")
    hazard = state.get("hazard_result")
    geofence = state.get("geofence_result")
    risk = state.get("risk_result")
    evidence = state.get("evidence") or []
    change_summary = state.get("change_summary")

    map_geojson = _build_geojson(
        intent_lat=lat,
        intent_lon=lon,
        location_name=location,
        pfz=pfz,
        geofence=geofence,
        risk=risk,
    )

    marine_snapshot = _build_marine_snapshot(
        resolved=resolved,
        location_name=location,
        lat=lat,
        lon=lon,
        is_coastal=is_coastal,
        weather=weather,
        ocean=ocean,
        pfz=pfz,
        sst=sst,
        hazard=hazard,
        geofence=geofence,
        risk=risk,
        evidence=evidence,
        overall_data_status=state.get("overall_data_status", "live"),
        change_summary=change_summary,
    )

    # 1. Final LLM Input Contract & Structured Logging (PRD §4)
    final_synthesis_input = {
        "user_query": raw_query,
        "intent": intent_name,
        "intent_subtype": intent_subtype,
        "response_mode": response_mode,
        "resolved_location": resolved,
        "conversation_context": {
            "history_turns": len(state.get("conversation_history") or []),
            "last_intent": (state.get("last_parsed_intent") or {}).get("intent"),
            "last_location": (state.get("last_parsed_intent") or {}).get("location_name"),
        },
        "previous_relevant_result": state.get("previous_marine_assessment") or (state.get("last_results") or {}).get("risk_agent", {}).get("data"),
        "answer_plan": answer_plan,
        "agent_results": {
            "weather": weather.get("data") if weather and weather.get("status") == "success" else None,
            "ocean": ocean.get("data") if ocean and ocean.get("status") == "success" else None,
            "pfz": pfz.get("data") if pfz and pfz.get("status") == "success" else None,
            "hazard": hazard.get("data") if hazard and hazard.get("status") == "success" else None,
            "geofence": geofence.get("data") if geofence and geofence.get("status") == "success" else None,
            "risk": risk.get("data") if risk and risk.get("status") == "success" else None,
        },
        "data_quality": {
            "overall_status": state.get("overall_data_status", "live"),
            "reports": state.get("data_quality_reports", []),
        }
    }

    executed_agents = [r.get("agent_name") for r in (state.get("trace") or []) if r.get("status") == "success"]
    logger.info(
        f"\nFINAL_SYNTHESIS_INPUT\n"
        f"---------------------\n"
        f"request_id: {req_id}\n"
        f"conversation_id: {conv_id}\n"
        f"user_query: {raw_query!r}\n"
        f"intent: {intent_name}\n"
        f"resolved_location: {resolved.get('name') if resolved else 'None'}\n"
        f"context_reference: {bool(final_synthesis_input['previous_relevant_result'])}\n"
        f"answer_plan: {answer_plan.get('answer_type') if answer_plan else 'None'}\n"
        f"executed_agents: {executed_agents}\n"
        f"data_status: {state.get('overall_data_status', 'live')}"
    )

    # 2. Early-Exit for Conversational Guidance / Message Quality Gate (PRD §5.1)
    if intent_name == "CONVERSATIONAL_GUIDANCE" or state.get("message_quality") in ("EMPTY", "AMBIGUOUS", "ACKNOWLEDGEMENT"):
        guidance_text = state.get("final_answer_text")
        if not guidance_text:
            guidance_text = "What would you like to know? You can ask about weather, sea conditions, fishing indicators, tides, hazards, or trip safety."
        return {
            "final_answer_text": guidance_text,
            "map_geojson": map_geojson,
            "marine_snapshot": marine_snapshot,
            "synthesis_method": "direct_fact",
        }

    # 2b. Early-Exit for ClarificationCard / CLARIFICATION mode (unresolved location)
    _answer_type = answer_plan.get("answer_type") if answer_plan else None
    _response_mode = state.get("response_mode") or (intent.get("response_mode") if intent else None)
    if _answer_type == "ClarificationCard" or _response_mode == "CLARIFICATION":
        clarification_text = state.get("final_answer_text")
        if not clarification_text:
            clarification_text = _get_location_clarification_fallback(lang)
        return {
            "final_answer_text": clarification_text,
            "map_geojson": map_geojson,
            "marine_snapshot": marine_snapshot,
            "synthesis_method": "direct_fact",
        }

    # 3. Direct Location Queries (PRD §7, §8)
    if intent_name == "LOCATION_QUERY":
        loc_text = state.get("final_answer_text") or _render_location_response(lang, resolved)
        return {
            "final_answer_text": loc_text,
            "map_geojson": map_geojson,
            "marine_snapshot": marine_snapshot,
            "synthesis_method": "direct_fact",
        }

    # 4. Inapplicability Notice (e.g. Inland water level/tide/PFZ)
    if state.get("response_mode") == "APPLICABILITY_EXPLANATION" or (intent and intent.get("response_mode") == "APPLICABILITY_EXPLANATION"):
        app_text = state.get("final_answer_text")
        if app_text:
            return {
                "final_answer_text": app_text,
                "map_geojson": map_geojson,
                "marine_snapshot": marine_snapshot,
                "synthesis_method": "applicability",
            }

    # 5. Risk Explanation Queries with Sub-intents (PRD §6)
    if intent_name == "RISK_EXPLANATION" or (intent and intent.get("query_type") == "risk_explanation"):
        explanation_text = _render_risk_explanation_response(
            lang=lang,
            raw_query=raw_query,
            intent_subtype=intent_subtype,
            resolved=resolved,
            risk=risk,
            hazard=hazard,
            weather=weather,
            change_summary=change_summary,
            risk_explanation_data=state.get("risk_explanation_data"),
            previous_marine_assessment=state.get("previous_marine_assessment"),
        )
        return {
            "final_answer_text": explanation_text,
            "map_geojson": map_geojson,
            "marine_snapshot": marine_snapshot,
            "synthesis_method": "llm",
        }

    location = (resolved.get("name") if resolved else None) or (intent.get("location_name") if intent else "the requested location") or "the requested location"
    lat = (resolved["lat"] if resolved else None) or (intent.get("lat") if intent else None) or 8.7642
    lon = (resolved["lon"] if resolved else None) or (intent.get("lon") if intent else None) or 78.1348
    is_coastal = resolved.get("coastal", True) if resolved else True
    area_type = "coastal" if is_coastal else "inland"

    weather = state.get("weather_result")
    pfz = state.get("pfz_result")
    ocean = state.get("ocean_result")
    hazard = state.get("hazard_result")
    geofence = state.get("geofence_result")
    risk = state.get("risk_result")
    evidence = state.get("evidence") or []

    map_geojson = _build_geojson(
        intent_lat=lat,
        intent_lon=lon,
        location_name=location,
        pfz=pfz,
        geofence=geofence,
        risk=risk,
    )

    if not config.GROQ_API_KEY:
        logger.warning("GROQ_API_KEY not set. Falling back to intent-aware template synthesis.")
        fallback_res = _fallback_synthesis(state)
        fallback_res["map_geojson"] = map_geojson
        fallback_res["marine_snapshot"] = marine_snapshot
        fallback_res["synthesis_method"] = "template_fallback"
        return fallback_res

    # Prepare selective evidence context for LLM based on AnswerPlan (Section 44)
    req_caps = answer_plan.get("required_capabilities", []) if answer_plan else []
    evidence_payload: dict = {}
    if not req_caps or "weather" in req_caps:
        evidence_payload["weather"] = weather.get("data") if weather and weather.get("status") == "success" else None
    if not req_caps or "ocean" in req_caps:
        evidence_payload["ocean_tides"] = ocean.get("data") if ocean and ocean.get("status") == "success" else None
    if not req_caps or "pfz" in req_caps:
        evidence_payload["pfz"] = pfz.get("data") if pfz and pfz.get("status") == "success" else None
    if not req_caps or "hazard" in req_caps:
        evidence_payload["hazard"] = hazard.get("data") if hazard and hazard.get("status") == "success" else None
    if not req_caps or "geofence" in req_caps:
        evidence_payload["geofence"] = geofence.get("data") if geofence and geofence.get("status") == "success" else None
    if not req_caps or "risk" in req_caps:
        evidence_payload["risk_components"] = risk.get("data", {}).get("components") if risk and risk.get("status") == "success" else None
        evidence_payload["risk_score"] = risk.get("data", {}).get("composite_score") if risk and risk.get("status") == "success" else None
        evidence_payload["risk_label"] = risk.get("data", {}).get("risk_label") if risk and risk.get("status") == "success" else None

    evidence_str = json.dumps(evidence_payload, indent=2)

    # Note if any fallback data was used
    data_quality_notes = []
    for agent_name, res in [("weather", weather), ("pfz", pfz), ("hazard", hazard)]:
        if res and res.get("status") == "success":
            dq = res.get("data_quality", "live")
            if dq == "fallback":
                data_quality_notes.append(f"{agent_name.capitalize()} agent used cached fallback data.")
            elif dq == "historical_proxy":
                data_quality_notes.append(f"{agent_name.capitalize()} agent used historical proxy data.")

    dq_str = " ".join(data_quality_notes) if data_quality_notes else "All data is live."

    # Intent-driven synthesis prompt (Sections 15, 31, 44, 45)
    system_template = """You are Tarang, an intelligent coastal & marine assistant for fishermen.
Current User Query: {raw_query}
Current Intent: {intent_name}
Response Mode: {response_mode}
Location: {location} (Coordinates: {lat:.2f}°N, {lon:.2f}°E, Area: {area_type})
Answer Plan: {answer_plan_str}

USER-FACING RESPONSE POLICY (PRD §5.1, §8, §16, §19):
1. Answer the user's actual question first.
2. Use simple everyday language. Keep the main answer short: prefer 2–5 short sentences. Target: 1 idea per sentence.
3. Mention only the information relevant to the current question. Convert technical measurements into understandable meaning:
   - Prefer 'Wave height' over 'Significant wave height'
   - Prefer 'Risk level' over 'Composite decision-support score'
   - Prefer 'Air pressure' over 'Atmospheric surface pressure'
   - Prefer 'Tide prediction' over 'Harmonic tidal prediction'
   - Prefer 'Distance from boundary' over 'Geofence proximity'
   - Prefer 'Satellite fishing indicator' over 'Chlorophyll-a concentration'
   - Prefer 'Data available' over 'Evidence coverage'
   - Prefer 'No major hazard detected' over 'Hazard level 0/100'
   - Prefer 'Check the latest warning before leaving' over 'Execute standard precautions'
   - Prefer 'Conditions are currently calm' over 'Current conditions appear manageable'
4. Do not expose internal risk formulas, weights, contribution points, agent names, state fields, JSON, execution details, cache internals, or implementation terminology.
5. Do not repeat every available data point. Detailed numeric evidence belongs in UI details cards, not the primary answer.
6. Tarang NEVER authorizes departure. Do not say 'proceed with standard safety precautions' or 'safe to depart'.
   - Low risk: 'Conditions are currently rated low risk by Tarang. Check the latest official advisory before leaving shore.'
   - Caution: 'Conditions need caution. Check the latest advisory and sea conditions before leaving shore.'
   - High risk: 'Conditions are risky right now. Avoid going out until conditions improve and official advisories allow it.'
   - Unknown: 'Tarang does not have enough reliable data to assess the trip safely right now; conditions are currently unknown and critical data is unavailable.'
7. If MULTI_INTENT: You MUST answer EVERY question and topic asked in the compound query. For each topic asked (e.g. sea level/tide, fishing potential/PFZ, hazards, weather/wind speed, safety risk), provide a clear, factual summary from the JSON Evidence directly so that all user questions are answered completely.
8. If the intent is LOCATION_QUERY: provide a concise, direct answer stating the user's current location and coordinates. Do NOT mention marine safety, PFZ, or tides.
9. If the intent is WEATHER_QUERY or SEA_LEVEL_PRESSURE_QUERY: summarize temperature, wind, and conditions for {location} in 2-3 short sentences. Do NOT mention PFZ, tides, or fishing risk.
10. If the intent is TIDE_QUERY or WATER_LEVEL_QUERY:
    - For coastal locations: summarize water level above Chart Datum and whether the tide is rising or falling in 2 short sentences.
    - For inland locations: explain that local coastal tide/water level measurements are not applicable to inland {location}, and suggest coastal harbours (e.g. Mumbai, Kochi, Chennai, Visakhapatnam).
11. If the intent is PFZ_QUERY: refer to it as 'Fishing Potential Indicator' (satellite chlorophyll proxy), never an 'official PFZ advisory'. State distance and note that satellite data does not guarantee fish.
12. If cached data was used (e.g. PFZ), state: 'Some fishing-zone data is from the latest available dataset rather than live data.'
13. NEVER state a numeric value that is not present in the provided evidence or location coordinates.
14. The response must be in the {lang} language.

JSON Evidence:
{evidence_str}
"""

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_template),
        ("user", f"Answer this query directly: {raw_query}")
    ])

    llm = ChatGroq(
        model=config.GROQ_MODEL_QUALITY,
        api_key=config.GROQ_API_KEY,
        temperature=0.2,
        max_retries=0,
        timeout=10.0
    )
    chain = prompt | llm

    LANG_NAMES = {
        "en": "English",
        "hi": "Hindi",
        "ta": "Tamil",
        "gu": "Gujarati",
        "bn": "Bengali",
        "te": "Telugu",
        "ml": "Malayalam",
        "mr": "Marathi",
        "od": "Odia",
        "or": "Odia",
    }
    lang_name = LANG_NAMES.get(lang, "English")

    try:
        res = chain.invoke({
            "raw_query": raw_query,
            "intent_name": intent_name,
            "response_mode": response_mode,
            "location": location,
            "lat": lat,
            "lon": lon,
            "area_type": area_type,
            "answer_plan_str": json.dumps(answer_plan, indent=2) if answer_plan else "None",
            "lang": lang_name,
            "dq_str": dq_str,
            "evidence_str": evidence_str,
        })
        output_text = res.content

        # Grounding check: include coordinates, query numbers, and standard constants
        output_nums = _extract_numbers(output_text)
        evidence_nums = _extract_numbers(evidence_str)
        if resolved:
            evidence_nums.update(_extract_numbers(json.dumps(resolved)))
            if "lat" in resolved and isinstance(resolved["lat"], (int, float)):
                evidence_nums.update({round(resolved["lat"], 2), round(resolved["lat"], 1), round(resolved["lat"], 3), float(int(resolved["lat"]))})
            if "lon" in resolved and isinstance(resolved["lon"], (int, float)):
                evidence_nums.update({round(resolved["lon"], 2), round(resolved["lon"], 1), round(resolved["lon"], 3), float(int(resolved["lon"]))})
        if intent:
            if intent.get("lat") and isinstance(intent["lat"], (int, float)):
                evidence_nums.update({round(intent["lat"], 2), round(intent["lat"], 1), round(intent["lat"], 3), float(int(intent["lat"]))})
            if intent.get("lon") and isinstance(intent["lon"], (int, float)):
                evidence_nums.update({round(intent["lon"], 2), round(intent["lon"], 1), round(intent["lon"], 3), float(int(intent["lon"]))})
        evidence_nums.update(_extract_numbers(raw_query))
        now_utc = datetime.now(timezone.utc)
        safe_nums = {float(n) for n in range(32)} | {
            float(now_utc.year), float(now_utc.year - 1), float(now_utc.year + 1),
            float(now_utc.month), float(now_utc.day),
            0.5, 1.5, 2.5, 3.5, 4.5, 5.5, 6.5, 7.5, 8.5, 9.5,
            48.0, 72.0, 100.0, 300.0, 500.0, 1000.0, 1013.25
        }
        ungrounded = output_nums - evidence_nums - safe_nums

        if ungrounded:
            logger.warning(f"Numeric grounding check failed. Ungrounded numbers: {ungrounded}. Falling back to template.")
            fallback_res = _fallback_synthesis(state)
            fallback_res["map_geojson"] = map_geojson
            fallback_res["marine_snapshot"] = marine_snapshot
            fallback_res["synthesis_method"] = "template_fallback"
            return fallback_res

        # Lightweight Response Validation Layer (Sections 32-34)
        is_valid, reason = _validate_response(output_text, answer_plan, resolved)
        if not is_valid:
            logger.warning(f"Response validation failed ({reason}). Falling back to intent template.")
            fallback_res = _fallback_synthesis(state)
            fallback_res["map_geojson"] = map_geojson
            fallback_res["marine_snapshot"] = marine_snapshot
            fallback_res["synthesis_method"] = "template_fallback"
            return fallback_res

        return {
            "final_answer_text": output_text,
            "map_geojson": map_geojson,
            "marine_snapshot": marine_snapshot,
            "synthesis_method": "llm",
        }
    except Exception as exc:
        logger.warning(f"Groq synthesis failed ({exc}), falling back to template synthesis.")
        fallback_res = _fallback_synthesis(state)
        fallback_res["map_geojson"] = map_geojson
        fallback_res["marine_snapshot"] = marine_snapshot
        fallback_res["synthesis_method"] = "template_fallback"
        return fallback_res


# ---------------------------------------------------------------------------
# Fallback template-based synthesis (Intent-aware)
# ---------------------------------------------------------------------------

def _fallback_synthesis(state: ORCAState) -> dict:
    """
    Fallback LangGraph node: fuse agent results into a cited natural-language
    answer using intent-specific templates (Section 16, 17).
    """
    lang = state.get("detected_language", "en")
    intent = state.get("parsed_intent")
    answer_plan = state.get("answer_plan") or (intent.get("answer_plan") if intent else None)
    intent_name = (answer_plan.get("intent") if answer_plan else None) or (intent.get("intent") if intent else None) or "MARINE_SAFETY_QUERY"
    resolved = state.get("resolved_location")

    time_window = intent.get("time_window", "next_24h") if intent else "next_24h"
    weather = state.get("weather_result")
    pfz = state.get("pfz_result")
    sst = state.get("sst_result")
    ocean = state.get("ocean_result")
    hazard = state.get("hazard_result")
    geofence = state.get("geofence_result")
    risk = state.get("risk_result")
    evidence = state.get("evidence") or []
    change_summary = state.get("change_summary")

    snap = _build_marine_snapshot(
        resolved=resolved,
        weather=weather,
        ocean=ocean,
        pfz=pfz,
        sst=sst,
        hazard=hazard,
        geofence=geofence,
        risk=risk,
        evidence=evidence,
        overall_data_status=state.get("overall_data_status", "live"),
        change_summary=change_summary,
    )

    # Early exit if final text is already produced
    existing_answer = state.get("final_answer_text", "")
    if existing_answer:
        return {"final_answer_text": existing_answer, "marine_snapshot": snap}

    if intent_name == "LOCATION_QUERY":
        answer_text = _render_location_response(lang, resolved)
    elif intent_name in ("WATER_LEVEL_QUERY", "TIDE_QUERY"):
        if resolved and not resolved.get("coastal", False):
            answer_text = _render_inland_ocean_applicability(lang, resolved)
        else:
            answer_text = _render_ocean_response(lang, resolved, ocean)
    elif intent_name == "SEA_LEVEL_PRESSURE_QUERY":
        answer_text = _render_pressure_response(lang, resolved, weather)
    elif intent_name == "WEATHER_QUERY":
        answer_text = _render_weather_response(lang, resolved, time_window, weather)
    elif intent_name == "PFZ_QUERY":
        answer_text = _render_pfz_response(lang, resolved, pfz)
    elif intent_name == "SST_QUERY":
        answer_text = _render_sst_response(lang, resolved, sst)
    elif intent_name == "HAZARD_QUERY":
        answer_text = _render_hazard_response(lang, resolved, hazard)
    elif intent_name == "RISK_EXPLANATION":
        answer_text = _render_risk_explanation_response(
            lang=lang,
            raw_query=state.get("raw_query", ""),
            intent_subtype=state.get("intent_subtype") or (intent.get("intent_subtype") if intent else "WHY_THIS_RISK"),
            resolved=resolved,
            risk=risk,
            hazard=hazard,
            weather=weather,
            change_summary=change_summary,
            risk_explanation_data=state.get("risk_explanation_data"),
            previous_marine_assessment=state.get("previous_marine_assessment"),
        )
    elif intent_name == "MULTI_INTENT":
        groups = (answer_plan.get("intent_groups") if answer_plan else None) or (intent.get("intent_groups") if intent else None)
        answer_text = _render_multi_intent_response(lang, resolved, groups, weather, ocean, pfz, hazard, risk)
    else:
        answer_text = _render_template(
            lang=lang,
            location=resolved.get("name", "the requested location") if resolved else "the requested location",
            time_window=time_window,
            weather=weather,
            pfz=pfz,
            hazard=hazard,
            geofence=geofence,
            risk=risk,
            evidence=evidence,
            ocean=ocean,
        )

    return {
        "final_answer_text": answer_text,
        "marine_snapshot": snap,
    }
