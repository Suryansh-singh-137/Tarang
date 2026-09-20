"use client";

import React, { useEffect, useRef, useState } from "react";
import { LanguageCode } from "@/lib/types";
import { translations } from "@/lib/i18n";

interface Props {
  language: LanguageCode;
  className?: string;
}

interface FeatureItem {
  num: string;
  index: number;
  title: string;
  body: string;
}

interface FeaturesData {
  row1: FeatureItem[];
  row2: FeatureItem[];
}

const FEATURES_BY_LANG: Record<LanguageCode, FeaturesData> = {
  en: {
    row1: [
      {
        num: "01",
        index: 0,
        title: "Marine Weather",
        body: "Live wave height, wind speed, and visibility from Open-Meteo ERA5 reanalysis and ICON NWP forecasts. Sea state classification per WMO Douglas scale.",
      },
      {
        num: "02",
        index: 1,
        title: "Fishing Potential",
        body: "Chlorophyll-a based proxy zones from INCOIS Oceansat-2 satellite grid. Disclosed as historical scientific indicator, not a live official PFZ advisory.",
      },
      {
        num: "03",
        index: 2,
        title: "Hazard & Cyclone",
        body: "GDACS live tropical cyclone tracking alongside weather-code hazards. Real-time distance, wind speed, and alert level from UN disaster monitoring.",
      },
      {
        num: "04",
        index: 3,
        title: "Risk Scoring",
        body: "Deterministic, explainable composite scoring — weighted wave, wind, visibility, and cyclone proximity. No LLM in the safety-critical path.",
      },
    ],
    row2: [
      {
        num: "05",
        index: 4,
        title: "Multilingual, by voice",
        body: "Ask in English, Hindi, or Tamil — speak or type. Answers come back the same way, read aloud on request. Groq Whisper for transcription, Sarvam AI for synthesis.",
      },
      {
        num: "06",
        index: 5,
        title: "Every claim, sourced",
        body: "Answers cite the exact agent and data source behind every number — provenance tiers from official national (INCOIS/IMD) through global awareness (GDACS) to operational model (Open-Meteo). No fabricated claims, ever.",
      },
    ],
  },
  hi: {
    row1: [
      {
        num: "01",
        index: 0,
        title: "समुद्री मौसम",
        body: "Open-Meteo ERA5 और ICON पूर्वानुमानों से लाइव लहरों की ऊंचाई, हवा की गति और दृश्यता। WMO डगलस पैमाने के अनुसार समुद्र की स्थिति।",
      },
      {
        num: "02",
        index: 1,
        title: "मत्स्य पालन संभावना",
        body: "INCOIS Oceansat-2 उपग्रह ग्रिड से क्लोरोफिल-ए आधारित मछली क्षेत्र। वैज्ञानिक संकेतक के रूप में प्रदर्शित, आधिकारिक PFZ परामर्श नहीं।",
      },
      {
        num: "03",
        index: 2,
        title: "खतरा एवं चक्रवात",
        body: "GDACS लाइव चक्रवात ट्रैकिंग और मौसम संबंधी खतरे। संयुक्त राष्ट्र आपदा निगरानी से वास्तविक समय की दूरी, हवा की गति और चेतावनी स्तर।",
      },
      {
        num: "04",
        index: 3,
        title: "जोखिम स्कोरिंग",
        body: "पारदर्शी समग्र स्कोरिंग — लहरों, हवा, दृश्यता और चक्रवात की निकटता का वैज्ञानिक भार। सुरक्षा-संवेदनशील पथ में कोई अनुमान नहीं।",
      },
    ],
    row2: [
      {
        num: "05",
        index: 4,
        title: "बहुभाषी, आवाज द्वारा",
        body: "अपनी भाषा में बोलकर या लिखकर पूछें। उत्तर भी उसी तरह वापस मिलते हैं और आवाज में सुने जा सकते हैं। व्हिस्पर और सर्वम एआई द्वारा संचालित।",
      },
      {
        num: "06",
        index: 5,
        title: "प्रत्येक आंकड़े का स्रोत",
        body: "हर संख्या के पीछे सटीक स्रोत दर्ज है — राष्ट्रीय (INCOIS/IMD), वैश्विक (GDACS) और मौसम मॉडल (Open-Meteo)। शून्य असत्यापित दावे।",
      },
    ],
  },
  ta: {
    row1: [
      {
        num: "01",
        index: 0,
        title: "கடல்சார் வானிலை",
        body: "ஓபன்-மீடியோ ERA5 மற்றும் ICON முன்னறிவிப்புகள் மூலம் நேரலை அலை உயரம், காற்றின் வேகம் மற்றும் பார்வைத்திறன். WMO டக்ளஸ் அளவுகோல் வகைப்பாடு.",
      },
      {
        num: "02",
        index: 1,
        title: "மீன்பிடி சாத்தியக்கூறு",
        body: "INCOIS ஓசன்சாட்-2 செயற்கைக்கோள் தரவு அடிப்படையிலான மீன்பிடி பகுதிகள். அறிவியல் குறிகாட்டியாக வழங்கப்படுகிறது, அதிகாரப்பூர்வ ஆலோசனை அல்ல.",
      },
      {
        num: "03",
        index: 2,
        title: "ஆபத்து & புயல்",
        body: "GDACS நேரலை வெப்பமண்டல புயல் கண்காணிப்பு மற்றும் வானிலை அபாயங்கள். ஐ.நா பேரிடர் கண்காணிப்பிலிருந்து நிகழ்நேர தூரம் மற்றும் காற்று வேகம்.",
      },
      {
        num: "04",
        index: 3,
        title: "இடர் மதிப்பீடு",
        body: "தெளிவான கூட்டு மதிப்பெண் — அலைகள், காற்று, பார்வைத்திறன் மற்றும் புயல் அருகாமை ஆகியவற்றின் துல்லியமான அறிவியல் பகுப்பாய்வு.",
      },
    ],
    row2: [
      {
        num: "05",
        index: 4,
        title: "பன்மொழி, குரல் வழி",
        body: "உங்கள் தாய்மொழியில் பேசி அல்லது தட்டச்சு செய்து கேளுங்கள். பதில்கள் குரல் வழியே ஒலிக்கப்படும். விஸ்பர் மற்றும் சர்வம் AI மூலம் இயக்கப்படுகிறது.",
      },
      {
        num: "06",
        index: 5,
        title: "அனைத்து ஆதாரங்களும் தெளிவு",
        body: "ஒவ்வொரு பதிலுக்கும் பின்னணியில் உள்ள சரியான முகவர் மற்றும் தரவு மூலம் வெளிப்படையாகக் குறிப்பிடப்படுகிறது (INCOIS, GDACS, Open-Meteo).",
      },
    ],
  },
  gu: {
    row1: [
      {
        num: "01",
        index: 0,
        title: "દરિયાઈ હવામાન",
        body: "Open-Meteo ERA5 અને ICON પૂર્વાનુમાનોથી લાઈવ મોજાંની ઊંચાઈ, પવનની ઝડપ અને દૃશ્યતા. WMO ડગ્લાસ સ્કેલ મુજબ દરિયાની સ્થિતિનું વર્ગીકરણ.",
      },
      {
        num: "02",
        index: 1,
        title: "મત્સ્ય સંભાવના",
        body: "INCOIS ઓશન્સસેટ-૨ સેટેલાઇટ ગ્રીડ પરથી ક્લોરોફિલ-એ આધારિત મત્સ્ય ઝોન. વૈજ્ઞાનિક સંકેત તરીકે દર્શાવેલ, સત્તાવાર સલાહ નથી.",
      },
      {
        num: "03",
        index: 2,
        title: "જોખમ અને વાવાઝોડું",
        body: "GDACS લાઈવ ચક્રવાત ટ્રેકિંગ અને હવામાન જોખમો. સંયુક્ત રાષ્ટ્ર આપત્તિ દેખરેખ તરફથી વાસ્તવિક સમયનું અંતર, પવનની ગતિ અને એલર્ટ સ્તર.",
      },
      {
        num: "04",
        index: 3,
        title: "જોખમ મૂલ્યાંકન",
        body: "પારદર્શક સંયુક્ત સ્કોરિંગ — મોજાં, પવન, દૃશ્યતા અને વાવાઝોડાની નિકટતાનું વૈજ્ઞાનિક મૂલ્યાંકન. સુરક્ષા નિર્ણયોમાં કોઈ અસમંજસ નહીં.",
      },
    ],
    row2: [
      {
        num: "05",
        index: 4,
        title: "બહુભાષી, અવાજ દ્વારા",
        body: "ગુજરાતી કે તમારી ભાષામાં બોલીને અથવા લખીને પૂછો. જવાબો પણ અવાજમાં સાંભળી શકાય છે. વ્હીસ્પર અને સર્વમ AI દ્વારા સંચાલિત.",
      },
      {
        num: "06",
        index: 5,
        title: "દરેક આંકડાનો સ્ત્રોત",
        body: "દરેક સંખ્યા પાછળ સચોટ એજન્ટ અને ડેટા સ્ત્રોત દર્શાવેલ છે — રાષ્ટ્રીય (INCOIS/IMD), વૈશ્વિક (GDACS) અને ઓપન-મેટિઓ મોડલ.",
      },
    ],
  },
  bn: {
    row1: [
      {
        num: "01",
        index: 0,
        title: "সামুদ্রিক আবহাওয়া",
        body: "Open-Meteo ERA5 এবং ICON পূর্বাভাস থেকে রিয়েল-টাইম ঢেউয়ের উচ্চতা, বাতাসের গতি এবং দৃশ্যমানতা। WMO ডগলাস স্কেলে সমুদ্রের অবস্থা।",
      },
      {
        num: "02",
        index: 1,
        title: "মৎস্য সম্ভাবনা",
        body: "INCOIS Oceansat-2 স্যাটেলাইট গ্রিড থেকে ক্লোরোফিল-এ ভিত্তিক মাছের সম্ভাব্য অঞ্চল। বৈজ্ঞানিক সূচক হিসেবে প্রদর্শিত, সরকারি পরামর্শ নয়।",
      },
      {
        num: "03",
        index: 2,
        title: "বিপদ ও ঘূর্ণিঝড়",
        body: "GDACS রিয়েল-টাইম ঘূর্ণিঝড় ট্র্যাকিং এবং আবহাওয়ার বিপদ। জাতিসংঘের দুর্যোগ পর্যবেক্ষণ থেকে সরাসরি দূরত্ব, বাতাসের গতি ও সতর্কবার্তা।",
      },
      {
        num: "04",
        index: 3,
        title: "ঝুঁকি মূল্যায়ন",
        body: "স্বচ্ছ যৌথ ঝুঁকি স্কোরিং — ঢেউ, বাতাস, দৃশ্যমানতা এবং ঘূর্ণিঝড়ের নৈকট্যের নির্ভুল গাণিতিক হিসেব। নিরাপত্তা ক্ষেত্রে কোনো কাল্পনিক অনুমান নেই।",
      },
    ],
    row2: [
      {
        num: "05",
        index: 4,
        title: "বহুভাষিক, ভয়েস ইনপুট",
        body: "বাংলা বা আপনার পছন্দের ভাষায় মুখে বলুন বা লিখে জিজ্ঞাসা করুন। উত্তর কণ্ঠস্বরেও শোনা সম্ভব। হুইস্পার এবং সর্বম এআই চালিত।",
      },
      {
        num: "06",
        index: 5,
        title: "প্রতিটি তথ্যের সূত্র",
        body: "প্রতিটি সংখ্যার পেছনে সঠিক ডেটা উৎস ও এজেন্টের উল্লেখ থাকে — সরকারি জাতীয় (INCOIS/IMD), বৈশ্বিক (GDACS) ও আবহাওয়া মডেল (Open-Meteo)।",
      },
    ],
  },
  te: {
    row1: [
      {
        num: "01",
        index: 0,
        title: "సముద్ర వాతావరణం",
        body: "Open-Meteo ERA5 మరియు ICON సూచనల నుండి ప్రత్యక్ష అలల ఎత్తు, గాలి వేగం మరియు దృశ్యమానత. WMO డగ్లస్ స్కేలు ప్రకారం సముద్ర స్థితి వర్గీకరణ.",
      },
      {
        num: "02",
        index: 1,
        title: "చేపల వేట సంభావ్యత",
        body: "INCOIS ఓషన్శాట్-2 ఉపగ్రహ గ్రిడ్ నుండి క్లోరోఫిల్-ఎ ఆధారిత ప్రాక్సీ జోన్లు. శాస్త్రీయ సూచికగా మాత్రమే అందించబడుతుంది, అధికారిక సలహా కాదు.",
      },
      {
        num: "03",
        index: 2,
        title: "ప్రమాదం & తుఫాను",
        body: "GDACS ప్రత్యక్ష తుఫాను ట్రాకింగ్ మరియు వాతావరణ ప్రమాదాలు. ఐక్యరాజ్యసమితి విపత్తు పర్యవేక్షణ నుండి నిజ-సమయ దూరం, గాలి వేగం మరియు హెచ్చరిక స్థాయి.",
      },
      {
        num: "04",
        index: 3,
        title: "రిస్క్ స్కోరింగ్",
        body: "స్పష్టమైన మిశ్రమ స్కోరింగ్ — అలలు, గాలి, దృశ్యమానత మరియు తుఫాను సామీప్యత యొక్క సంఖ్యాత్మక భద్రతా విశ్లేషణ. ఊహాజనిత సమాధానాలకు తావులేదు.",
      },
    ],
    row2: [
      {
        num: "05",
        index: 4,
        title: "బహుభాషా, వాయిస్ ద్వారా",
        body: "తెలుగు లేదా మీ భాషలో మాట్లాడి లేదా రాసి అడగండి. సమాధానాలు మాటల రూపంలో కూడా వినవచ్చు. విస్పర్ మరియు సర్వం AI మద్దతుతో.",
      },
      {
        num: "06",
        index: 5,
        title: "ప్రతి అంశానికి ఆధారం",
        body: "ప్రతి సంఖ్య వెనుక ఉన్న నిర్దిష్ట ఏజెంట్ మరియు డేటా మూలాన్ని స్పష్టంగా పేర్కొంటుంది (INCOIS, GDACS, Open-Meteo). కల్పితాలు లేవు.",
      },
    ],
  },
  ml: {
    row1: [
      {
        num: "01",
        index: 0,
        title: "സമുദ്ര കാലാവസ്ഥ",
        body: "Open-Meteo ERA5, ICON പ്രവചനങ്ങളിൽ നിന്നുള്ള തത്സമയ തിരമാല ഉയരം, കാറ്റിന്റെ വേഗത, ദൃശ്യപരത. WMO ഡഗ്ലസ് സ്കെയിൽ പ്രകാരമുള്ള സമുദ്ര അവസ്ഥ.",
      },
      {
        num: "02",
        index: 1,
        title: "മത്സ്യലഭ്യത സാധ്യത",
        body: "INCOIS ഓഷ്യൻസാറ്റ്-2 ഉപഗ്രഹ ഡാറ്റയെ അടിസ്ഥാനമാക്കിയുള്ള മത്സ്യമേഖലകൾ. ഒരു ശാസ്ത്രീയ സൂചകമായി വെളിപ്പെടുത്തുന്നു, ഔദ്യോഗിക PFZ അല്ല.",
      },
      {
        num: "03",
        index: 2,
        title: "അപകടവും ചുഴലിക്കാറ്റും",
        body: "GDACS തത്സമയ ചുഴലിക്കാറ്റ് നിരീക്ഷണവും കാലാവസ്ഥാ മുന്നറിയിപ്പുകളും. യുഎൻ ദുരന്ത നിരീക്ഷണത്തിൽ നിന്നുള്ള ദൂരവും കാറ്റിന്റെ വേഗതയും മുന്നറിയിപ്പും.",
      },
      {
        num: "04",
        index: 3,
        title: "റിസ്ക് സ്കോറിംഗ്",
        body: "സുതാര്യമായ സുരക്ഷാ സ്കോറിംഗ് — തിരമാലകൾ, കാറ്റ്, കാഴ്ചാപരിധി, ചുഴലിക്കാറ്റിന്റെ സാമീപ്യം എന്നിവ കൃത്യമായി വിശകലനം ചെയ്യുന്നു.",
      },
    ],
    row2: [
      {
        num: "05",
        index: 4,
        title: "ബഹുഭാഷാ വോയ്‌സ് പിന്തുണ",
        body: "മലയാളത്തിലോ നിങ്ങളുടെ ഭാഷയിലോ സംസാരിച്ചോ എഴുതിയോ ചോദിക്കുക. ഉത്തരങ്ങൾ ശബ്ദരൂപത്തിലും കേൾക്കാം. വിസ്പർ, സർവം AI സാങ്കേതികവിദ്യ.",
      },
      {
        num: "06",
        index: 5,
        title: "എല്ലാ വിവരങ്ങൾക്കും ഉറവിടം",
        body: "ഓരോ നമ്പറിന് പിന്നിലും കൃത്യമായ ഏജന്റും ഡാറ്റ ഉറവിടവും വ്യക്തമാക്കുന്നു — ദേശീയ (INCOIS), ആഗോള (GDACS), മോഡൽ (Open-Meteo).",
      },
    ],
  },
  mr: {
    row1: [
      {
        num: "01",
        index: 0,
        title: "सागरी हवामान",
        body: "Open-Meteo ERA5 आणि ICON अंदाजानुसार थेट लाटांची उंची, वाऱ्याचा वेग आणि दृश्यमानता. WMO डगलास स्केलनुसार समुद्राच्या स्थितीचे वर्गीकरण.",
      },
      {
        num: "02",
        index: 1,
        title: "मासेमारी संभाव्यता",
        body: "INCOIS Oceansat-2 उपग्रह ग्रीडवरून क्लोरोफिल-ए आधारित मासेमारी क्षेत्रे. वैज्ञानिक निर्देशक म्हणून प्रदर्शित, अधिकृत PFZ सल्ला नाही.",
      },
      {
        num: "03",
        index: 2,
        title: "धोका आणि चक्रीवादळ",
        body: "GDACS थेट चक्रीवादळ ट्रॅकिंग आणि हवामान धोके. संयुक्त राष्ट्र आपत्ती निरीक्षणाकडून थेट अंतर, वाऱ्याचा वेग आणि सतर्कता पातळी.",
      },
      {
        num: "04",
        index: 3,
        title: "जोखिम मूल्यांकन",
        body: "पारदर्शक समग्र स्कोअरिंग — लाटा, वारा, दृश्यमानता आणि चक्रीवादळ निकटाचे वैज्ञानिक वजन. सुरक्षा निर्णयात कोणताही अंदाज नाही.",
      },
    ],
    row2: [
      {
        num: "05",
        index: 4,
        title: "बहुभाषिक, आवाजाद्वारे",
        body: "मराठी किंवा तुमच्या भाषेत बोलून किंवा लिहून विचारा. उत्तरे आवाजात ऐकण्याची सोय उपलब्ध. व्हिस्पर आणि सर्वम AI द्वारे समर्थित.",
      },
      {
        num: "06",
        index: 5,
        title: "प्रत्येक दाव्याचा स्रोत",
        body: "प्रत्येक आकड्यामागे अचूक एजंट आणि डेटा स्रोत नोंदवला आहे — राष्ट्रीय (INCOIS/IMD), जागतिक (GDACS) आणि मॉडेल (Open-Meteo).",
      },
    ],
  },
  od: {
    row1: [
      {
        num: "01",
        index: 0,
        title: "ସାମୁଦ୍ରିକ ପାଣିପାଗ",
        body: "Open-Meteo ERA5 ଏବଂ ICON ପୂର୍ବାନୁମାନରୁ ପ୍ରତ୍ୟକ୍ଷ ଢେଉର ଉଚ୍ଚତା, ପବନର ବେଗ ଏବଂ ଦୃଶ୍ୟମାନତା। WMO ଡଗଲାସ୍ ସ୍କେଲ୍ ଅନୁଯାୟୀ ସମୁଦ୍ର ସ୍ଥିତି।",
      },
      {
        num: "02",
        index: 1,
        title: "ମତ୍ସ୍ୟ ସମ୍ଭାବନା",
        body: "INCOIS Oceansat-2 ଉପଗ୍ରହ ଗ୍ରୀଡ୍‌ରୁ କ୍ଲୋରୋଫିଲ୍-ଏ ଆଧାରିତ ମାଛ ଧରିବା କ୍ଷେତ୍ର। ବୈଜ୍ଞାନିକ ସୂଚକ ଭାବରେ ପ୍ରଦର୍ଶିତ, ସରକାରୀ ପରାମର୍ଶ ନୁହେଁ।",
      },
      {
        num: "03",
        index: 2,
        title: "ବିପଦ ଓ ବାତ୍ୟା",
        body: "GDACS ପ୍ରତ୍ୟକ୍ଷ ବାତ୍ୟା ଟ୍ରାକିଂ ଏବଂ ପାଣିପାଗ ବିପଦ। ମିଳିତ ଜାତିସଂଘ ବିପର୍ଯ୍ୟୟ ନିରୀକ୍ଷଣରୁ ପ୍ରକୃତ ଦୂରତା, ପବନ ବେଗ ଓ ଚେତାବନୀ ସ୍ତର।",
      },
      {
        num: "04",
        index: 3,
        title: "ବିପଦ ସ୍କୋରିଂ",
        body: "ସ୍ପଷ୍ଟ ସାମଗ୍ରିକ ସ୍କୋରିଂ — ଢେଉ, ପବନ, ଦୃଶ୍ୟମାନତା ଏବଂ ବାତ୍ୟାର ନିକଟତା ଉପରେ ଆଧାରିତ। ସୁରକ୍ଷା ନିଷ୍ପତ୍ତିରେ କୌଣସି ଅଯଥା ଅନୁମାନ ନାହିଁ।",
      },
    ],
    row2: [
      {
        num: "05",
        index: 4,
        title: "ବହୁଭାଷୀ, ସ୍ୱର ଦ୍ୱାରା",
        body: "ଓଡ଼ିଆ କିମ୍ବା ନିଜ ଭାଷାରେ କହି ବା ଲେଖି ପଚାରନ୍ତୁ। ଉତ୍ତର ସ୍ୱରରେ ମଧ୍ୟ ଶୁଣିବା ସମ୍ଭବ। ହୁଇସ୍ପର ଏବଂ ସର୍ବମ AI ଦ୍ୱାରା ପରିଚାଳିତ।",
      },
      {
        num: "06",
        index: 5,
        title: "ପ୍ରତ୍ୟେକ ତଥ୍ୟର ଉତ୍ସ",
        body: "ପ୍ରତ୍ୟେକ ସଂଖ୍ୟା ପଛରେ ସଠିକ୍ ଏଜେଣ୍ଟ ଏବଂ ଡାଟା ଉତ୍ସ ପ୍ରଦାନ କରାଯାଇଛି — ସରକାରୀ (INCOIS/IMD), ବିଶ୍ୱସ୍ତରୀୟ (GDACS) ଓ ମଡେଲ (Open-Meteo)।",
      },
    ],
  },
};

export const FeaturesSection: React.FC<Props> = ({
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
      { threshold: 0.12 }
    );

    if (sectionRef.current) {
      observer.observe(sectionRef.current);
    }

    return () => observer.disconnect();
  }, []);

  const featureData = FEATURES_BY_LANG[language] || FEATURES_BY_LANG.en;

  return (
    <section ref={sectionRef} className={`py-16 sm:py-20 lg:py-24 ${className}`}>
      <div className="max-w-[1200px] mx-auto w-full px-6 sm:px-10 lg:px-16">

        {/* Section label — small mono, left-aligned */}
        <div
          className={`font-mono-data text-[11px] text-[var(--ink-muted)] tracking-widest uppercase mb-4 transition-all duration-500 ${
            isVisible ? "reveal-visible" : "reveal-init"
          }`}
        >
          {t.featuresEyebrow}
        </div>

        {/* Section intro — Fraunces, medium size */}
        <p
          className={`font-serif-display text-xl sm:text-2xl lg:text-3xl font-normal text-[var(--ink)] leading-snug max-w-[600px] mb-10 sm:mb-14 transition-all duration-500 delay-100 ${
            isVisible ? "reveal-visible" : "reveal-init"
          }`}
        >
          {t.featuresSub}
        </p>

        {/* ── Row 1: Four columns (unequal to row 2) ── */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-0 border-t border-[var(--border)]">
          {featureData.row1.map((feat) => (
            <div
              key={feat.num}
              style={{
                transitionDelay: isVisible ? `${feat.index * 75}ms` : "0ms",
              }}
              className={`py-6 sm:py-8 pr-6 lg:pr-8 border-b lg:border-b-0 lg:border-r border-[var(--border)] last:border-r-0 last:border-b-0 flex flex-col transition-all duration-500 ${
                isVisible ? "reveal-visible" : "reveal-init"
              }`}
            >
              {/* Micro-diagram & Number row */}
              <div className="flex items-center justify-between mb-4">
                <span className="font-mono-data text-[11px] text-[var(--ink-subtle)] tracking-widest block">
                  {feat.num}
                </span>
                <div className="w-8 h-8 flex items-center justify-center text-[var(--current)]" aria-hidden="true">
                  {feat.num === "01" && (
                    <svg width="32" height="32" viewBox="0 0 34 34" fill="none" xmlns="http://www.w3.org/2000/svg">
                      <path d="M4 19C7.5 15.5 11 15.5 14.5 19C18 22.5 21.5 22.5 25 19C27.5 16.5 29.5 16.5 30 17" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                      <path d="M4 25C7.5 21.5 11 21.5 14.5 25C18 28.5 21.5 28.5 25 25C27.5 22.5 29.5 22.5 30 23" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" opacity="0.35"/>
                      <path d="M9 11C13 9 19 9 24 11" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
                      <path d="M22 8L25 11L22 14" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                    </svg>
                  )}
                  {feat.num === "02" && (
                    <svg width="32" height="32" viewBox="0 0 34 34" fill="none" xmlns="http://www.w3.org/2000/svg">
                      <circle cx="17" cy="17" r="13" stroke="currentColor" strokeWidth="1.5" opacity="0.25"/>
                      <path d="M17 17L26 8" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
                      <circle cx="17" cy="17" r="2.5" fill="currentColor"/>
                      <circle cx="21" cy="12" r="1.5" fill="var(--dawn)"/>
                      <circle cx="13" cy="22" r="1.5" fill="currentColor"/>
                      <circle cx="23" cy="20" r="1.5" fill="currentColor" opacity="0.6"/>
                      <path d="M17 4A13 13 0 0 1 30 17" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
                    </svg>
                  )}
                  {feat.num === "03" && (
                    <svg width="32" height="32" viewBox="0 0 34 34" fill="none" xmlns="http://www.w3.org/2000/svg">
                      <circle cx="17" cy="17" r="13" stroke="currentColor" strokeWidth="1.5" strokeDasharray="3 3" opacity="0.35"/>
                      <circle cx="17" cy="17" r="7" stroke="currentColor" strokeWidth="1.5" opacity="0.6"/>
                      <path d="M17 7C14 7 12 9 12 12C12 17 22 17 22 22C22 25 20 27 17 27" stroke="var(--dawn)" strokeWidth="1.5" strokeLinecap="round"/>
                      <circle cx="17" cy="2" fill="var(--dawn)"/>
                    </svg>
                  )}
                  {feat.num === "04" && (
                    <svg width="32" height="32" viewBox="0 0 34 34" fill="none" xmlns="http://www.w3.org/2000/svg">
                      <path d="M6 24A13 13 0 1 1 28 24" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
                      <path d="M17 17L22 12" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
                      <circle cx="17" cy="17" r="2.5" fill="currentColor"/>
                      <line x1="6" y1="24" x2="8" y2="24" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
                      <line x1="17" y1="4" x2="17" y2="6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
                      <line x1="28" y1="24" x2="26" y2="24" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
                    </svg>
                  )}
                </div>
              </div>

              {/* Title — sans, semibold */}
              <h3 className="text-sm sm:text-base font-semibold text-[var(--ink)] mb-2">
                {feat.title}
              </h3>

              {/* Body — small, muted, specific copy */}
              <p className="text-xs sm:text-sm text-[var(--ink-muted)] leading-relaxed">
                {feat.body}
              </p>
            </div>
          ))}
        </div>

        {/* ── Row 2: Two wider columns — deliberately asymmetric vs row 1 ── */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-0 border-t border-[var(--border)] mt-0">
          {featureData.row2.map((feat) => (
            <div
              key={feat.num}
              style={{
                transitionDelay: isVisible ? `${feat.index * 75}ms` : "0ms",
              }}
              className={`py-6 sm:py-8 pr-6 lg:pr-12 border-b sm:border-b-0 sm:border-r border-[var(--border)] last:border-r-0 last:border-b-0 flex flex-col transition-all duration-500 ${
                isVisible ? "reveal-visible" : "reveal-init"
              }`}
            >
              {/* Micro-diagram & Number row */}
              <div className="flex items-center justify-between mb-4">
                <span className="font-mono-data text-[11px] text-[var(--ink-subtle)] tracking-widest block">
                  {feat.num}
                </span>
                <div className="w-8 h-8 flex items-center justify-center text-[var(--current)]" aria-hidden="true">
                  {feat.num === "05" && (
                    <svg width="32" height="32" viewBox="0 0 34 34" fill="none" xmlns="http://www.w3.org/2000/svg">
                      <path d="M5 9C5 6.79086 6.79086 5 9 5H21C23.2091 5 25 6.79086 25 9V17C25 19.2091 23.2091 21 21 21H13L7 26V21H9C6.79086 21 5 19.2091 5 17V9Z" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                      <path d="M11 13V13.01" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
                      <path d="M15 11V15" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
                      <path d="M19 12V14" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
                      <path d="M28 10C29.5 11.5 29.5 14.5 28 16" stroke="var(--dawn)" strokeWidth="1.5" strokeLinecap="round"/>
                    </svg>
                  )}
                  {feat.num === "06" && (
                    <svg width="32" height="32" viewBox="0 0 34 34" fill="none" xmlns="http://www.w3.org/2000/svg">
                      <circle cx="10" cy="11" r="3.5" stroke="currentColor" strokeWidth="1.5"/>
                      <circle cx="24" cy="11" r="3.5" stroke="currentColor" strokeWidth="1.5"/>
                      <circle cx="17" cy="23" r="3.5" stroke="currentColor" strokeWidth="1.5"/>
                      <path d="M13.5 11H20.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
                      <path d="M12 14L15 20" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
                      <path d="M22 14L19 20" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
                      <circle cx="17" cy="23" r="1" fill="var(--current)"/>
                    </svg>
                  )}
                </div>
              </div>

              {/* Title — sans, semibold */}
              <h3 className="text-sm sm:text-base font-semibold text-[var(--ink)] mb-2">
                {feat.title}
              </h3>

              {/* Body — small, muted, specific copy */}
              <p className="text-xs sm:text-sm text-[var(--ink-muted)] leading-relaxed">
                {feat.body}
              </p>
            </div>
          ))}
        </div>

      </div>
    </section>
  );
};
