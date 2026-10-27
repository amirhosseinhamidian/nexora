"use client";

import { useParams } from "next/navigation";

import { StatePanel } from "@/components/state-panel";
import { isLocale } from "@/i18n/config";
import { getDictionary } from "@/i18n/dictionaries";

export default function ErrorBoundary({
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  const params = useParams<{ locale: string }>();
  const locale = isLocale(params.locale) ? params.locale : "fa";
  const dictionary = getDictionary(locale).states;
  return (
    <StatePanel
      action={{ label: dictionary.reload, onClick: reset }}
      description={dictionary.errorDescription}
      kind="error"
      title={dictionary.errorTitle}
    />
  );
}
