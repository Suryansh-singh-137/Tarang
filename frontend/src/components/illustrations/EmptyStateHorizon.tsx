import React from "react";

interface Props {
  className?: string;
  width?: number;
  height?: number;
}

/**
 * EmptyStateHorizon — Editorial coastal horizon linework illustration.
 *
 * Strict PRD rules:
 * - NO container, NO border, NO bounding rectangle fill. Bleeds directly into page background.
 * - Uniform 1.5px stroke weight across EVERY line (sun, boat, horizon lines, waves, birds).
 * - Palette strictly drawn from token set:
 *     --ink: #16242B
 *     --current: #2E8FA0
 *     --dawn: #E88F5C
 *     --foam: #DCEFEE
 */
export const EmptyStateHorizon: React.FC<Props> = ({
  className = "w-full max-w-sm h-auto",
  width = 320,
  height = 150,
}) => {
  return (
    <svg
      viewBox="0 0 320 150"
      width={width}
      height={height}
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      aria-label="Coastal dawn horizon with fishing boat silhouette in 1.5px linework"
      role="img"
    >
      {/* ── Distant Birds in Flight (1.5px stroke linework in --ink) ── */}
      <path
        d="M 62 34 Q 68 28 74 34 Q 80 28 86 34"
        stroke="#16242B"
        strokeWidth="1.5"
        strokeLinecap="round"
        fill="none"
        strokeOpacity="0.75"
      />
      <path
        d="M 88 24 Q 93 19 98 24 Q 103 19 108 24"
        stroke="#16242B"
        strokeWidth="1.5"
        strokeLinecap="round"
        fill="none"
        strokeOpacity="0.5"
      />

      {/* ── Sun Disc low on Horizon (1.5px stroke in --dawn) ── */}
      {/* Subtle warm halo */}
      <circle
        cx="145"
        cy="86"
        r="26"
        stroke="#E88F5C"
        strokeWidth="1.5"
        strokeOpacity="0.85"
        fill="#E88F5C"
        fillOpacity="0.08"
      />
      {/* Concentric sun ray arcs */}
      <path
        d="M 112 86 A 33 33 0 0 1 178 86"
        stroke="#E88F5C"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeOpacity="0.35"
        strokeDasharray="4 6"
        fill="none"
      />

      {/* ── Continuous Horizon Line (1.5px stroke in --current) ── */}
      <line
        x1="12"
        y1="86"
        x2="308"
        y2="86"
        stroke="#2E8FA0"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeOpacity="0.9"
      />

      {/* ── Coastal Fishing Boat Silhouette (1.5px stroke in --ink) ── */}
      <g transform="translate(196, 52)" className="animate-boat-bob">
        {/* Main mast */}
        <line
          x1="22"
          y1="4"
          x2="22"
          y2="34"
          stroke="#16242B"
          strokeWidth="1.5"
          strokeLinecap="round"
        />
        {/* Fore stay & Back stay */}
        <line
          x1="22"
          y1="8"
          x2="36"
          y2="34"
          stroke="#16242B"
          strokeWidth="1.5"
          strokeLinecap="round"
          strokeOpacity="0.8"
        />
        <line
          x1="22"
          y1="10"
          x2="7"
          y2="34"
          stroke="#16242B"
          strokeWidth="1.5"
          strokeLinecap="round"
          strokeOpacity="0.8"
        />
        {/* Sail linework contour */}
        <path
          d="M 22 9 L 34 30 L 22 31 Z"
          stroke="#16242B"
          strokeWidth="1.5"
          strokeLinejoin="round"
          fill="#16242B"
          fillOpacity="0.08"
        />
        {/* Masthead pennant in --dawn */}
        <path
          d="M 22 4 L 28 7 L 22 10 Z"
          stroke="#E88F5C"
          strokeWidth="1.5"
          strokeLinejoin="round"
          fill="#E88F5C"
        />
        {/* Boat hull contour */}
        <path
          d="M 4 34 C 10 34 36 34 42 34 C 47 34 49 39 44 40 C 38 41 9 41 3 40 C -1 39 0 34 4 34 Z"
          stroke="#16242B"
          strokeWidth="1.5"
          strokeLinejoin="round"
          fill="#16242B"
        />
      </g>

      {/* ── Rhythmic Sea Swell Waves below Horizon (1.5px stroke in --current / --foam) ── */}
      {/* Primary surface wave */}
      <path
        d="M 24 99 Q 64 95 104 99 T 184 99 T 264 99 T 304 99"
        stroke="#2E8FA0"
        strokeWidth="1.5"
        strokeLinecap="round"
        fill="none"
        strokeOpacity="0.8"
      />
      {/* Secondary swell wave */}
      <path
        d="M 48 112 Q 98 108 148 112 T 248 112 T 292 112"
        stroke="#2E8FA0"
        strokeWidth="1.5"
        strokeLinecap="round"
        fill="none"
        strokeOpacity="0.55"
      />
      {/* Deep water tide line */}
      <path
        d="M 18 126 Q 78 122 138 126 T 258 126"
        stroke="#2E8FA0"
        strokeWidth="1.5"
        strokeLinecap="round"
        fill="none"
        strokeOpacity="0.35"
      />
      {/* Gentle shoreline ripple */}
      <path
        d="M 82 139 Q 132 136 182 139 T 242 139"
        stroke="#2E8FA0"
        strokeWidth="1.5"
        strokeLinecap="round"
        fill="none"
        strokeOpacity="0.2"
      />
    </svg>
  );
};
