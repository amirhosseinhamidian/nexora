"use client";

import { Languages, Moon, Sun } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useTheme } from "next-themes";
import { useSyncExternalStore } from "react";

import type { Locale } from "@/i18n/config";
import type { Dictionary } from "@/i18n/dictionaries";

type FoundationControlsProps = {
  dictionary: Dictionary["header"];
  locale: Locale;
};

export function FoundationControls({ dictionary, locale }: FoundationControlsProps) {
  const pathname = usePathname();
  const { resolvedTheme, setTheme } = useTheme();
  const mounted = useSyncExternalStore(
    () => () => undefined,
    () => true,
    () => false,
  );

  const nextLocale: Locale = locale === "fa" ? "en" : "fa";
  const segments = pathname.split("/");
  segments[1] = nextLocale;
  const localePath = segments.join("/") || `/${nextLocale}`;
  const isDark = mounted && resolvedTheme === "dark";

  return (
    <div className="foundation-controls">
      <Link
        aria-label={`${dictionary.language}: ${nextLocale.toUpperCase()}`}
        className="control-button"
        href={localePath}
        hrefLang={nextLocale}
      >
        <Languages aria-hidden="true" size={18} />
        <span>{nextLocale.toUpperCase()}</span>
      </Link>
      <button
        aria-label={`${dictionary.theme}: ${isDark ? dictionary.light : dictionary.dark}`}
        className="control-button icon-only"
        onClick={() => setTheme(isDark ? "light" : "dark")}
        type="button"
      >
        {isDark ? <Sun aria-hidden="true" size={18} /> : <Moon aria-hidden="true" size={18} />}
      </button>
    </div>
  );
}
