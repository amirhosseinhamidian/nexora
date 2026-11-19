"use client";

import { createContext, useContext } from "react";

import type { Locale } from "@/i18n/config";
import { formatTimestamp } from "@/lib/portfolio-analytics";

export const WorkspaceTimeZone = createContext<string | undefined>(undefined);
export function useWorkspaceTimeZone() {
  return useContext(WorkspaceTimeZone);
}

export function WorkspaceTime({ dateTime, locale }: { dateTime: string; locale: Locale }) {
  const timeZone = useWorkspaceTimeZone();
  return <time dateTime={dateTime}>{formatTimestamp(dateTime, locale, timeZone)}</time>;
}
