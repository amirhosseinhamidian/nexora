"use client";

import {
  Bell,
  BookOpen,
  BriefcaseBusiness,
  Download,
  FileChartColumn,
  LayoutDashboard,
  List,
  SlidersHorizontal,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import type { Locale } from "@/i18n/config";
import type { Dictionary } from "@/i18n/dictionaries";

const destinations = [
  { segment: "overview", label: "overview", icon: LayoutDashboard },
  { segment: "portfolios", label: "portfolio", icon: BriefcaseBusiness },
  { segment: "transactions", label: "transactions", icon: List },
  { segment: "decisions", label: "decisions", icon: FileChartColumn },
  { segment: "alerts", label: "alerts", icon: Bell },
  { segment: "journal", label: "journal", icon: BookOpen },
  { segment: "exports", label: "exports", icon: Download },
  { segment: "settings", label: "settings", icon: SlidersHorizontal },
] as const;

export function WorkspaceNavigation({
  dictionary,
  locale,
  onNavigate,
}: {
  dictionary: Dictionary;
  locale: Locale;
  onNavigate?: () => void;
}) {
  const pathname = usePathname();

  return (
    <nav aria-label={dictionary.workspacePages.navigationLabel}>
      <ul className="navigation-list">
        {destinations.map(({ segment, label, icon: Icon }) => {
          const href = `/${locale}/${segment}`;
          const current = pathname === href;
          const active = current || pathname.startsWith(`${href}/`);
          return (
            <li key={segment}>
              <Link
                aria-current={current ? "page" : active ? "location" : undefined}
                className={`navigation-link${active ? " active" : ""}`}
                href={href}
                onNavigate={onNavigate}
                title={dictionary.navigation[label]}
              >
                <Icon aria-hidden="true" size={19} />
                <span className="navigation-label">{dictionary.navigation[label]}</span>
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
