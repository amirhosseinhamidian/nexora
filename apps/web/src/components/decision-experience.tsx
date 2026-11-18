"use client";

import { Workflow } from "lucide-react";
import { useState } from "react";

import { AlertInbox } from "@/components/alert-inbox";
import { DecisionFeed } from "@/components/decision-feed";
import { OutcomeJournalPanel } from "@/components/outcome-journal-panel";
import { WatchlistPanel } from "@/components/watchlist-panel";
import type { Locale } from "@/i18n/config";
import type { Dictionary } from "@/i18n/dictionaries";

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

      <div
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
      </div>

      <DecisionFeed
        dictionary={dictionary}
        locale={locale}
        onDecisionChange={setActiveDecisionId}
      />
      <OutcomeJournalPanel decisionId={activeDecisionId} dictionary={dictionary} locale={locale} />
      <AlertInbox dictionary={dictionary} locale={locale} />
      <WatchlistPanel dictionary={dictionary} locale={locale} />
    </section>
  );
}
