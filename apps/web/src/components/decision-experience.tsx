"use client";

import { Alert } from "@nexora/ui/primitives";
import { Workflow } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { DecisionFeed } from "@/components/decision-feed";
import { OutcomeJournalPanel } from "@/components/outcome-journal-panel";
import type { Locale } from "@/i18n/config";
import type { Dictionary } from "@/i18n/dictionaries";
import { alertsHref, watchlistsHref } from "@/lib/monitoring";

export function DecisionExperience({
  dictionary,
  locale,
}: {
  dictionary: Dictionary;
  locale: Locale;
}) {
  const copy = dictionary.decisionExperience;
  const [activeDecisionId, setActiveDecisionId] = useState<string>();

  return (
    <section aria-labelledby="decision-experience-title" className="decision-experience">
      <div className="decision-experience-heading">
        <div>
          <p className="eyebrow">{copy.eyebrow}</p>
          <h2 id="decision-experience-title">{copy.title}</h2>
          <p>{copy.description}</p>
        </div>
        <Workflow aria-hidden="true" size={28} />
      </div>

      <Alert
        aria-label={copy.activeDecision}
        aria-live="polite"
        className="decision-context"
        role="status"
      >
        <strong>{copy.activeDecision}</strong>
        {activeDecisionId ? (
          <code dir="ltr">{activeDecisionId}</code>
        ) : (
          <span>{copy.noActiveDecision}</span>
        )}
      </Alert>

      <DecisionFeed
        dictionary={dictionary}
        locale={locale}
        onDecisionChange={setActiveDecisionId}
      />
      {activeDecisionId ? (
        <OutcomeJournalPanel
          decisionId={activeDecisionId}
          dictionary={dictionary}
          key={activeDecisionId}
          locale={locale}
          readOnly
        />
      ) : null}
      <div className="monitoring-links">
        <Link className="secondary-button" href={alertsHref(locale)}>
          {dictionary.monitoring.inbox}
        </Link>
        <Link className="secondary-button" href={watchlistsHref(locale)}>
          {dictionary.monitoring.watchlists}
        </Link>
      </div>
    </section>
  );
}
