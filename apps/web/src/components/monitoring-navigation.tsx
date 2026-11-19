import Link from "next/link";

import type { Locale } from "@/i18n/config";
import type { Dictionary } from "@/i18n/dictionaries";
import { alertsHref, watchlistsHref } from "@/lib/monitoring";

export function MonitoringNavigation({
  copy,
  locale,
  view,
  watchlist,
}: {
  copy: Dictionary["monitoring"];
  locale: Locale;
  view: "alerts" | "watchlists";
  watchlist?: string;
}) {
  return (
    <nav aria-label={copy.navigation} className="accounting-navigation">
      <Link
        aria-current={view === "alerts" ? "page" : undefined}
        href={alertsHref(locale, { watchlist })}
      >
        {copy.inbox}
      </Link>
      <Link
        aria-current={view === "watchlists" ? "page" : undefined}
        href={watchlistsHref(locale, watchlist)}
      >
        {copy.watchlists}
      </Link>
    </nav>
  );
}
