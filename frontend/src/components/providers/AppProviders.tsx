"use client";

import React from "react";
import { LocationProvider } from "@/lib/locationContext";

export function AppProviders({ children }: { children: React.ReactNode }) {
  return <LocationProvider>{children}</LocationProvider>;
}
