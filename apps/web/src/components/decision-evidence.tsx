import { Disclosure } from "@nexora/ui/primitives";

import type { Locale } from "@/i18n/config";
import type { Dictionary } from "@/i18n/dictionaries";
import type { DecisionFeedItem } from "@/lib/decision-intelligence";
import { formatTimestamp } from "@/lib/portfolio-analytics";

function displayValue(value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

export function EvidencePanel({
  copy,
  item,
  locale,
}: {
  copy: Dictionary["decisionFeed"];
  item: DecisionFeedItem;
  locale: Locale;
}) {
  return (
    <article className="decision-evidence" aria-label={copy.detailTitle}>
      <div className="decision-evidence-heading">
        <div>
          <p className="eyebrow">{copy.detailEyebrow}</p>
          <h3>{item.resource_id}</h3>
        </div>
        <span className={`evidence-state ${item.local_state}`}>
          {copy.reviewStates[item.local_state]}
        </span>
      </div>
      <dl className="source-reference-grid">
        <div>
          <dt>{copy.observedAt}</dt>
          <dd>{formatTimestamp(item.source.observed_at, locale)}</dd>
        </div>
        <div>
          <dt>{copy.providerVersion}</dt>
          <dd dir="ltr">TRD Bot {item.source.source_version}</dd>
        </div>
        <div>
          <dt>{copy.sourceSchema}</dt>
          <dd dir="ltr">{item.source.resource_schema_version}</dd>
        </div>
        <div>
          <dt>{copy.aggregateVersion}</dt>
          <dd dir="ltr">{item.source.aggregate_version ?? "—"}</dd>
        </div>
        <div className="wide">
          <dt>{copy.sourceChecksum}</dt>
          <dd className="checksum" dir="ltr">
            {item.source.checksum}
          </dd>
        </div>
        <div className="wide">
          <dt>{copy.evidenceChecksum}</dt>
          <dd className="checksum" dir="ltr">
            sha256:{item.evidence_sha256}
          </dd>
        </div>
      </dl>
      <Disclosure className="accounting-disclosure" label={copy.evidenceTitle}>
        <dl className="evidence-payload">
          {Object.entries(item.evidence).map(([key, value]) => (
            <div key={key}>
              <dt dir="ltr">{key}</dt>
              <dd dir="ltr">{displayValue(value)}</dd>
            </div>
          ))}
        </dl>
      </Disclosure>
      <p className="advisory-boundary">{copy.advisoryBoundary}</p>
    </article>
  );
}
