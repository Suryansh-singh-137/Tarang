"use client";

/**
 * WindLayer.tsx  (Canvas-based wind particle flow with fisherman advisory intelligence)
 * ──────────────────────────────────────────────────────────────────────────────────────
 * Renders two canvas layers appended directly to the Leaflet map container:
 *
 *  bgCanvas   (z-index 400) — Wind-speed color field sampled via IDW interpolation.
 *  ptCanvas   (z-index 410) — Animated particle flow trails showing wind direction & speed.
 *
 * DATA SOURCE: `/weather/wind-grid` backend endpoint (Open-Meteo ERA5-ICON).
 *
 * FISHERMAN VALUE:
 *  - Categorizes wind into intuitive safety states (Safe / Caution / Rough / Danger)
 *  - Calculates speed in both km/h and Knots
 *  - Identifies drift direction (where nets & boats will drift)
 *  - Provides actionable fishing advantages (net casting orientation, pelagic feeding, fuel savings)
 */

import { useEffect, useState } from "react";
import { fetchWindGridApi, WindPoint } from "@/lib/api";

// ─── Visual config ────────────────────────────────────────────────────────────
const PART_DESKTOP  = 160;    // particles on desktop
const PART_MOBILE   = 70;     // particles on mobile / small screen
const MAX_AGE       = 90;     // frames before particle resets
const SPEED_SCALE   = 0.0014; // degrees per frame per km/h (visual speed)
const TRAIL_KEEP    = 0.95;   // destination-in alpha per frame
const BG_ALPHA      = 148;    // 0-255 background color field opacity
const FIELD_COLS    = 100;    // offscreen bg field width (px)
const FIELD_ROWS    = 75;     // offscreen bg field height (px)
const GRID_N        = 4;      // 4×4 = 16 API wind sample points (fast & accurate)
const FETCH_THRESH  = 1.5;    // degrees of center shift before re-fetching

// ─── Color palette: blue → teal → green → yellow → orange → red ───────────────
const STOPS: [number, [number, number, number]][] = [
  [0,   [20,  80, 180]],   // deep navy blue  (calm: < 8 km/h)
  [8,   [40, 140, 195]],   // blue
  [15,  [55, 185, 185]],   // teal (light breeze)
  [22,  [80, 205, 130]],   // mint green (moderate)
  [28,  [185, 225,  75]],  // yellow-green
  [33,  [250, 180,  40]],  // amber (caution)
  [40,  [235,  75,  35]],  // red-orange (rough)
  [50,  [170,   0,  10]],  // deep red (gale/danger)
];

function sRgb(speed: number): [number, number, number] {
  const s = Math.max(0, Math.min(speed, 50));
  for (let i = 0; i < STOPS.length - 1; i++) {
    const [s1, c1] = STOPS[i], [s2, c2] = STOPS[i + 1];
    if (s <= s2) {
      const t = (s - s1) / (s2 - s1);
      return [
        (c1[0] + (c2[0] - c1[0]) * t) | 0,
        (c1[1] + (c2[1] - c1[1]) * t) | 0,
        (c1[2] + (c2[2] - c1[2]) * t) | 0,
      ];
    }
  }
  return STOPS[STOPS.length - 1][1];
}

// ─── IDW interpolation at a lat/lon point from the wind grid ─────────────────
function idw(lat: number, lon: number, pts: WindPoint[]) {
  if (!pts.length) return null;
  let uw = 0, vw = 0, tw = 0;
  for (const p of pts) {
    const d2 = (lat - p.lat) ** 2 + (lon - p.lon) ** 2;
    const w = d2 < 1e-8 ? 1e8 : 1 / d2;
    // Travel direction: FROM → +180°
    const trad = ((p.direction_deg + 180) % 360) * (Math.PI / 180);
    uw += w * p.speed_kmh * Math.sin(trad); // east component
    vw += w * p.speed_kmh * Math.cos(trad); // north component
    tw += w;
  }
  const u = uw / tw, v = vw / tw;
  return { u, v, speed: Math.hypot(u, v) };
}

// ─── 16 Compass Cardinals & Full Names ─────────────────────────────────────────
const CARD_16 = [
  { abbr: "N",   name: "North" },
  { abbr: "NNE", name: "North-Northeast" },
  { abbr: "NE",  name: "Northeast" },
  { abbr: "ENE", name: "East-Northeast" },
  { abbr: "E",   name: "East" },
  { abbr: "ESE", name: "East-Southeast" },
  { abbr: "SE",  name: "Southeast" },
  { abbr: "SSE", name: "South-Southeast" },
  { abbr: "S",   name: "South" },
  { abbr: "SSW", name: "South-Southwest" },
  { abbr: "SW",  name: "Southwest" },
  { abbr: "WSW", name: "West-Southwest" },
  { abbr: "W",   name: "West" },
  { abbr: "WNW", name: "West-Northwest" },
  { abbr: "NW",  name: "Northwest" },
  { abbr: "NNW", name: "North-Northwest" },
];

export function getCardinal(deg: number): string {
  const idx = Math.round(((deg % 360) + 360) % 360 / 22.5) % 16;
  return CARD_16[idx].abbr;
}

export function getCardinalName(deg: number): string {
  const idx = Math.round(((deg % 360) + 360) % 360 / 22.5) % 16;
  return CARD_16[idx].name;
}

// ─── Fisherman Marine Intelligence ───────────────────────────────────────────
export interface FishermanAdvisory {
  safetyStatus: "SAFE" | "CAUTION" | "ROUGH" | "DANGER";
  safetyTitle: string;
  safetyBadgeColor: string;
  safetyTextColor: string;
  safetyBorderColor: string;
  boatAdvisory: string;
  advantageTip: string;
  driftWarning: string;
  fuelTip: string;
  waveEstimate: string;
}

export function getFishermanAdvisory(speedKmh: number, fromDeg: number): FishermanAdvisory {
  const travelDeg = (fromDeg + 180) % 360;
  const toCard = getCardinal(travelDeg);
  const fromCard = getCardinal(fromDeg);

  if (speedKmh < 16) {
    return {
      safetyStatus: "SAFE",
      safetyTitle: "Calm Sea • Safe for All Fishing Boats",
      safetyBadgeColor: "#dcfce7",
      safetyTextColor: "#15803d",
      safetyBorderColor: "#86efac",
      boatAdvisory: "Safe for Catamarans, Country Craft, Fiber Boats & Trawlers.",
      advantageTip: "Calm surface: Ideal for near-shore gillnets, cast nets & squid jigging with minimal net drift.",
      driftWarning: `Gentle drift towards ${toCard}. Anchors and float-lines will stay firmly in position.`,
      fuelTip: "Minimal wind drag: Normal economical diesel consumption.",
      waveEstimate: "0.2 – 0.6 m (Smooth calm sea)",
    };
  } else if (speedKmh < 28) {
    return {
      safetyStatus: "CAUTION",
      safetyTitle: "Moderate Breeze • Caution for Small Craft",
      safetyBadgeColor: "#fef9c3",
      safetyTextColor: "#854d0e",
      safetyBorderColor: "#fde047",
      boatAdvisory: "Motorized fiber boats & mechanized trawlers safe. Small canoes stay near coast (< 3 nm).",
      advantageTip: `Wind concentrates pelagic fish (sardines/mackerel) along foam lines. Cast nets across wind.`,
      driftWarning: `Active drift towards ${toCard}. Keep boat positioned down-wind of nets to prevent tangling.`,
      fuelTip: `Heading into wind (${fromCard}) will burn ~15% more fuel. Return with tailwind when possible.`,
      waveEstimate: "0.8 – 1.4 m (Moderate chop & small whitecaps)",
    };
  } else if (speedKmh < 42) {
    return {
      safetyStatus: "ROUGH",
      safetyTitle: "Rough Sea • Small Boats Stay Inshore",
      safetyBadgeColor: "#ffedd5",
      safetyTextColor: "#c2410c",
      safetyBorderColor: "#fdba74",
      boatAdvisory: "Fiber boats (<28 ft) advised NOT to go to deep sea. Wear life jackets at all times.",
      advantageTip: "Fish take shelter in deeper water contours or behind headlands and island reefs.",
      driftWarning: `High drift towards ${toCard}! Surface nets risk dragging onto shallow reefs or breaking.`,
      fuelTip: `Heavy headwind against ${fromCard}. Angle across waves to protect engine and avoid hull slamming.`,
      waveEstimate: "1.5 – 2.5 m (Rough breaking waves)",
    };
  } else {
    return {
      safetyStatus: "DANGER",
      safetyTitle: "High Wind Alert • Do NOT Venture into Sea",
      safetyBadgeColor: "#fee2e2",
      safetyTextColor: "#b91c1c",
      safetyBorderColor: "#fca5a5",
      boatAdvisory: "DANGER OF BOAT CAPSIZING. INCOIS & Coast Guard red advisory. All vessels return to port.",
      advantageTip: "Extreme maritime risk. Suspend all net setting and hauling operations immediately.",
      driftWarning: `Gale-force drift towards ${toCard}. Severe danger of engine stall or being pushed onto rocks.`,
      fuelTip: "Steer directly towards nearest sheltered bay, creek, or harbor immediately.",
      waveEstimate: "> 2.8 m (Very rough to high gale sea)",
    };
  }
}

// ─── Public types ─────────────────────────────────────────────────────────────
export interface WindClickInfo {
  lat: number;
  lon: number;
  speedKmh: number;
  speedKnots: number;
  dirDeg: number;       // Meteorological FROM direction
  travelDeg: number;    // Direction wind travels TOWARD
  fromCardinal: string; // e.g. "WSW"
  fromName: string;     // e.g. "West-Southwest"
  toCardinal: string;   // e.g. "ENE"
  toName: string;       // e.g. "East-Northeast"
  advisory: FishermanAdvisory;
  sx: number;
  sy: number;
}

export interface WindLayerProps {
  mapRef: React.RefObject<any>;
  enabled: boolean;
  onWindInfo?: (info: WindClickInfo | null) => void;
}

// ─── Particle type (internal) ─────────────────────────────────────────────────
interface Particle {
  lat: number;
  lon: number;
  age: number;
  maxAge: number;
  prevX: number;
  prevY: number;
  speed: number;
}

// ─────────────────────────────────────────────────────────────────────────────
//  Canvas setup & lifecycle
// ─────────────────────────────────────────────────────────────────────────────
function setupWindCanvas(
  map: any,
  opts: {
    setLoading: (b: boolean) => void;
    setError: (s: string | null) => void;
    onWindInfo?: (info: WindClickInfo | null) => void;
  }
): () => void {
  const { setLoading, setError, onWindInfo } = opts;

  let cancelled = false;
  let rafId = 0;
  let pts: WindPoint[] = [];
  let particles: Particle[] = [];
  let bgDirty = true;
  let lastFetchLat = Infinity, lastFetchLon = Infinity;

  // ── Create canvases ──────────────────────────────────────────────────────
  const container = map.getContainer() as HTMLDivElement;

  const bgCanvas = document.createElement("canvas");
  bgCanvas.setAttribute("data-tarang", "wind-bg");
  bgCanvas.style.cssText =
    "position:absolute;top:0;left:0;width:100%;height:100%;pointer-events:none;z-index:400;";
  container.appendChild(bgCanvas);

  const ptCanvas = document.createElement("canvas");
  ptCanvas.setAttribute("data-tarang", "wind-particles");
  ptCanvas.style.cssText =
    "position:absolute;top:0;left:0;width:100%;height:100%;pointer-events:none;z-index:410;";
  container.appendChild(ptCanvas);

  // ── Size canvases to container ────────────────────────────────────────────
  function sizeCanvases() {
    const w = container.clientWidth, h = container.clientHeight;
    bgCanvas.width = w; bgCanvas.height = h;
    ptCanvas.width = w; ptCanvas.height = h;
    bgDirty = true;
    particles.forEach(p => { p.age = p.maxAge; });
  }
  sizeCanvases();

  let ro: ResizeObserver | null = null;
  if (typeof ResizeObserver !== "undefined") {
    ro = new ResizeObserver(sizeCanvases);
    ro.observe(container);
  }

  // ── Particle management ───────────────────────────────────────────────────
  function resetParticle(p: Particle) {
    const b = map.getBounds();
    p.lat = b.getSouth() + Math.random() * (b.getNorth() - b.getSouth());
    p.lon = b.getWest()  + Math.random() * (b.getEast()  - b.getWest());
    p.age = 0;
    p.maxAge = MAX_AGE * (0.55 + Math.random() * 0.9);
    const pt = map.latLngToContainerPoint([p.lat, p.lon]);
    p.prevX = pt.x; p.prevY = pt.y;
    p.speed = 0;
  }

  function seedParticles() {
    const n = (typeof window !== "undefined" && window.innerWidth < 768)
      ? PART_MOBILE : PART_DESKTOP;
    particles = Array.from({ length: n }, (): Particle => ({
      lat: 0, lon: 0, age: MAX_AGE, maxAge: MAX_AGE,
      prevX: -999, prevY: -999, speed: 0,
    }));
  }

  // ── Wind data fetch ───────────────────────────────────────────────────────
  async function fetchData() {
    if (cancelled || !map) return;
    const b = map.getBounds();
    const cLat = (b.getSouth() + b.getNorth()) / 2;
    const cLon = (b.getWest()  + b.getEast())  / 2;
    const dist = Math.hypot(cLat - lastFetchLat, cLon - lastFetchLon);
    if (dist < FETCH_THRESH && pts.length > 0) return; // already populated

    setLoading(true);
    setError(null);

    // Compute safe, clamped bounding box
    let s = b.getSouth();
    let n = b.getNorth();
    let w = b.getWest();
    let e = b.getEast();

    // If zoomed far out, clamp span around viewport center to 30° to keep fetch fast
    if ((n - s) > 30) {
      s = cLat - 15;
      n = cLat + 15;
    }
    if ((e - w) > 30) {
      w = cLon - 15;
      e = cLon + 15;
    }

    s = Math.max(-85, s - 0.5);
    n = Math.min(85, n + 0.5);
    w = Math.max(-180, w - 0.5);
    e = Math.min(180, e + 0.5);

    try {
      const res = await fetchWindGridApi(s, n, w, e, GRID_N);
      if (cancelled) return;
      if (res?.points && res.points.length > 0) {
        pts = res.points;
        lastFetchLat = cLat;
        lastFetchLon = cLon;
        bgDirty = true;
        setError(null);
      } else {
        if (pts.length === 0) {
          setError("No wind data available for this region");
        }
      }
    } catch {
      if (!cancelled && pts.length === 0) {
        setError("Wind data temporarily unavailable");
      }
    } finally {
      if (!cancelled) setLoading(false);
    }
  }

  // ── Draw background color field (once per data/bounds change) ────────────
  function drawBg() {
    if (!bgDirty || !pts.length) return;
    const ctx = bgCanvas.getContext("2d")!;
    const W = bgCanvas.width, H = bgCanvas.height;
    if (W === 0 || H === 0) return;

    const offC = document.createElement("canvas");
    offC.width = FIELD_COLS; offC.height = FIELD_ROWS;
    const offCtx = offC.getContext("2d")!;
    const img = offCtx.createImageData(FIELD_COLS, FIELD_ROWS);
    const d = img.data;

    for (let row = 0; row < FIELD_ROWS; row++) {
      for (let col = 0; col < FIELD_COLS; col++) {
        const cssX = (col / (FIELD_COLS - 1)) * W;
        const cssY = (row / (FIELD_ROWS - 1)) * H;
        const ll = map.containerPointToLatLng([cssX, cssY]);
        const w = idw(ll.lat, ll.lng, pts);
        if (!w) continue;
        const [r, g, b] = sRgb(w.speed);
        const i = (row * FIELD_COLS + col) * 4;
        d[i] = r; d[i + 1] = g; d[i + 2] = b; d[i + 3] = BG_ALPHA;
      }
    }
    offCtx.putImageData(img, 0, 0);

    ctx.clearRect(0, 0, W, H);
    ctx.imageSmoothingEnabled = true;
    ctx.imageSmoothingQuality = "high";
    ctx.drawImage(offC, 0, 0, W, H);
    bgDirty = false;
  }

  // ── Animation loop ────────────────────────────────────────────────────────
  function animate() {
    if (cancelled) return;

    drawBg();

    const ctx = ptCanvas.getContext("2d")!;
    const W = ptCanvas.width, H = ptCanvas.height;
    if (W === 0 || H === 0) {
      rafId = requestAnimationFrame(animate);
      return;
    }

    // Fade old trails: destination-in preserves existing pixel alpha × fill alpha
    ctx.globalCompositeOperation = "destination-in";
    ctx.fillStyle = `rgba(0,0,0,${TRAIL_KEEP})`;
    ctx.fillRect(0, 0, W, H);
    ctx.globalCompositeOperation = "source-over";

    if (pts.length > 0) {
      const b = map.getBounds();
      const latMin = b.getSouth(), latMax = b.getNorth();
      const lonMin = b.getWest(),  lonMax = b.getEast();

      for (const p of particles) {
        const oob =
          p.lat < latMin - 1.0 || p.lat > latMax + 1.0 ||
          p.lon < lonMin - 1.0 || p.lon > lonMax + 1.0;

        if (p.age >= p.maxAge || oob) {
          resetParticle(p);
          continue;
        }

        const wind = idw(p.lat, p.lon, pts);
        if (!wind || wind.speed < 0.2) { p.age++; continue; }

        const pt0 = map.latLngToContainerPoint([p.lat, p.lon]);

        p.lat += wind.v * SPEED_SCALE;
        p.lon += wind.u * SPEED_SCALE;
        p.age++;
        p.speed = wind.speed;

        const pt1 = map.latLngToContainerPoint([p.lat, p.lon]);

        const lt = p.age / p.maxAge;
        const alpha = Math.min(lt * 4, 1) * Math.min((1 - lt) * 4, 1) * 0.92;
        const [r, g, b] = sRgb(wind.speed);

        ctx.beginPath();
        ctx.strokeStyle = `rgba(${r},${g},${b},${alpha})`;
        ctx.lineWidth = 1.6;
        ctx.lineCap = "round";
        ctx.moveTo(pt0.x, pt0.y);
        ctx.lineTo(pt1.x, pt1.y);
        ctx.stroke();

        p.prevX = pt1.x;
        p.prevY = pt1.y;
      }
    }

    rafId = requestAnimationFrame(animate);
  }

  // ── Map event handlers ────────────────────────────────────────────────────
  const onMoveEnd = () => {
    bgDirty = true;
    fetchData();
  };
  const onZoomEnd = () => {
    bgDirty = true;
    particles.forEach(p => { p.age = p.maxAge; });
    fetchData();
  };

  // Click on map → calculate localized fisherman advisory
  const onClick = (e: any) => {
    if (!onWindInfo || !pts.length) return;
    const wind = idw(e.latlng.lat, e.latlng.lng, pts);
    if (!wind) {
      onWindInfo(null);
      return;
    }

    const travelDir = (Math.atan2(wind.u, wind.v) * 180 / Math.PI + 360) % 360;
    const fromDir   = (travelDir + 180) % 360;
    const speedKmh  = Math.round(wind.speed * 10) / 10;
    const speedKnots = Math.round(wind.speed * 0.539957 * 10) / 10;

    const advisory = getFishermanAdvisory(speedKmh, fromDir);

    onWindInfo({
      lat: e.latlng.lat,
      lon: e.latlng.lng,
      speedKmh,
      speedKnots,
      dirDeg: fromDir,
      travelDeg: travelDir,
      fromCardinal: getCardinal(fromDir),
      fromName: getCardinalName(fromDir),
      toCardinal: getCardinal(travelDir),
      toName: getCardinalName(travelDir),
      advisory,
      sx: e.containerPoint.x,
      sy: e.containerPoint.y,
    });
  };

  map.on("moveend", onMoveEnd);
  map.on("zoomend", onZoomEnd);
  map.on("click", onClick);

  // ── Kick off ──────────────────────────────────────────────────────────────
  seedParticles();
  fetchData().then(() => {
    if (!cancelled) animate();
  });

  // ── Return cleanup ────────────────────────────────────────────────────────
  return () => {
    cancelled = true;
    cancelAnimationFrame(rafId);
    ro?.disconnect();
    bgCanvas.remove();
    ptCanvas.remove();
    map.off("moveend", onMoveEnd);
    map.off("zoomend", onZoomEnd);
    map.off("click", onClick);
  };
}

// ─────────────────────────────────────────────────────────────────────────────
//  React component
// ─────────────────────────────────────────────────────────────────────────────
export function WindLayer({ mapRef, enabled, onWindInfo }: WindLayerProps) {
  const [loading, setLoading] = useState(false);
  const [error, setError]     = useState<string | null>(null);

  useEffect(() => {
    if (!enabled) return;
    const map = mapRef.current;
    if (!map) return;

    const cleanup = setupWindCanvas(map, { setLoading, setError, onWindInfo });
    return cleanup;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled]);

  if (!enabled) return null;

  return (
    <>
      {loading && (
        <div
          style={{
            position: "absolute", bottom: 52, left: 12, zIndex: 1001,
            background: "rgba(255,255,255,0.95)", backdropFilter: "blur(6px)",
            border: "1px solid #bae6fd", borderRadius: 8,
            padding: "5px 12px", fontSize: 11, color: "#0369a1",
            fontWeight: 600, display: "flex", alignItems: "center",
            gap: 7, pointerEvents: "none", boxShadow: "0 2px 8px rgba(0,0,0,0.08)",
          }}
        >
          <span style={{ display: "inline-block", animation: "spin 1.2s linear infinite" }}>⟳</span>
          Loading live marine wind…
        </div>
      )}
      {error && !loading && (
        <div
          style={{
            position: "absolute", bottom: 52, left: 12, zIndex: 1001,
            background: "rgba(255,255,255,0.95)", backdropFilter: "blur(6px)",
            border: "1px solid #fde68a", borderRadius: 8,
            padding: "6px 12px", fontSize: 11, color: "#92400e",
            fontWeight: 500, pointerEvents: "auto",
            boxShadow: "0 2px 8px rgba(0,0,0,0.08)",
            display: "flex", alignItems: "center", gap: 8,
          }}
        >
          <span>⚠ {error}</span>
          <button
            type="button"
            onClick={() => {
              setError(null);
              setLoading(true);
              const map = mapRef.current;
              if (map) {
                const b = map.getBounds();
                fetchWindGridApi(
                  Math.max(-85, b.getSouth()), Math.min(85, b.getNorth()),
                  Math.max(-180, b.getWest()), Math.min(180, b.getEast()),
                  GRID_N
                ).then(res => {
                  setLoading(false);
                  if (!res?.points?.length) setError("No wind data available for this region");
                }).catch(() => {
                  setLoading(false);
                  setError("Wind data temporarily unavailable");
                });
              }
            }}
            className="bg-amber-100 hover:bg-amber-200 text-amber-900 px-2 py-0.5 rounded font-semibold text-[10px] cursor-pointer"
          >
            Retry
          </button>
        </div>
      )}
    </>
  );
}
