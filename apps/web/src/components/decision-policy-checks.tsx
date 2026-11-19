import { Disclosure } from "@nexora/ui/primitives";

import type { Locale } from "@/i18n/config";
import type { Dictionary } from "@/i18n/dictionaries";
import type { DecisionPolicyCheck } from "@/lib/decision-intelligence";
import { exactDecimal } from "@/lib/portfolio-accounting";

export function DecisionPolicyChecks({
  checks,
  dictionary,
  locale,
  title,
}: {
  checks: DecisionPolicyCheck[];
  dictionary: Dictionary;
  locale: Locale;
  title: string;
}) {
  if (!checks.length) return null;
  const copy = dictionary.decisionFeed;
  const labels = dictionary.decisionPages;
  const value = (text: string) =>
    text === "unavailable" ? (
      labels.correlationStates.unavailable
    ) : (
      <bdi dir="ltr">{exactDecimal(text, locale)}</bdi>
    );

  return (
    <>
      <h3>{title}</h3>
      <div className="risk-checks">
        {checks.map((check) => (
          <article className={check.passed ? "passed" : "failed"} key={check.name}>
            <div>
              <strong>
                {Object.hasOwn(labels.checks, check.name) ? (
                  labels.checks[check.name as keyof typeof labels.checks]
                ) : (
                  <bdi>{check.name}</bdi>
                )}
              </strong>
              <span>{check.passed ? copy.checkPassed : copy.checkFailed}</span>
            </div>
            <p>
              {copy.actualValue} {value(check.actual_value)} · {copy.limitValue}{" "}
              {value(check.limit_value)}
            </p>
            <Disclosure className="accounting-disclosure" label={labels.checkDetails}>
              <p dir="auto">{check.explanation}</p>
            </Disclosure>
          </article>
        ))}
      </div>
    </>
  );
}
