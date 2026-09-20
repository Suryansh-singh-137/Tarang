"use client";

import React, { useEffect, useRef, useState } from "react";
import { Layers, Fish, AlertTriangle, Maximize2, HelpCircle, Thermometer, Volume2, VolumeX, ChevronDown, ChevronUp, Compass, Navigation, Loader2 } from "lucide-react";
import { ShorelineCompass } from "../illustrations/ShorelineCompass";
import { MapGeoJSON, RiskLabel, MarineSnapshot } from "@/lib/types";
import { useLocation } from "@/lib/locationContext";
import { synthesizeSpeech } from "@/lib/api";
import { LANGUAGES } from "../common/LanguageToggle";

function formatDDM(lat: number, lon: number): string {
  const latDeg = Math.floor(Math.abs(lat));
  const latMin = ((Math.abs(lat) - latDeg) * 60).toFixed(2);
  const latDir = lat >= 0 ? "N" : "S";

  const lonDeg = Math.floor(Math.abs(lon));
  const lonMin = ((Math.abs(lon) - lonDeg) * 60).toFixed(2);
  const lonDir = lon >= 0 ? "E" : "W";

  return `${String(latDeg).padStart(2, "0")}° ${latMin}' ${latDir}, ${String(lonDeg).padStart(3, "0")}° ${lonMin}' ${lonDir}`;
}

function calculateBearing(lat1: number, lon1: number, lat2: number, lon2: number): number {
  const toRad = (deg: number) => (deg * Math.PI) / 180;
  const toDeg = (rad: number) => (rad * 180) / Math.PI;

  const φ1 = toRad(lat1);
  const φ2 = toRad(lat2);
  const Δλ = toRad(lon2 - lon1);

  const y = Math.sin(Δλ) * Math.cos(φ2);
  const x = Math.cos(φ1) * Math.sin(φ2) - Math.sin(φ1) * Math.cos(φ2) * Math.cos(Δλ);
  const θ = Math.atan2(y, x);

  return (toDeg(θ) + 360) % 360;
}

function bearingToCardinal(degrees: number): string {
  const dirs = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"];
  const ix = Math.round(degrees / 22.5) % 16;
  return dirs[ix];
}

interface ActiveRouteInfo {
  startName: string;
  endName: string;
  totalDistanceKm: number;
  totalDistanceNm: number;
  initialBearing: number;
  initialCardinal: string;
  startCoords?: [number, number];
  endCoords?: [number, number];
  waveM: number;
  windKmh: number;
  legsCount: number;
}

function buildSteerSpeechText(info: ActiveRouteInfo, lang: string): string {
  const bearing = Math.round(info.initialBearing);
  const card = info.initialCardinal;
  const dest = info.endName || "Fishing Grounds";
  const nm = info.totalDistanceNm;
  const km = info.totalDistanceKm;
  const wave = info.waveM;

  const cardinalNames: Record<string, Record<string, string>> = {
    en: { N: "North", NNE: "North North-East", NE: "North-East", ENE: "East North-East", E: "East", ESE: "East South-East", SE: "South-East", SSE: "South South-East", S: "South", SSW: "South South-West", SW: "South-West", WSW: "West South-West", W: "West", WNW: "West North-West", NW: "North-West", NNW: "North North-West" },
    hi: { N: "उत्तर", NNE: "उत्तर उत्तर-पूर्व", NE: "उत्तर-पूर्व", ENE: "पूर्व उत्तर-पूर्व", E: "पूर्व", ESE: "पूर्व दक्षिण-पूर्व", SE: "दक्षिण-पूर्व", SSE: "दक्षिण दक्षिण-पूर्व", S: "दक्षिण", SSW: "दक्षिण दक्षिण-पश्चिम", SW: "दक्षिण-पश्चिम", WSW: "पश्चिम दक्षिण-पश्चिम", W: "पश्चिम", WNW: "पश्चिम उत्तर-पश्चिम", NW: "उत्तर-पश्चिम", NNW: "उत्तर उत्तर-पश्चिम" },
    ta: { N: "வடக்கு", NNE: "வடக்கு வடகிழக்கு", NE: "வடகிழக்கு", ENE: "கிழக்கு வடகிழக்கு", E: "கிழக்கு", ESE: "கிழக்கு தென்கிழக்கு", SE: "தென்கிழக்கு", SSE: "தெற்கு தென்கிழக்கு", S: "தெற்கு", SSW: "தெற்கு தென்மேற்கு", SW: "தென்மேற்கு", WSW: "மேற்கு தென்மேற்கு", W: "மேற்கு", WNW: "மேற்கு வடமேற்கு", NW: "வடமேற்கு", NNW: "வடக்கு வடமேற்கு" },
    ml: { N: "വടക്ക്", NNE: "വടക്ക് വടക്കുകിഴക്ക്", NE: "വടക്കുകിഴക്ക്", ENE: "കിഴക്ക് വടക്കുകിഴക്ക്", E: "കിഴക്ക്", ESE: "കിഴക്ക് തെക്കുകിഴക്ക്", SE: "തെക്കുകിഴക്ക്", SSE: "തെക്ക് തെക്കുകിഴക്ക്", S: "തെക്ക്", SSW: "തെക്ക് തെക്കുപടിഞ്ഞാറ്", SW: "തെക്കുപടിഞ്ഞാറ്", WSW: "പടിഞ്ഞാറ് തെക്കുപടിഞ്ഞാറ്", W: "പടിഞ്ഞാറ്", WNW: "പടിഞ്ഞാറ് വടക്കുപടിഞ്ഞാറ്", NW: "വടക്കുപടിഞ്ഞാറ്", NNW: "വടക്ക് വടക്കുപടിഞ്ഞാറ്" },
    te: { N: "ఉత్తరం", NNE: "ఉత్తర ఈశాన్యం", NE: "ఈశాన్యం", ENE: "తూర్పు ఈశాన్యం", E: "తూర్పు", ESE: "తూర్పు ఆగ్నేయం", SE: "ఆగ్నేయం", SSE: "దక్షిణ ఆగ్నేయం", S: "దక్షిణం", SSW: "దక్షిణ నైరుతి", SW: "నైరుతి", WSW: "పడమర నైరుతి", W: "పడమర", WNW: "పడమర వాయువ్యం", NW: "వాయువ్యం", NNW: "ఉత్తర వాయువ్యం" },
    gu: { N: "ઉત્તર", NNE: "ઉત્તર ઉત્તર-પૂર્વ", NE: "ઉત્તર-પૂર્વ", ENE: "પૂર્વ ઉત્તર-પૂર્વ", E: "પૂર્વ", ESE: "પૂર્વ દક્ષિણ-પૂર્વ", SE: "દક્ષિણ-પૂર્વ", SSE: "દક્ષિણ દક્ષિણ-પૂર્વ", S: "દક્ષિણ", SSW: "દક્ષિણ દક્ષિણ-પશ્ચિમ", SW: "દક્ષિણ-પશ્ચિમ", WSW: "પશ્ચિમ દક્ષિણ-પશ્ચિમ", W: "પશ્ચિમ", WNW: "પશ્ચિમ ઉત્તર-પશ્ચિમ", NW: "ઉત્તર-પશ્ચિમ", NNW: "ઉત્તર ઉત્તર-પશ્ચિમ" },
    mr: { N: "उत्तर", NNE: "उत्तर उत्तर-पूर्व", NE: "उत्तर-पूर्व", ENE: "पूर्व उत्तर-पूर्व", E: "पूर्व", ESE: "पूर्व दक्षिण-पूर्व", SE: "दक्षिण-पूर्व", SSE: "दक्षिण दक्षिण-पूर्व", S: "दक्षिण", SSW: "दक्षिण दक्षिण-पश्चिम", SW: "दक्षिण-पश्चिम", WSW: "पश्चिम दक्षिण-पश्चिम", W: "पश्चिम", WNW: "पश्चिम उत्तर-पश्चिम", NW: "उत्तर-पश्चिम", NNW: "उत्तर उत्तर-पश्चिम" },
    bn: { N: "উত্তর", NNE: "উত্তর উত্তর-পূর্ব", NE: "উত্তর-পূর্ব", ENE: "পূর্ব উত্তর-পূর্ব", E: "পূর্ব", ESE: "পূর্ব দক্ষিণ-পূর্ব", SE: "দক্ষিণ-পূর্ব", SSE: "দক্ষিণ দক্ষিণ-পূর্ব", S: "দক্ষিণ", SSW: "দক্ষিণ দক্ষিণ-পশ্চিম", SW: "দক্ষিণ-পশ্চিম", WSW: "পশ্চিম দক্ষিণ-পশ্চিম", W: "পশ্চিম", WNW: "পশ্চিম উত্তর-পশ্চিম", NW: "উত্তর-পশ্চিম", NNW: "উত্তর উত্তর-পশ্চিম" },
    od: { N: "ଉତ୍ତର", NNE: "ଉତ୍ତର ଉତ୍ତର-ପୂର୍ବ", NE: "ଉତ୍ତର-ପୂର୍ବ", ENE: "ପୂର୍ବ ଉତ୍ତର-ପୂର୍ବ", E: "ପୂର୍ବ", ESE: "ପୂର୍ବ ଦକ୍ଷିଣ-ପୂର୍ବ", SE: "ଦକ୍ଷିଣ-ପୂର୍ବ", SSE: "ଦକ୍ଷିଣ ଦକ୍ଷିଣ-ପୂର୍ବ", S: "ଦକ୍ଷିଣ", SSW: "ଦକ୍ଷିଣ ଦକ୍ଷିଣ-ପଶ୍ଚିମ", SW: "ଦକ୍ଷିଣ-ପଶ୍ଚିମ", WSW: "ପଶ୍ଚିମ ଦକ୍ଷିଣ-ପଶ୍ଚିମ", W: "ପଶ୍ଚିମ", WNW: "ପଶ୍ଚିମ ଉତ୍ତର-ପଶ୍ଚିମ", NW: "ଉତ୍ତର-ପଶ୍ଚିମ", NNW: "ଉତ୍ତର ଉତ୍ତର-ପଶ୍ଚିମ" },
  };

  const cName = (cardinalNames[lang] && cardinalNames[lang][card]) || (cardinalNames.en[card] || card);

  switch (lang) {
    case "hi":
      return `ध्यान दें कप्तान। ${dest} की ओर कंपास दिशा ${bearing} डिग्री ${cName} पर नाव चलाएं। कुल समुद्री दूरी ${nm} नॉटिकल मील (${km} किलोमीटर) है। समुद्र में लहरों की ऊंचाई ${wave} मीटर है। नीले सुरक्षित नौवहन गलियारे में रहें।`;
    case "ta":
      return `கவனிக்கவும் மாலுமியே. ${dest} நோக்கி திசைகாட்டி வழித்தடம் ${bearing} டிகிரி ${cName} வழியில் படகை செலுத்துங்கள். மொத்த கடல் தூரம் ${nm} நாட்டிகல் மைல் (${km} கிலோமீட்டர்). அலை உயரம் ${wave} மீட்டர். நீல நிற பாதுகாப்பு கடல் பாதையில் செல்லவும்.`;
    case "ml":
      return `ശ്രദ്ധിക്കുക സ്രാങ്കേ. ${dest} ലക്ഷ്യമാക്കി കോമ്പസ് ദിശ ${bearing} ഡിഗ്രി ${cName} ലേക്ക് ബോട്ട് തിരിക്കുക. ആകെ കടൽ ദൂരം ${nm} നോട്ടിക്കൽ മൈൽ (${km} കിലോമീറ്റർ). തിരമാല ഉയരം ${wave} മീറ്റർ. നീല സുരക്ഷിത ചാനലിലൂടെ മാത്രം സഞ്ചരിക്കുക.`;
    case "te":
      return `శ్రద్ధ వహించండి కెప్టెన్. ${dest} వైపు కంపాస్ దిశ ${bearing} డిగ్రీలు ${cName} లో పడవను నడపండి. మొత్తం సముద్ర దూరం ${nm} నాటికల్ మైళ్ళు (${km} కిలోమీటర్లు). అలల ఎత్తు ${wave} మీటర్లు. నీలిరంగు సురక్షిత ఛానల్‌లో ప్రయాణించండి.`;
    case "gu":
      return `ધ્યાન આપો કપ્તાન. ${dest} તરફ હોકાયંત્ર દિશા ${bearing} ડિગ્રી ${cName} પર હોડી ચલાવો. કુલ દરિયાઈ અંતર ${nm} નોટિકલ માઈલ (${km} કિલોમીટર) છે. મોજાંની ઊંચાઈ ${wave} મીટર છે. વાદળી સુરક્ષિત દરિયાઈ ચેનલમાં રહો.`;
    case "mr":
      return `लक्ष द्या तांडेल. ${dest} कडे होकायंत्र दिशा ${bearing} अंश ${cName} वर बोट चालवा. एकूण सागरी अंतर ${nm} नॉटिकल मैल (${km} किलोमीटर) आहे. लाटांची उंची ${wave} मीटर आहे. निळ्या सुरक्षित कॉरिडॉरमधून प्रवास करा.`;
    case "bn":
      return `মনোযোগ দিন নাবিক। ${dest} অভিমুখে কম্পাস দিক ${bearing} ডিগ্রি ${cName} এ নৌকা চালান। মোট সামুদ্রিক দূরত্ব ${nm} নটিক্যাল মাইল (${km} কিলোমিটার)। ঢেউয়ের উচ্চতা ${wave} মিটার। নীল নিরাপদ চ্যানেলের মধ্যে চলুন।`;
    case "od":
      return `ଧ୍ୟାନ ଦିଅନ୍ତୁ କ୍ୟାପ୍ଟେନ। ${dest} ଆଡ଼କୁ କମ୍ପାସ ଦିଗ ${bearing} ଡିଗ୍ରୀ ${cName} ରେ ଡଙ୍ଗା ଚଳାନ୍ତୁ। ମୋଟ ସାମୁଦ୍ରିକ ଦୂରତା ${nm} ନଟିକାଲ୍ ମାଇଲ୍ (${km} କିଲୋମିଟର)। ଢେଉର ଉଚ୍ଚତା ${wave} ମିଟର। ନୀଳ ନିରାପଦ ଚ୍ୟାନେଲରେ ଗତି କରନ୍ତୁ।`;
    default:
      return `Attention Skipper. Set compass course ${bearing} degrees ${cName} towards ${dest}. Total passage distance ${nm} nautical miles (${km} kilometers). Sea state wave height ${wave} meters. Maintain course within the blue safe navigation corridor.`;
  }
}

interface Props {
  geoJson?: MapGeoJSON | null;
  riskLabel?: RiskLabel;
  locationName?: string;
  className?: string;
  snapshot?: MarineSnapshot | null;
  onWhyThisResult?: () => void;
  language?: string;
}

export const MarineMap: React.FC<Props> = ({
  geoJson,
  riskLabel = "LOW",
  locationName = "Coastal Waters",
  className = "w-full h-full min-h-[350px]",
  snapshot,
  onWhyThisResult,
  language = "en",
}) => {
  const { selectedLocation, selectCoordinates } = useLocation();
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapInstanceRef = useRef<any>(null);
  const geoLayerGroupRef = useRef<any>(null);
  const [isMounted, setIsMounted] = useState(false);
  const [isLegendOpen, setIsLegendOpen] = useState(false);
  const [featuresCount, setFeaturesCount] = useState({ pfz: 0, imbl: false, query: false });
  const [activeRouteInfo, setActiveRouteInfo] = useState<ActiveRouteInfo | null>(null);
  const [isHudMinimized, setIsHudMinimized] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [isLoadingVoice, setIsLoadingVoice] = useState(false);
  const [audioElement, setAudioElement] = useState<HTMLAudioElement | null>(null);

  const hasGeoData = Boolean(geoJson && geoJson.features && geoJson.features.length > 0);

  // Guard SSR
  useEffect(() => {
    setIsMounted(true);
  }, []);

  useEffect(() => {
    if (!isMounted || !mapContainerRef.current) return;

    let L: any;

    const initMap = async () => {
      L = (await import("leaflet")).default;

      if (!mapInstanceRef.current && mapContainerRef.current) {
        const centerLat = selectedLocation?.lat || 10.5;
        const centerLon = selectedLocation?.lon || 78.5;

        const map = L.map(mapContainerRef.current, {
          center: [centerLat, centerLon],
          zoom: selectedLocation ? 8 : 6,
          zoomControl: true,
          attributionControl: false,
        });

        // Standard OpenStreetMap tiles (Reliable, keyless, zero watermarks)
        L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
          maxZoom: 18,
          subdomains: ["a", "b", "c"],
          attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
        }).addTo(map);

        L.control
          .attribution({
            position: "bottomright",
            prefix: '<span class="text-[9px] text-gray-500">Tarang Marine • INCOIS • OSM</span>',
          })
          .addTo(map);

        // Click to pick location
        map.on("click", (e: any) => {
          const lat = Number(e.latlng.lat.toFixed(4));
          const lon = Number(e.latlng.lng.toFixed(4));
          const btnId = `btn-set-loc-${Math.round(lat * 100)}-${Math.round(lon * 100)}`;
          L.popup()
            .setLatLng(e.latlng)
            .setContent(
              `<div style="font-family: sans-serif; font-size: 12px; padding: 4px; color: #1c1917;">
                <div style="font-weight: 600; margin-bottom: 2px;">Marine Point</div>
                <div style="font-family: monospace; font-size: 11px; color: #57534e; margin-bottom: 6px;">${lat.toFixed(2)}°N, ${lon.toFixed(2)}°E</div>
                <button id="${btnId}" style="background: #f59e0b; color: #1c1917; border: none; border-radius: 6px; padding: 4px 8px; font-weight: 600; font-size: 11px; cursor: pointer; box-shadow: 0 1px 2px rgba(0,0,0,0.1);">
                  📍 Set Active Location
                </button>
              </div>`
            )
            .openOn(map);

          setTimeout(() => {
            const btn = document.getElementById(btnId);
            if (btn) {
              btn.onclick = () => {
                selectCoordinates(lat, lon, undefined, "map");
                map.closePopup();
              };
            }
          }, 50);
        });

        const layerGroup = L.layerGroup().addTo(map);
        mapInstanceRef.current = map;
        geoLayerGroupRef.current = layerGroup;
      }

      if (hasGeoData) {
        renderFeatures(L);
      } else if (selectedLocation && mapInstanceRef.current) {
        mapInstanceRef.current.setView([selectedLocation.lat, selectedLocation.lon], 8);
      }
    };

    initMap();

    return () => {
      if (mapInstanceRef.current) {
        mapInstanceRef.current.remove();
        mapInstanceRef.current = null;
      }
    };
  }, [isMounted]);

  // Update features whenever geoJson or riskLabel changes
  useEffect(() => {
    if (!mapInstanceRef.current) return;
    import("leaflet").then((leafletModule) => {
      renderFeatures(leafletModule.default);
    });
  }, [geoJson, riskLabel]);

  const renderFeatures = (L: any) => {
    if (!mapInstanceRef.current || !geoLayerGroupRef.current) return;

    const group = geoLayerGroupRef.current;
    group.clearLayers();

    const bounds = L.latLngBounds([]);
    let pfzCount = 0;
    let hasImbl = false;
    let hasQuery = false;
    let foundRoute: any = null;
    let foundStart: any = null;
    let foundEnd: any = null;
    let routeSegmentsCount = 0;

    const riskStroke =
      riskLabel === "HIGH" || riskLabel === "EXTREME"
        ? "#DC2626"
        : riskLabel === "MODERATE"
        ? "#D97706"
        : "#1B8755";

    if (geoJson && geoJson.features && geoJson.features.length > 0) {
      geoJson.features.forEach((feature) => {
        const geom = feature.geometry;
        const props = feature.properties || {};
        const featType = props.feature_type;

        // 1. Query Location Point
        if (featType === "query_point" || props.name === "Query Location") {
          const [lon, lat] = geom.coordinates;
          hasQuery = true;
          bounds.extend([lat, lon]);

          // Coastal safety perimeter circle (20km radius zone)
          L.circle([lat, lon], {
            radius: 20000,
            color: riskStroke,
            weight: 1.5,
            fillColor: riskStroke,
            fillOpacity: 0.08,
            dashArray: "4 4",
          }).addTo(group);

          const pinHtml = `
            <div style="position: relative; display: flex; align-items: center; justify-content: center;">
              <div style="position: absolute; width: 34px; height: 34px; border-radius: 9999px; background: rgba(46, 143, 160, 0.25); animation: ping 2s cubic-bezier(0, 0, 0.2, 1) infinite;"></div>
              <div style="width: 22px; height: 22px; border-radius: 9999px; background: #16242B; border: 2.5px solid #FFFFFF; box-shadow: 0 2px 6px rgba(0,0,0,0.3); display: flex; align-items: center; justify-content: center;">
                <div style="width: 8px; height: 8px; border-radius: 9999px; background: #2E8FA0;"></div>
              </div>
            </div>
          `;
          const queryIcon = L.divIcon({
            html: pinHtml,
            className: "custom-query-pin",
            iconSize: [34, 34],
            iconAnchor: [17, 17],
          });

          const whyBtnId = `why-point-btn-${Math.floor(Math.random() * 10000)}`;
          const waveTxt = snapshot?.weather?.wave_height_m !== undefined && snapshot?.weather?.wave_height_m !== null
            ? `• Wave: <b>${snapshot.weather.wave_height_m}m</b><br/>` : "";
          const windTxt = snapshot?.weather?.wind_speed_kmh !== undefined && snapshot?.weather?.wind_speed_kmh !== null
            ? `• Wind: <b>${snapshot.weather.wind_speed_kmh} km/h</b><br/>` : "";
          const sstTxt = snapshot?.sst?.sst_celsius !== undefined && snapshot?.sst?.sst_celsius !== null
            ? `• SST: <b>${snapshot.sst.sst_celsius.toFixed(1)}°C</b>${snapshot.sst.sst_anomaly_c != null ? ` (${snapshot.sst.sst_anomaly_c >= 0 ? "+" : ""}${snapshot.sst.sst_anomaly_c.toFixed(1)}°C anom)` : ""}<br/><span style="font-size: 10px; color: #64748B; font-style: italic;">SST reflects temperature only; does not guarantee fish presence.</span><br/>` : "";

          const marker = L.marker([lat, lon], { icon: queryIcon })
            .bindPopup(`
              <div style="font-family: sans-serif; font-size: 12px; color: #16242B; padding: 4px; min-width: 170px;">
                <strong style="color: #0284c7; font-size: 13px;">📍 ${props.label || locationName}</strong><br/>
                <span style="color: #6B7280; font-size: 11px;">${formatDDM(lat, lon)}</span><br/>
                <div style="margin-top: 4px; line-height: 1.4; color: #374151;">
                  ${waveTxt}
                  ${windTxt}
                  ${sstTxt}
                  • Verdict: <b style="color: ${riskStroke};">${riskLabel} RISK</b>
                </div>
                ${onWhyThisResult ? `
                  <button id="${whyBtnId}" style="margin-top: 6px; width: 100%; background: #4f46e5; color: white; border: none; border-radius: 4px; padding: 4px 6px; font-size: 11px; font-weight: 600; cursor: pointer;">
                    🔍 Why this result?
                  </button>
                ` : ""}
              </div>
            `)
            .addTo(group);

          if (onWhyThisResult) {
            marker.on("popupopen", () => {
              const btn = document.getElementById(whyBtnId);
              if (btn) {
                btn.onclick = () => {
                  onWhyThisResult();
                };
              }
            });
          }
        }

        // 2. Potential Fishing Zone (PFZ) indicator beacons
        else if (featType === "pfz_zone" || props.type === "pfz") {
          const [lon, lat] = geom.coordinates;
          pfzCount++;
          bounds.extend([lat, lon]);

          const chl = props.chlorophyll_mg_m3 || props.chl || "1.2";
          const dist = props.distance_km != null ? `${Math.round(props.distance_km)} km` : "Nearby";

          const pfzHtml = `
            <div style="display: flex; align-items: center; justify-content: center; width: 24px; height: 24px; background-color: #1B8755; color: white; border: 2px solid white; border-radius: 50%; box-shadow: 0 2px 5px rgba(0,0,0,0.25); font-size: 12px;">
              🐟
            </div>
          `;
          const pfzIcon = L.divIcon({
            html: pfzHtml,
            className: "custom-pfz-pin",
            iconSize: [24, 24],
            iconAnchor: [12, 12],
          });

          L.marker([lat, lon], { icon: pfzIcon })
            .bindPopup(`
              <div style="font-family: sans-serif; font-size: 12px; color: #16242B;">
                <strong style="color: #1B8755;">🐟 Fishing Indicator Zone #${pfzCount}</strong><br/>
                <div style="margin-top: 4px; line-height: 1.4; color: #374151;">
                  • Coordinates: <b>${formatDDM(lat, lon)}</b><br/>
                  • Distance: <b>${dist} offshore</b><br/>
                  • Chlorophyll-a: <b>${typeof chl === "number" ? chl.toFixed(2) : chl} mg/m³</b><br/>
                  • Bearing: <b>${props.bearing_deg || props.bearing || "E"}°</b>
                </div>
                <div style="margin-top: 6px; font-size: 10px; color: #6B7280; border-top: 1px solid #E5E7EB; padding-top: 4px;">
                  INCOIS Oceansat-2 satellite proxy indicator (not a catch guarantee)
                </div>
              </div>
            `)
            .addTo(group);
        }

        // 3. Safe Navigation Fairway Corridor Buffer Swath
        else if (props.type === "route_corridor") {
          const latLngs = geom.coordinates.map(([lon, lat]: [number, number]) => {
            bounds.extend([lat, lon]);
            return [lat, lon];
          });
          L.polyline(latLngs, {
            color: props.stroke || "#0284c7",
            weight: 26,
            opacity: 0.16,
            lineCap: "round",
            lineJoin: "round",
          })
            .bindPopup(`
              <div style="font-family: sans-serif; font-size: 12px; color: #16242B; min-width: 175px;">
                <strong style="color: #0284c7; font-size: 13px;">🛡️ Safe Navigation Fairway Corridor</strong><br/>
                <p style="margin-top: 4px; font-size: 11px; color: #475569; line-height: 1.4;">
                  Recommended ±0.5 NM buffer fairway. NavIC/ECDIS safe transit channel clear of charted shallow reefs.
                </p>
              </div>
            `)
            .addTo(group);
        }

        // 4. Overall Route Line with Flow & Directional Chevrons
        else if (props.type === "route") {
          foundRoute = feature;
          const latLngs = geom.coordinates.map(([lon, lat]: [number, number]) => {
            bounds.extend([lat, lon]);
            return [lat, lon];
          });

          // A. Deep navy casing polyline for contrast against light ocean tiles
          L.polyline(latLngs, {
            color: "#0f172a",
            weight: 6.5,
            opacity: 0.55,
            lineCap: "round",
            lineJoin: "round",
          }).addTo(group);

          // B. Main vibrant route line
          L.polyline(latLngs, {
            color: props.stroke || "#f59e0b",
            weight: props["stroke-width"] || (props.is_active_profile === false ? 3 : 4),
            opacity: props.opacity !== undefined ? props.opacity : 0.95,
            lineCap: "round",
            lineJoin: "round",
          }).addTo(group);

          // C. Animated nautical dash flow
          L.polyline(latLngs, {
            className: "leaflet-marine-flow",
            color: "#ffffff",
            weight: 2,
            opacity: 0.85,
          }).addTo(group);

          // D. Directional Chevrons along route segments pointing in direction of travel
          if (geom.coordinates.length >= 2) {
            for (let c = 0; c < geom.coordinates.length - 1; c++) {
              const [p1Lon, p1Lat] = geom.coordinates[c];
              const [p2Lon, p2Lat] = geom.coordinates[c + 1];
              const segBearing = calculateBearing(p1Lat, p1Lon, p2Lat, p2Lon);
              const midLat = (p1Lat + p2Lat) / 2;
              const midLon = (p1Lon + p2Lon) / 2;

              const chevronHtml = `
                <div style="transform: rotate(${segBearing}deg); display: flex; align-items: center; justify-content: center; width: 18px; height: 18px; pointer-events: none;">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="${props.stroke || '#f59e0b'}" stroke="#ffffff" stroke-width="2">
                    <polygon points="12,2 22,20 12,15 2,20" />
                  </svg>
                </div>
              `;
              const chevronIcon = L.divIcon({
                html: chevronHtml,
                className: "custom-chevron-icon",
                iconSize: [18, 18],
                iconAnchor: [9, 9],
              });
              L.marker([midLat, midLon], { icon: chevronIcon, interactive: false }).addTo(group);
            }
          }
        }

        // 5. Per-Leg Risk-Colored Segments
        else if (props.type === "route_segment") {
          routeSegmentsCount++;
          const latLngs = geom.coordinates.map(([lon, lat]: [number, number]) => {
            bounds.extend([lat, lon]);
            return [lat, lon];
          });
          const segColor = props.stroke || "#2563eb";
          const segBearing = props.bearing_deg != null ? props.bearing_deg : (latLngs.length >= 2 ? calculateBearing(latLngs[0][0], latLngs[0][1], latLngs[1][0], latLngs[1][1]) : 0);
          const segCardinal = props.bearing_cardinal || bearingToCardinal(segBearing);
          const distNm = props.distance_nm != null ? `${props.distance_nm} NM` : "";
          const distKm = props.distance_km != null ? `${props.distance_km} km` : "";

          L.polyline(latLngs, {
            color: segColor,
            weight: 5,
            opacity: 0.9,
          })
            .bindPopup(`
              <div style="font-family: sans-serif; font-size: 12px; color: #16242B; min-width: 175px;">
                <strong style="color: ${segColor}; font-size: 13px;">Leg #${(props.segment_index ?? 0) + 1}</strong><br/>
                <div style="margin-top: 4px; line-height: 1.4; color: #374151;">
                  • Steer Directive: <b>Steer ${Math.round(segBearing)}° ${segCardinal}</b><br/>
                  • Distance: <b>${distNm}${distKm ? ` (${distKm})` : ""}</b><br/>
                  • Swell: <b>${props.wave_height_m ?? 0.8}m</b> | Wind: <b>${props.wind_speed_kmh ?? 12} km/h</b><br/>
                  • Risk Level: <b style="color: ${segColor};">${props.risk_label || "LOW"}</b>
                </div>
              </div>
            `)
            .addTo(group);
        }

        // 6. Mid-Leg Nautical Compass Bearing Badges
        else if (props.type === "route_leg_badge") {
          const [lon, lat] = geom.coordinates;
          bounds.extend([lat, lon]);

          const badgeHtml = `
            <div style="background: rgba(15, 23, 42, 0.92); backdrop-filter: blur(4px); color: #38bdf8; border: 1.5px solid #0284c7; border-radius: 9999px; padding: 2px 7px; font-size: 10px; font-weight: 700; box-shadow: 0 2px 8px rgba(0,0,0,0.4); display: inline-flex; align-items: center; gap: 4px; white-space: nowrap; cursor: pointer; user-select: none;">
              <span>🧭 ${Math.round(props.bearing_deg)}° ${props.bearing_cardinal || ""}</span>
              <span style="color: #64748b;">•</span>
              <span style="color: #f8fafc;">${props.distance_nm || props.distance_km} NM</span>
            </div>
          `;
          const badgeIcon = L.divIcon({
            html: badgeHtml,
            className: "custom-leg-badge",
            iconAnchor: [45, 12],
          });

          L.marker([lat, lon], { icon: badgeIcon })
            .bindPopup(`
              <div style="font-family: sans-serif; font-size: 12px; color: #16242B; min-width: 175px;">
                <strong style="color: #0284c7; font-size: 13px;">🧭 Leg #${props.leg_index} Steer Directive</strong><br/>
                <div style="font-size: 13px; font-weight: bold; color: #0f172a; margin: 4px 0;">
                  Steer ${Math.round(props.bearing_deg)}° (${props.bearing_cardinal})
                </div>
                <div style="line-height: 1.4; color: #374151;">
                  • Distance: <b>${props.distance_nm} NM (${props.distance_km} km)</b><br/>
                  • Swell: <b>${props.wave_height_m}m</b> | Wind: <b>${props.wind_speed_kmh} km/h</b><br/>
                  • Safe Fairway: <b>±0.5 NM Channel</b>
                </div>
              </div>
            `)
            .addTo(group);
        }

        // 7. Intermediate Waypoints (Course Alterations)
        else if (props.type === "route_waypoint") {
          const [lon, lat] = geom.coordinates;
          bounds.extend([lat, lon]);

          const wptHtml = `
            <div style="display: flex; align-items: center; justify-content: center; width: 22px; height: 22px; background-color: #0284c7; color: white; border: 2px solid white; border-radius: 50%; box-shadow: 0 2px 6px rgba(0,0,0,0.35); font-size: 10px; font-weight: 800;">
              ${props.waypoint_index}
            </div>
          `;
          const wptIcon = L.divIcon({
            html: wptHtml,
            className: "custom-route-waypoint",
            iconSize: [22, 22],
            iconAnchor: [11, 11],
          });

          L.marker([lat, lon], { icon: wptIcon })
            .bindPopup(`
              <div style="font-family: sans-serif; font-size: 12px; color: #16242B; min-width: 180px;">
                <strong style="color: #0284c7; font-size: 13px;">📍 Waypoint #${props.waypoint_index}</strong><br/>
                <div style="color: #6B7280; font-size: 10.5px; font-family: monospace; margin: 2px 0;">
                  ${formatDDM(lat, lon)}
                </div>
                <div style="margin-top: 4px; line-height: 1.4; color: #374151;">
                  • Course Alteration: <b>Turn to ${Math.round(props.turn_bearing_deg)}° (${props.turn_cardinal})</b><br/>
                  • Swell: <b>${props.wave_height_m}m</b> | Wind: <b>${props.wind_speed_kmh} km/h</b>
                </div>
              </div>
            `)
            .addTo(group);
        }

        // 8. Departure Harbor Marker
        else if (props.type === "route_start") {
          foundStart = feature;
          const [lon, lat] = geom.coordinates;
          bounds.extend([lat, lon]);
          const startHtml = `
            <div style="position: relative; display: flex; align-items: center; justify-content: center;">
              <div style="position: absolute; width: 34px; height: 34px; border-radius: 50%; background: rgba(34, 197, 94, 0.3); animation: ping 2s cubic-bezier(0, 0, 0.2, 1) infinite;"></div>
              <div style="width: 28px; height: 28px; background-color: #16a34a; color: white; border: 2.5px solid white; border-radius: 50%; box-shadow: 0 2px 6px rgba(0,0,0,0.35); font-size: 13px; display: flex; align-items: center; justify-content: center; z-index: 2;">
                ⚓
              </div>
            </div>
          `;
          const startIcon = L.divIcon({
            html: startHtml,
            className: "custom-route-start",
            iconSize: [34, 34],
            iconAnchor: [17, 17],
          });
          L.marker([lat, lon], { icon: startIcon })
            .bindPopup(`
              <div style="font-family: sans-serif; font-size: 12px; color: #16242B; min-width: 180px;">
                <strong style="color: #16a34a; font-size: 13px;">⚓ Departure: ${props.name || "Start Harbor"}</strong><br/>
                <div style="color: #6B7280; font-size: 10.5px; font-family: monospace; margin: 2px 0;">
                  ${formatDDM(lat, lon)}
                </div>
                <div style="margin-top: 4px; line-height: 1.4; color: #374151;">
                  ${props.initial_bearing_deg != null ? `• Initial Course: <b>Steer ${Math.round(props.initial_bearing_deg)}° (${props.initial_cardinal})</b><br/>` : ""}
                  ${props.total_distance_nm != null ? `• Total Voyage: <b>${props.total_distance_nm} NM (${props.total_distance_km} km)</b>` : ""}
                </div>
              </div>
            `)
            .addTo(group);
        }

        // 9. Destination Marker
        else if (props.type === "route_end") {
          foundEnd = feature;
          const [lon, lat] = geom.coordinates;
          bounds.extend([lat, lon]);
          const endHtml = `
            <div style="display: flex; align-items: center; justify-content: center; width: 28px; height: 28px; background-color: #ef4444; color: white; border: 2.5px solid white; border-radius: 50%; box-shadow: 0 2px 6px rgba(0,0,0,0.35); font-size: 13px;">
              🏁
            </div>
          `;
          const endIcon = L.divIcon({
            html: endHtml,
            className: "custom-route-end",
            iconSize: [28, 28],
            iconAnchor: [14, 14],
          });
          L.marker([lat, lon], { icon: endIcon })
            .bindPopup(`
              <div style="font-family: sans-serif; font-size: 12px; color: #16242B; min-width: 180px;">
                <strong style="color: #ef4444; font-size: 13px;">🏁 Destination: ${props.name || "Destination"}</strong><br/>
                <div style="color: #6B7280; font-size: 10.5px; font-family: monospace; margin: 2px 0;">
                  ${formatDDM(lat, lon)}
                </div>
                <div style="margin-top: 4px; line-height: 1.4; color: #374151;">
                  • Arrival Ground • Monitor echo-sounder & drift.<br/>
                  ${props.total_distance_nm != null ? `• Total Voyage: <b>${props.total_distance_nm} NM</b>` : ""}
                </div>
              </div>
            `)
            .addTo(group);
        }

        // 10. PFZ Waypoint Near Route
        else if (props.type === "pfz_near_route") {
          const [lon, lat] = geom.coordinates;
          bounds.extend([lat, lon]);
          const pfzHtml = `
            <div style="display: flex; align-items: center; justify-content: center; width: 22px; height: 22px; background-color: #06b6d4; color: white; border: 2px solid white; border-radius: 50%; box-shadow: 0 2px 4px rgba(0,0,0,0.25); font-size: 11px;">
              🐟
            </div>
          `;
          const pfzIcon = L.divIcon({
            html: pfzHtml,
            className: "custom-pfz-near-route",
            iconSize: [22, 22],
            iconAnchor: [11, 11],
          });
          L.marker([lat, lon], { icon: pfzIcon })
            .bindPopup(`
              <div style="font-family: sans-serif; font-size: 12px;">
                <strong style="color: #0891b2;">🐟 Fishing Zone Waypoint</strong><br/>
                <div style="color: #6B7280; font-size: 10.5px; font-family: monospace; margin: 2px 0;">
                  ${formatDDM(lat, lon)}
                </div>
                <span>Chlorophyll-a: <b>${props.chl_mg_m3 || 0} mg/m³</b></span>
              </div>
            `)
            .addTo(group);
        }

        // 11. Warning Marker on Route
        else if (props.type === "route_warning") {
          const [lon, lat] = geom.coordinates;
          bounds.extend([lat, lon]);
          const warnHtml = `
            <div style="display: flex; align-items: center; justify-content: center; width: 24px; height: 24px; background-color: #ef4444; color: white; border: 2px solid white; border-radius: 50%; box-shadow: 0 2px 4px rgba(0,0,0,0.3); font-size: 12px;">
              ⚠️
            </div>
          `;
          const warnIcon = L.divIcon({
            html: warnHtml,
            className: "custom-route-warning",
            iconSize: [24, 24],
            iconAnchor: [12, 12],
          });
          L.marker([lat, lon], { icon: warnIcon })
            .bindPopup(`
              <div style="font-family: sans-serif; font-size: 12px; color: #dc2626;">
                <strong>⚠️ Severe Condition Warning</strong><br/>
                <div style="color: #6B7280; font-size: 10.5px; font-family: monospace; margin: 2px 0;">
                  ${formatDDM(lat, lon)}
                </div>
                <span>Risk Level: <b>${props.risk_label || "HIGH"}</b> (Score: ${props.risk_score || 0})</span>
              </div>
            `)
            .addTo(group);
        }

        // 12. International Maritime Boundary Line (IMBL)
        else if (featType === "imbl_boundary" || props.type === "boundary" || geom.type === "LineString") {
          hasImbl = true;
          const latLngs = geom.coordinates.map(([lon, lat]: [number, number]) => {
            bounds.extend([lat, lon]);
            return [lat, lon];
          });

          L.polyline(latLngs, {
            color: "#DC2626",
            weight: 2.5,
            dashArray: "6, 6",
            opacity: 0.9,
          })
            .bindPopup(`
              <div style="font-family: sans-serif; font-size: 12px;">
                <strong style="color: #DC2626;">⛔ ${props.name || "India-Sri Lanka IMBL"}</strong><br/>
                <p style="margin-top: 4px; font-size: 11px; color: #4B5563;">
                  International Maritime Boundary Line. Indian fishermen must NOT cross this demarcation line under any circumstances.
                </p>
              </div>
            `)
            .addTo(group);
        }
      });

      // Derive active route info for Helmsman HUD
      if (foundRoute || (foundStart && foundEnd)) {
        const rProps = foundRoute?.properties || {};
        const sCoords = foundStart?.geometry?.coordinates; // [lon, lat]
        const eCoords = foundEnd?.geometry?.coordinates; // [lon, lat]

        const distKm = rProps.total_distance_km ?? (foundStart?.properties?.total_distance_km || 0);
        const distNm = rProps.total_distance_nm ?? (foundStart?.properties?.total_distance_nm || (distKm ? +(distKm * 0.539957).toFixed(1) : 0));
        let initBearing = rProps.initial_bearing_deg ?? foundStart?.properties?.initial_bearing_deg;
        let initCardinal = rProps.initial_cardinal ?? foundStart?.properties?.initial_cardinal;

        if (initBearing == null && sCoords && eCoords) {
          initBearing = Math.round(calculateBearing(sCoords[1], sCoords[0], eCoords[1], eCoords[0]));
          initCardinal = bearingToCardinal(initBearing);
        }

        const wave = snapshot?.weather?.wave_height_m ?? 0.8;
        const wind = snapshot?.weather?.wind_speed_kmh ?? 12;

        setActiveRouteInfo({
          startName: foundStart?.properties?.name || "Departure Harbor",
          endName: foundEnd?.properties?.name || "Destination",
          totalDistanceKm: distKm,
          totalDistanceNm: distNm,
          initialBearing: initBearing ?? 0,
          initialCardinal: initCardinal ?? "N",
          startCoords: sCoords ? [sCoords[1], sCoords[0]] : undefined,
          endCoords: eCoords ? [eCoords[1], eCoords[0]] : undefined,
          waveM: typeof wave === "number" ? wave : 0.8,
          windKmh: typeof wind === "number" ? wind : 12,
          legsCount: routeSegmentsCount || 1,
        });
      } else {
        setActiveRouteInfo(null);
      }
    } else {
      setActiveRouteInfo(null);
    }

    setFeaturesCount({ pfz: pfzCount, imbl: hasImbl, query: hasQuery });

    if (bounds.isValid()) {
      mapInstanceRef.current.fitBounds(bounds, { padding: [40, 40], maxZoom: 10 });
    }
  };

  // Cleanup audio when component unmounts or language changes
  useEffect(() => {
    return () => {
      if (audioElement) {
        audioElement.pause();
        audioElement.currentTime = 0;
      }
      if (typeof window !== "undefined" && "speechSynthesis" in window) {
        window.speechSynthesis.cancel();
      }
    };
  }, [audioElement, language]);

  const speakCourse = async () => {
    if (!activeRouteInfo) return;

    // If currently playing Sarvam audio, stop it
    if (audioElement) {
      audioElement.pause();
      audioElement.currentTime = 0;
      setAudioElement(null);
      setIsSpeaking(false);
      return;
    }

    // If currently playing browser fallback speech, stop it
    if (isSpeaking) {
      if (typeof window !== "undefined" && "speechSynthesis" in window) {
        window.speechSynthesis.cancel();
      }
      setIsSpeaking(false);
      return;
    }

    const speechText = buildSteerSpeechText(activeRouteInfo, language);
    setIsLoadingVoice(true);

    try {
      // Call Sarvam AI Bulbul V3 TTS via backend /speak
      const audioBlob = await synthesizeSpeech(speechText, language);
      const audioUrl = URL.createObjectURL(audioBlob);
      const audio = new Audio(audioUrl);

      audio.onended = () => {
        setIsSpeaking(false);
        setAudioElement(null);
        URL.revokeObjectURL(audioUrl);
      };
      audio.onerror = () => {
        setIsSpeaking(false);
        setAudioElement(null);
        URL.revokeObjectURL(audioUrl);
      };

      setAudioElement(audio);
      await audio.play();
      setIsSpeaking(true);
    } catch (err) {
      console.warn("Sarvam AI TTS failed, falling back to browser speech synthesis:", err);
      // Graceful fallback to browser speech synthesis
      if (typeof window !== "undefined" && "speechSynthesis" in window) {
        const utterance = new SpeechSynthesisUtterance(speechText);
        utterance.rate = 0.95;
        utterance.pitch = 1.0;
        utterance.lang = language === "en" ? "en-IN" : language;
        utterance.onend = () => setIsSpeaking(false);
        utterance.onerror = () => setIsSpeaking(false);

        setIsSpeaking(true);
        window.speechSynthesis.speak(utterance);
      }
    } finally {
      setIsLoadingVoice(false);
    }
  };

  const handleRecenter = async () => {
    if (!mapInstanceRef.current || !geoLayerGroupRef.current) return;
    const L = (await import("leaflet")).default;
    const bounds = L.latLngBounds([]);
    geoLayerGroupRef.current.eachLayer((layer: any) => {
      if (layer.getBounds) bounds.extend(layer.getBounds());
      else if (layer.getLatLng) bounds.extend(layer.getLatLng());
    });
    if (bounds.isValid()) {
      mapInstanceRef.current.fitBounds(bounds, { padding: [40, 40] });
    }
  };

  // ── Active chart state ──
  return (
    <div className={`relative bg-[#E2ECEE] rounded-xl overflow-hidden border border-[var(--border)] shadow-xs flex flex-col ${className}`}>
      {/* Map Control Toolbar */}
      <div className="absolute top-3 left-3 z-[1000] bg-white/90 backdrop-blur-xs border border-[var(--border)] rounded-lg p-2 shadow-xs flex items-center gap-3 text-xs text-[var(--ink)]">
        <div className="flex items-center gap-1.5 font-semibold text-[var(--current)]">
          <Layers className="w-4 h-4" />
          <span>Marine Chart</span>
        </div>

        <div className="h-3.5 w-px bg-[var(--border)]" />

        {/* Dynamic badges */}
        {!hasGeoData ? (
          <span className="text-[11px] text-[var(--ink-muted)]">
            📍 Coastal Waters Overview
          </span>
        ) : (
          <div className="flex items-center gap-2 text-[11px] text-[var(--ink-muted)]">
            {featuresCount.query && (
              <span className="flex items-center gap-1">
                <span className="w-2 h-2 rounded-full bg-[var(--current)]" /> Query Point
              </span>
            )}
            {featuresCount.pfz > 0 && (
              <span className="flex items-center gap-1 font-medium text-[#1B8755]">
                <Fish className="w-3 h-3" /> {featuresCount.pfz} PFZ
              </span>
            )}
            {featuresCount.imbl && (
              <span className="flex items-center gap-1 font-medium text-[#DC2626]">
                <AlertTriangle className="w-3 h-3" /> IMBL Line
              </span>
            )}
            {snapshot?.sst?.sst_celsius != null && (
              <span className="flex items-center gap-1 font-medium text-[#0284C7] bg-[#E0F2FE] px-1.5 py-0.5 rounded border border-[#BAE6FD]" title="Sea Surface Temperature (INCOIS ERDDAP). Thermal indicator only; does not guarantee fish.">
                <Thermometer className="w-3 h-3 text-[#0284C7]" />
                {snapshot.sst.sst_celsius.toFixed(1)}°C SST
                {snapshot.sst.sst_anomaly_c != null && (
                  <span className="text-[10px] opacity-80">
                    ({snapshot.sst.sst_anomaly_c >= 0 ? "+" : ""}{snapshot.sst.sst_anomaly_c.toFixed(1)}°)
                  </span>
                )}
              </span>
            )}
          </div>
        )}
      </div>

      {/* Action buttons: Info / Legend Toggle + Recenter (Part 1C.1) */}
      <div className="absolute top-3 right-3 z-[1000] flex items-center gap-1.5">
        <button
          type="button"
          onClick={() => setIsLegendOpen(!isLegendOpen)}
          className={`p-2 bg-white/90 backdrop-blur-xs hover:bg-white text-[var(--ink)] border border-[var(--border)] rounded-lg shadow-xs transition-colors cursor-pointer ${
            isLegendOpen ? "ring-2 ring-[var(--current)]" : ""
          }`}
          title="Toggle map symbols legend"
          aria-label="Toggle map symbols legend"
        >
          <HelpCircle className="w-4 h-4 text-[var(--ink-muted)]" />
        </button>
        <button
          type="button"
          onClick={handleRecenter}
          className="p-2 bg-white/90 backdrop-blur-xs hover:bg-white text-[var(--ink)] border border-[var(--border)] rounded-lg shadow-xs transition-colors cursor-pointer"
          title="Recenter map on active features"
          aria-label="Recenter map"
        >
          <Maximize2 className="w-4 h-4" />
        </button>
      </div>

      {/* Map DOM target */}
      <div ref={mapContainerRef} className="w-full h-full min-h-[350px] z-10" />

      {/* Real-World Fisherman Helmsman HUD (Floating Navigation Cockpit when Route is Loaded) */}
      {activeRouteInfo && (
        <div className="absolute bottom-3 right-3 left-3 md:left-auto md:w-[470px] z-[1000] bg-[#0B151C]/95 backdrop-blur-md border border-[#1E3A4A] rounded-xl shadow-2xl p-3 text-white pointer-events-auto animate-in slide-in-from-bottom-2 duration-200">
          {/* Top Row: System Badge & Voice Helmsman Button & Minimize */}
          <div className="flex items-center justify-between border-b border-[#1E3A4A]/80 pb-2 mb-2.5">
            <div className="flex items-center gap-2">
              <span className="flex h-2 w-2 relative">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-[#38BDF8] opacity-75"></span>
                <span className="relative inline-flex rounded-full h-2 w-2 bg-[#38BDF8]"></span>
              </span>
              <span className="text-[11px] font-bold tracking-wider text-[#38BDF8] uppercase flex items-center gap-1">
                <Compass className="w-3.5 h-3.5 text-[#38BDF8]" />
                NavIC Marine Helmsman HUD
              </span>
            </div>

            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={speakCourse}
                disabled={isLoadingVoice}
                className={`px-2.5 py-1 rounded text-xs font-semibold flex items-center gap-1.5 transition-all cursor-pointer shadow-xs ${
                  isSpeaking
                    ? "bg-[#EF4444] hover:bg-[#DC2626] text-white animate-pulse"
                    : isLoadingVoice
                    ? "bg-[#0284C7]/60 text-white cursor-wait"
                    : "bg-[#0284C7] hover:bg-[#0369A1] text-white active:scale-95"
                }`}
                title={`Speak steering course aloud using Sarvam AI Bulbul V3 in ${LANGUAGES.find((l) => l.code === language)?.label || "English"}`}
              >
                {isLoadingVoice ? (
                  <>
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    <span>Sarvam TTS...</span>
                  </>
                ) : isSpeaking ? (
                  <>
                    <VolumeX className="w-3.5 h-3.5" />
                    <span>Stop Voice</span>
                  </>
                ) : (
                  <>
                    <Volume2 className="w-3.5 h-3.5" />
                    <span>
                      🔊 Speak Course (
                      <span className="font-mono uppercase text-[10px] bg-white/20 px-1 py-0.5 rounded">
                        {language}
                      </span>
                      )
                    </span>
                  </>
                )}
              </button>

              <button
                type="button"
                onClick={() => setIsHudMinimized(!isHudMinimized)}
                className="text-slate-400 hover:text-white p-1 rounded hover:bg-[#1E3A4A] transition-colors cursor-pointer"
                aria-label="Toggle HUD display"
              >
                {isHudMinimized ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
              </button>
            </div>
          </div>

          {/* Expanded HUD body */}
          {!isHudMinimized ? (
            <div className="space-y-2.5">
              {/* Steer Directive + Rotating Compass Rose */}
              <div className="flex items-center gap-3 bg-[#13222C] p-2.5 rounded-lg border border-[#1E3A4A]">
                {/* Miniature Marine Binnacle Compass */}
                <div className="relative w-12 h-12 rounded-full bg-[#0B151C] border border-[#38BDF8]/40 flex items-center justify-center shrink-0 shadow-inner">
                  {/* Compass needle pointing along bearing */}
                  <div
                    className="absolute w-1 h-8 rounded-full bg-gradient-to-b from-[#EF4444] via-white to-[#38BDF8] transition-transform duration-500 shadow-xs"
                    style={{
                      transform: `rotate(${activeRouteInfo.initialBearing}deg)`,
                      transformOrigin: "center center",
                    }}
                  />
                  <div className="w-2.5 h-2.5 rounded-full bg-white z-10 shadow" />
                  <span className="absolute -top-1 text-[8px] font-extrabold text-slate-400">N</span>
                </div>

                <div className="flex-1 min-w-0">
                  <div className="flex items-baseline gap-1.5 flex-wrap">
                    <span className="text-xl font-black text-[#F8FAFC]">
                      {Math.round(activeRouteInfo.initialBearing)}°
                    </span>
                    <span className="text-base font-extrabold text-[#38BDF8]">
                      {activeRouteInfo.initialCardinal}
                    </span>
                    <span className="text-xs text-slate-300 truncate max-w-[200px]">
                      ➔ {activeRouteInfo.endName}
                    </span>
                  </div>
                  <p className="text-[11px] text-emerald-400 font-medium flex items-center gap-1 mt-0.5">
                    <span>🛡️ Safe transit fairway (±0.5 NM buffer channel)</span>
                  </p>
                </div>
              </div>

              {/* Navigation Telemetry Matrix */}
              <div className="grid grid-cols-3 gap-2 text-center text-xs">
                <div className="bg-[#13222C] p-2 rounded-lg border border-[#1E3A4A]">
                  <div className="text-slate-400 text-[10px] uppercase font-semibold">Voyage Distance</div>
                  <div className="font-bold text-[#F8FAFC] text-sm mt-0.5">
                    {activeRouteInfo.totalDistanceNm} <span className="text-[10px] text-slate-400 font-normal">NM</span>
                  </div>
                  <div className="text-[10px] text-slate-400">({activeRouteInfo.totalDistanceKm} km)</div>
                </div>

                <div className="bg-[#13222C] p-2 rounded-lg border border-[#1E3A4A]">
                  <div className="text-slate-400 text-[10px] uppercase font-semibold">Est. Passage</div>
                  <div className="font-bold text-[#F8FAFC] text-sm mt-0.5">
                    ~{(activeRouteInfo.totalDistanceKm / 20).toFixed(1)} <span className="text-[10px] text-slate-400 font-normal">hrs</span>
                  </div>
                  <div className="text-[10px] text-slate-400">@ 11 kts vessel speed</div>
                </div>

                <div className="bg-[#13222C] p-2 rounded-lg border border-[#1E3A4A]">
                  <div className="text-slate-400 text-[10px] uppercase font-semibold">Sea Conditions</div>
                  <div className="font-bold text-amber-400 text-sm mt-0.5">
                    {activeRouteInfo.waveM}m <span className="text-[10px] text-slate-400 font-normal">swell</span>
                  </div>
                  <div className="text-[10px] text-slate-400">{activeRouteInfo.windKmh} km/h wind</div>
                </div>
              </div>

              {/* Maritime DDM Coordinates Bar */}
              {activeRouteInfo.startCoords && activeRouteInfo.endCoords && (
                <div className="bg-[#0B151C] px-2.5 py-1.5 rounded border border-[#1E3A4A] text-[10px] font-mono text-amber-200/90 flex items-center justify-between">
                  <span title="Departure Port GPS (Degrees & Decimal Minutes)">⚓ {formatDDM(activeRouteInfo.startCoords[0], activeRouteInfo.startCoords[1])}</span>
                  <span className="text-slate-500">➔</span>
                  <span title="Target Catch Ground GPS (Degrees & Decimal Minutes)">🏁 {formatDDM(activeRouteInfo.endCoords[0], activeRouteInfo.endCoords[1])}</span>
                </div>
              )}
            </div>
          ) : (
            /* Minimized compact status */
            <div className="flex items-center justify-between text-xs">
              <div className="flex items-center gap-2">
                <span className="font-black text-[#F8FAFC]">Steer {Math.round(activeRouteInfo.initialBearing)}° {activeRouteInfo.initialCardinal}</span>
                <span className="text-slate-400">•</span>
                <span>{activeRouteInfo.totalDistanceNm} NM</span>
                <span className="text-slate-400">•</span>
                <span className="text-amber-400">{activeRouteInfo.waveM}m swell</span>
              </div>
              <span className="text-[10px] text-[#38BDF8]">Tap to expand HUD</span>
            </div>
          )}
        </div>
      )}

      {/* Map Legend Overlay — tucked behind info toggle button */}
      {isLegendOpen && (
        <div className="absolute bottom-3 left-3 z-[1000] bg-white/95 backdrop-blur-xs border border-[var(--border)] rounded-lg p-2.5 shadow-md text-[11px] text-[var(--ink-muted)] space-y-1.5 pointer-events-auto animate-in fade-in duration-150">
          <div className="flex items-center justify-between font-semibold text-[var(--ink)] text-xs mb-1">
            <span>Map Symbols</span>
            <button
              type="button"
              onClick={() => setIsLegendOpen(false)}
              className="text-[var(--ink-subtle)] hover:text-[var(--ink)] text-xs px-1 cursor-pointer"
            >
              ✕
            </button>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-2.5 h-2.5 rounded-full bg-[var(--ink)] border border-white" />
            <span>Target Query Point</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-2.5 h-2.5 rounded-full bg-[#1B8755] border border-white" />
            <span>Potential Fishing Zone (PFZ)</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-2.5 h-2.5 rounded-full bg-[#0284C7] border border-white" />
            <span>SST & Anomaly (INCOIS ERDDAP — temperature only, no catch guarantee)</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-5 h-0.5 border-t-2 border-dashed border-[#DC2626]" />
            <span>IMBL Maritime Boundary</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-5 h-2 bg-[#0284C7]/20 border border-[#0284C7]" />
            <span>Safe Fairway Corridor (±0.5 NM)</span>
          </div>
        </div>
      )}
    </div>
  );
};
