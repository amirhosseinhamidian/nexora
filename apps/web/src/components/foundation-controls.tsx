"use client";

import { IconButton } from "@nexora/ui/primitives";
import { Languages, Moon, Sun } from "lucide-react";
import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import { useTheme } from "next-themes";
import { useSyncExternalStore } from "react";

import type { Locale } from "@/i18n/config";
import type { Dictionary } from "@/i18n/dictionaries";
import { rememberLocale } from "@/lib/display-preferences";

type FoundationControlsProps = {
  dictionary: Dictionary["header"];
  locale: Locale;
};

export function FoundationControls({ dictionary, locale }: FoundationControlsProps) {
  const pathname = usePathname();
  const search = useSearchParams().toString();
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
        aria-label={`${dictionary.language}: ${dictionary.locales[nextLocale]}`}
        className="control-button"
        href={search ? `${localePath}?${search}` : localePath}
        hrefLang={nextLocale}
        onNavigate={() => rememberLocale(nextLocale)}
      >
        <Languages aria-hidden="true" size={18} />
        <bdi lang={nextLocale}>{dictionary.locales[nextLocale]}</bdi>
      </Link>
      <IconButton
        variant="ghost"
        aria-label={`${dictionary.theme}: ${isDark ? dictionary.light : dictionary.dark}`}
        className="control-button icon-only"
        onClick={() => setTheme(isDark ? "light" : "dark")}
        type="button"
      >
        {isDark ? <Sun aria-hidden="true" size={18} /> : <Moon aria-hidden="true" size={18} />}
      </IconButton>
    </div>
  );
}
