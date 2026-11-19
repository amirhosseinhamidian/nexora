"use client";

import { useParams } from "next/navigation";

import { StatePanel } from "@/components/state-panel";
import { defaultLocale, isLocale } from "@/i18n/config";
import { getDictionary } from "@/i18n/dictionaries";

export default function Loading() {
  const params = useParams<{ locale: string }>();
  const copy = getDictionary(isLocale(params.locale) ? params.locale : defaultLocale).states;
  return (
    <StatePanel description={copy.loadingDescription} kind="loading" title={copy.loadingTitle} />
  );
}
