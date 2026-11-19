import { Alert } from "@nexora/ui/primitives";

import { DecisionPolicyChecks } from "@/components/decision-policy-checks";
import type { Locale } from "@/i18n/config";
import { formatTimestamp } from "@/lib/portfolio-analytics";
import type { Dictionary } from "@/i18n/dictionaries";
import type { RiskGateExplanation } from "@/lib/decision-intelligence";

export function RiskGatePanel({
  dictionary,
  locale,
  riskGate,
}: {
  dictionary: Dictionary;
  locale: Locale;
  riskGate: RiskGateExplanation | null;
}) {
  const copy = dictionary.decisionFeed;
  if (!riskGate) {
    return (
      <section className="risk-explanation unavailable" aria-label={copy.riskTitle}>
        <h2>{copy.riskTitle}</h2>
        <p>{copy.riskUnavailable}</p>
      </section>
    );
  }
  return (
    <section className="risk-explanation" aria-label={copy.riskTitle}>
      <div className="risk-heading">
        <div>
          <h2>{copy.riskTitle}</h2>
        </div>
        <span className={`risk-decision ${riskGate.decision}`}>
          {copy.riskDecisions[riskGate.decision]}
        </span>
      </div>
      <dl className="risk-policy-grid">
        <div>
          <dt>{copy.policyVersion}</dt>
          <dd dir="ltr">{riskGate.policy.version}</dd>
        </div>
        <div>
          <dt>{copy.evaluatedAt}</dt>
          <dd>
            <time dateTime={riskGate.evaluated_at}>
              {formatTimestamp(riskGate.evaluated_at, locale)}
            </time>
          </dd>
        </div>
        <div className="wide">
          <dt>{copy.policyChecksum}</dt>
          <dd className="checksum" dir="ltr">
            {riskGate.policy.checksum}
          </dd>
        </div>
      </dl>
      <h5>{copy.providerReasons}</h5>
      {riskGate.provider_reason_codes.length ? (
        <ul className="risk-reasons">
          {riskGate.provider_reason_codes.map((reason) => (
            <li key={`${reason.namespace}:${reason.code}`} dir="ltr">
              <span>{reason.namespace}</span>
              <strong>{reason.code}</strong>
            </li>
          ))}
        </ul>
      ) : (
        <p className="risk-empty-reasons">{copy.noProviderReasons}</p>
      )}
      <DecisionPolicyChecks
        checks={riskGate.checks}
        dictionary={dictionary}
        locale={locale}
        title={copy.policyChecks}
      />
      <Alert tone="warning" className="risk-uncertainty" role="status">
        <strong>{copy.uncertainty}</strong>
        <p>{copy.uncertaintyNotSupplied}</p>
        <code>{riskGate.uncertainty.reason_code}</code>
      </Alert>
      <p className="advisory-boundary">{copy.riskBoundary}</p>
    </section>
  );
}
