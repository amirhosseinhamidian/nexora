import type { Locale } from "@/i18n/config";

export const displayTimeZones = [
  "browser",
  "UTC",
  "Asia/Tehran",
  "Europe/London",
  "America/New_York",
] as const;
export type DisplayTimeZone = (typeof displayTimeZones)[number];
export type DisplayPreferences = { sidebarCollapsed: boolean; timeZone: DisplayTimeZone };

export const defaultDisplayPreferences: DisplayPreferences = {
  sidebarCollapsed: false,
  timeZone: "browser",
};
export const LOCALE_PREFERENCE_COOKIE = "nexora-locale";

export function rememberLocale(locale: Locale) {
  document.cookie = `${LOCALE_PREFERENCE_COOKIE}=${locale}; Path=/; Max-Age=31536000; SameSite=Lax${window.location.protocol === "https:" ? "; Secure" : ""}`;
}

export function isDisplayTimeZone(value: unknown): value is DisplayTimeZone {
  return displayTimeZones.some((zone) => zone === value);
}

function preferenceKey(ownerId: string) {
  return `nexora-display-preferences-v1:${ownerId}`;
}

export function readDisplayPreferences(ownerId: string): DisplayPreferences {
  try {
    const stored = JSON.parse(
      localStorage.getItem(preferenceKey(ownerId)) ?? "null",
    ) as Partial<DisplayPreferences> | null;
    return {
      sidebarCollapsed: stored?.sidebarCollapsed === true,
      timeZone: isDisplayTimeZone(stored?.timeZone) ? stored.timeZone : "browser",
    };
  } catch {
    return defaultDisplayPreferences;
  }
}

export function writeDisplayPreferences(ownerId: string, preferences: DisplayPreferences): boolean {
  try {
    localStorage.setItem(preferenceKey(ownerId), JSON.stringify(preferences));
    return true;
  } catch {
    return false;
  }
}
