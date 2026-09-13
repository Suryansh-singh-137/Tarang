import React from "react";

interface Props {
  className?: string;
  width?: number;
  height?: number;
}

export const DriftingWaves: React.FC<Props> = ({
  className = "w-48 h-auto",
  width = 200,
  height = 54,
}) => {
  return (
    <svg
      viewBox="0 0 200 54"
      width={width}
      height={height}
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      aria-label="Calm marine waves thinking animation"
      role="img"
    >
      <defs>
        <linearGradient id="waveGrad" x1="0" y1="0" x2="200" y2="0" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stopColor="#2E8FA0" stopOpacity="0.1" />
          <stop offset="50%" stopColor="#2E8FA0" stopOpacity="0.8" />
          <stop offset="100%" stopColor="#2E8FA0" stopOpacity="0.1" />
        </linearGradient>
        <linearGradient id="mistGrad" x1="0" y1="0" x2="200" y2="0" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stopColor="#E88F5C" stopOpacity="0.1" />
          <stop offset="50%" stopColor="#E88F5C" stopOpacity="0.6" />
          <stop offset="100%" stopColor="#E88F5C" stopOpacity="0.1" />
        </linearGradient>
      </defs>

      {/* Top gentle drifting mist */}
      <path
        d="M-20 14 Q30 8 80 14 T180 14 T280 14"
        stroke="url(#mistGrad)"
        strokeWidth="2.5"
        strokeLinecap="round"
      >
        <animateTransform
          attributeName="transform"
          type="translate"
          values="0,0; -40,0; 0,0"
          dur="5s"
          repeatCount="indefinite"
        />
      </path>

      {/* Primary wave line */}
      <path
        d="M-40 28 Q10 20 60 28 T160 28 T260 28"
        stroke="url(#waveGrad)"
        strokeWidth="3"
        strokeLinecap="round"
      >
        <animateTransform
          attributeName="transform"
          type="translate"
          values="0,0; 30,0; 0,0"
          dur="4s"
          repeatCount="indefinite"
        />
      </path>

      {/* Lower subtle wave line */}
      <path
        d="M-10 42 Q40 36 90 42 T190 42 T290 42"
        stroke="#DCEFEE"
        strokeWidth="2"
        strokeLinecap="round"
      >
        <animateTransform
          attributeName="transform"
          type="translate"
          values="0,0; -25,0; 0,0"
          dur="6s"
          repeatCount="indefinite"
        />
      </path>
    </svg>
  );
};
