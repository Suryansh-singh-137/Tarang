import React from "react";

interface Props {
  className?: string;
  size?: number;
}

export const ShorelineCompass: React.FC<Props> = ({
  className = "w-36 h-36",
  size = 144,
}) => {
  return (
    <svg
      viewBox="0 0 160 160"
      width={size}
      height={size}
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      aria-label="Shoreline and navigation compass invitation illustration"
      role="img"
    >
      <defs>
        <linearGradient id="shoreWater" x1="0" y1="80" x2="160" y2="160" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stopColor="#DCEFEE" />
          <stop offset="60%" stopColor="#2E8FA0" stopOpacity="0.4" />
          <stop offset="100%" stopColor="#2E8FA0" stopOpacity="0.8" />
        </linearGradient>
      </defs>

      {/* Coastal water curve */}
      <path
        d="M10 140 C50 110 90 145 150 115 L150 160 L10 160 Z"
        fill="url(#shoreWater)"
        opacity="0.85"
      />

      {/* Shoreline sand boundary curve */}
      <path
        d="M5 140 C48 108 88 144 155 113"
        stroke="#E88F5C"
        strokeWidth="2"
        strokeDasharray="4 3"
      />

      {/* Outer compass boundary circle */}
      <circle cx="80" cy="72" r="48" stroke="#EDEEEA" strokeWidth="2" />
      <circle cx="80" cy="72" r="44" stroke="#2E8FA0" strokeWidth="1" strokeOpacity="0.3" strokeDasharray="3 3" />

      {/* Cardinal tick marks */}
      <line x1="80" y1="26" x2="80" y2="34" stroke="#16242B" strokeWidth="2" strokeLinecap="round" />
      <line x1="80" y1="110" x2="80" y2="118" stroke="#16242B" strokeWidth="1.5" strokeLinecap="round" />
      <line x1="34" y1="72" x2="42" y2="72" stroke="#16242B" strokeWidth="1.5" strokeLinecap="round" />
      <line x1="118" y1="72" x2="126" y2="72" stroke="#16242B" strokeWidth="1.5" strokeLinecap="round" />

      {/* 'N' marker on compass */}
      <text
        x="80"
        y="22"
        textAnchor="middle"
        fontSize="11"
        fontFamily="sans-serif"
        fontWeight="700"
        fill="#2E8FA0"
      >
        N
      </text>

      {/* Compass Needle (North in Dawn orange, South in muted ink) */}
      <polygon points="80,36 85,72 80,68" fill="#E88F5C" />
      <polygon points="80,36 75,72 80,68" fill="#D77B46" />
      <polygon points="80,108 85,72 80,76" fill="#8A9CA5" />
      <polygon points="80,108 75,72 80,76" fill="#52656E" />

      {/* Central pivot circle */}
      <circle cx="80" cy="72" r="5" fill="#FFFFFF" stroke="#16242B" strokeWidth="1.8" />
      <circle cx="80" cy="72" r="2" fill="#E88F5C" />

      {/* Gentle water riplets below compass */}
      <path d="M40 148 Q60 145 80 148" stroke="#FFFFFF" strokeWidth="1.5" strokeLinecap="round" strokeOpacity="0.7" />
      <path d="M95 142 Q115 139 135 142" stroke="#FFFFFF" strokeWidth="1.5" strokeLinecap="round" strokeOpacity="0.7" />
    </svg>
  );
};
