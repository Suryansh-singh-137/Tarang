import React from "react";

interface Props {
  className?: string;
  size?: number;
}

export const SonarRipples: React.FC<Props> = ({
  className = "w-28 h-28",
  size = 112,
}) => {
  return (
    <svg
      viewBox="0 0 120 120"
      width={size}
      height={size}
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      aria-label="Active sonar ripples listening animation"
      role="img"
    >
      <defs>
        <radialGradient id="sonarGlow" cx="0.5" cy="0.5" r="0.5">
          <stop offset="0%" stopColor="#E88F5C" stopOpacity="0.8" />
          <stop offset="40%" stopColor="#2E8FA0" stopOpacity="0.4" />
          <stop offset="100%" stopColor="#2E8FA0" stopOpacity="0" />
        </radialGradient>
      </defs>

      {/* Outermost ring */}
      <circle
        cx="60"
        cy="60"
        r="54"
        stroke="#2E8FA0"
        strokeWidth="1.2"
        strokeOpacity="0.25"
        strokeDasharray="4 4"
      >
        <animate
          attributeName="r"
          values="45;58;45"
          dur="3.2s"
          repeatCount="indefinite"
        />
        <animate
          attributeName="stroke-opacity"
          values="0.4;0.1;0.4"
          dur="3.2s"
          repeatCount="indefinite"
        />
      </circle>

      {/* Mid outer ring */}
      <circle
        cx="60"
        cy="60"
        r="42"
        stroke="#2E8FA0"
        strokeWidth="1.5"
        strokeOpacity="0.45"
      >
        <animate
          attributeName="r"
          values="34;46;34"
          dur="2.4s"
          repeatCount="indefinite"
        />
        <animate
          attributeName="stroke-opacity"
          values="0.6;0.2;0.6"
          dur="2.4s"
          repeatCount="indefinite"
        />
      </circle>

      {/* Mid inner ring */}
      <circle
        cx="60"
        cy="60"
        r="28"
        stroke="#E88F5C"
        strokeWidth="1.8"
        strokeOpacity="0.6"
      >
        <animate
          attributeName="r"
          values="22;32;22"
          dur="1.8s"
          repeatCount="indefinite"
        />
        <animate
          attributeName="stroke-opacity"
          values="0.8;0.3;0.8"
          dur="1.8s"
          repeatCount="indefinite"
        />
      </circle>

      {/* Glowing inner core */}
      <circle cx="60" cy="60" r="16" fill="url(#sonarGlow)" />

      {/* Core beacon dot */}
      <circle cx="60" cy="60" r="7" fill="#E88F5C">
        <animate
          attributeName="transform"
          type="scale"
          values="1;1.15;1"
          dur="1.2s"
          repeatCount="indefinite"
          transform-origin="60 60"
        />
      </circle>
    </svg>
  );
};
