"use client";

import { useParams } from "next/navigation";

import { StatePanel } from "@/components/state-panel";
import { defaultLocale, isLocale } from "@/i18n/config";
import { getDictionary } from "@/i18n/dictionaries";

export default function LocaleNotFound() {
  const params = useParams<{ locale: string }>();
  const locale = isLocale(params.locale) ? params.locale : defaultLocale;
  const copy = getDictionary(locale).states;
  return (
    <StatePanel
      action={{ label: copy.backToOverview, href: `/${locale}/overview` }}
      description={copy.notFoundDescription}
      kind="error"
      title={copy.notFoundTitle}
    />
  );
}
