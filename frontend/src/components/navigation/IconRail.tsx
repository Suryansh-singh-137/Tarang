import React from "react";
import { MessageSquare, Map as MapIcon, Fish, Compass, AlertTriangle } from "lucide-react";

export type ActiveTab = "chat" | "map" | "pfz" | "trip" | "alerts" | "trace";

interface Props {
  activeTab: ActiveTab;
  onSelectTab: (tab: ActiveTab) => void;
  hasMapData?: boolean;
  hasActiveAlert?: boolean;
  hasTraceData?: boolean;
  className?: string;
}

interface NavItem {
  id: ActiveTab;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  hasIndicator?: boolean;
  indicatorColor?: string;
}

export const IconRail: React.FC<Props> = ({
  activeTab,
  onSelectTab,
  hasMapData = false,
  hasActiveAlert = false,
  hasTraceData = false,
  className = "",
}) => {
  const items: NavItem[] = [
    {
      id: "chat",
      label: "Ask Tarang",
      icon: MessageSquare,
    },
    {
      id: "map",
      label: "Marine Map",
      icon: MapIcon,
      hasIndicator: hasMapData,
      indicatorColor: "bg-[var(--current)]",
    },
    {
      id: "pfz",
      label: "Fishing Zones",
      icon: Fish,
    },
    {
      id: "trip",
      label: "Trip Planner",
      icon: Compass,
    },
    {
      id: "alerts",
      label: "Safety & Alerts",
      icon: AlertTriangle,
      hasIndicator: hasActiveAlert,
      indicatorColor: "bg-[#D97706] animate-pulse",
    },
  ];

  return (
    <>
      {/* ── Desktop Icon Rail (≥768px) ── */}
      <aside
        className={`hidden md:flex flex-col items-center justify-between w-16 h-full bg-[var(--surface)] border-r border-[var(--border)] py-5 shrink-0 z-20 select-none ${className}`}
        aria-label="Application navigation rail"
      >
        <div className="flex flex-col items-center gap-3 w-full">
          {items.map((item) => {
            const Icon = item.icon;
            const isActive = activeTab === item.id;

            return (
              <button
                key={item.id}
                type="button"
                onClick={() => onSelectTab(item.id)}
                className={`group relative w-12 h-12 min-w-[48px] min-h-[48px] rounded-xl flex items-center justify-center transition-all cursor-pointer ${
                  isActive
                    ? "bg-[var(--foam)] text-[var(--current)] font-semibold shadow-2xs"
                    : "text-[var(--ink-muted)] hover:text-[var(--ink)] hover:bg-[var(--surface-muted)]"
                }`}
                title={item.label}
                aria-label={item.label}
                aria-current={isActive ? "page" : undefined}
              >
                <Icon className={`w-5 h-5 transition-transform group-hover:scale-105 ${isActive ? "stroke-[2.2]" : "stroke-[1.7]"}`} />

                {/* Unobtrusive indicator badge */}
                {item.hasIndicator && (
                  <span
                    className={`absolute top-2.5 right-2.5 w-2 h-2 rounded-full ${item.indicatorColor || "bg-[var(--current)]"} ring-2 ring-white`}
                    aria-label={`${item.label} updated`}
                  />
                )}

                {/* Subtle active left indicator bar */}
                {isActive && (
                  <span
                    className="absolute left-0 top-3 bottom-3 w-0.5 bg-[var(--current)] rounded-r-full"
                    aria-hidden="true"
                  />
                )}
              </button>
            );
          })}
        </div>

        {/* Bottom indicator / status */}
        <div className="flex flex-col items-center gap-2">
          <span
            className="w-2 h-2 rounded-full bg-[#1B8755]"
            title="System operational"
            aria-label="System operational"
          />
        </div>
      </aside>

      {/* ── Mobile Bottom Tab Bar (<768px) ── */}
      <nav
        className="md:hidden fixed bottom-0 left-0 right-0 h-14 bg-[var(--surface)] border-t border-[var(--border)] flex items-center justify-around z-30 shadow-lg px-2 select-none"
        aria-label="Mobile navigation tab bar"
      >
        {items.map((item) => {
          const Icon = item.icon;
          const isActive = activeTab === item.id;

          return (
            <button
              key={item.id}
              type="button"
              onClick={() => onSelectTab(item.id)}
              className={`relative flex flex-col items-center justify-center flex-1 h-full min-h-[48px] transition-colors cursor-pointer ${
                isActive ? "text-[var(--current)] font-semibold" : "text-[var(--ink-muted)]"
              }`}
              aria-label={item.label}
              aria-current={isActive ? "page" : undefined}
            >
              <div className="relative">
                <Icon className={`w-5 h-5 ${isActive ? "stroke-[2.2]" : "stroke-[1.7]"}`} />
                {item.hasIndicator && (
                  <span
                    className={`absolute -top-0.5 -right-0.5 w-2 h-2 rounded-full ${item.indicatorColor || "bg-[var(--current)]"} ring-1 ring-white`}
                  />
                )}
              </div>
              <span className="text-[10px] mt-0.5 font-sans">{item.label.split(" ")[0]}</span>
            </button>
          );
        })}
      </nav>
    </>
  );
};
