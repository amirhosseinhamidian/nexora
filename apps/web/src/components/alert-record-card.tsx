import { Button, Disclosure, FormField, Input, ResponsiveRecordList } from "@nexora/ui/primitives";
import Link from "next/link";
import { useId, useState } from "react";

import type { Locale } from "@/i18n/config";
import type { Dictionary } from "@/i18n/dictionaries";
import { decisionHref } from "@/lib/decision-intelligence";
import {
  alertDecisionId,
  alertSeverity,
  alertsHref,
  journalHref,
  type AlertAction,
  type AlertItem,
} from "@/lib/monitoring";
import { formatTimestamp, localizeDigits } from "@/lib/portfolio-analytics";

function defaultSnoozeValue() {
  const value = new Date(Date.now() + 60 * 60 * 1000);
  return new Date(value.getTime() - value.getTimezoneOffset() * 60_000).toISOString().slice(0, 16);
}

export function AlertRecordCard({
  decisionFilter,
  detail,
  dictionary,
  disabled,
  item,
  locale,
  onAction,
  watchlistId,
}: {
  detail: boolean;
  decisionFilter?: string;
  dictionary: Dictionary;
  disabled: boolean;
  item: AlertItem;
  locale: Locale;
  onAction: (item: AlertItem, action: AlertAction, snoozeUntil: string | null) => void;
  watchlistId?: string;
}) {
  const id = useId();
  const copy = dictionary.alertInbox;
  const labels = dictionary.monitoring;
  const [snooze, setSnooze] = useState(defaultSnoozeValue);
  const [invalidSnooze, setInvalidSnooze] = useState(false);
  const terminal = item.local_state === "expired" || item.local_state === "resolved";
  const decision = alertDecisionId(item.evidence);
  const severity = alertSeverity(item.evidence.severity);
  const message = typeof item.evidence.message === "string" ? item.evidence.message : undefined;

  function prepareSnooze() {
    const date = new Date(snooze);
    if (!Number.isFinite(date.getTime()) || date.getTime() <= Date.now()) {
      setInvalidSnooze(true);
      return;
    }
    onAction(item, "snooze", date.toISOString());
  }

  return (
    <li className="alert-card">
      <div className="alert-card-heading">
        <h3>
          {detail ? (
            <bdi>{item.alert_id}</bdi>
          ) : (
            <Link
              href={alertsHref(locale, {
                alert: item.alert_id,
                decision: decisionFilter,
                watchlist: watchlistId,
              })}
            >
              <bdi>{item.alert_id}</bdi>
            </Link>
          )}
        </h3>
        <span className={`evidence-state ${item.local_state}`}>
          {copy.states[item.local_state]}
        </span>
      </div>
      {message ? <p dir="auto">{message}</p> : null}
      <dl className="alert-lineage">
        <div>
          <dt>{copy.observedAt}</dt>
          <dd>
            <time dateTime={item.source.observed_at}>
              {formatTimestamp(item.source.observed_at, locale)}
            </time>
          </dd>
        </div>
        <div>
          <dt>{labels.severity}</dt>
          <dd>{severity ? dictionary.watchlists.severities[severity] : labels.unknownSeverity}</dd>
        </div>
        <div>
          <dt>{copy.sourceSchema}</dt>
          <dd>
            <bdi>{item.source.resource_schema_version}</bdi>
          </dd>
        </div>
        <div className="wide">
          <dt>{copy.sourceChecksum}</dt>
          <dd>
            <code dir="ltr">{item.source.checksum}</code>
          </dd>
        </div>
        {item.local_state === "snoozed" && item.snooze_until ? (
          <div>
            <dt>{copy.snoozeUntil}</dt>
            <dd>
              <time dateTime={item.snooze_until}>{formatTimestamp(item.snooze_until, locale)}</time>
            </dd>
          </div>
        ) : null}
      </dl>
      {decision ? (
        <div className="monitoring-links">
          <Link
            className="secondary-button"
            href={decisionHref(locale, {
              kind: "records",
              panel: "evidence",
              resourceId: decision,
            })}
          >
            {labels.openDecision}
          </Link>
          <Link className="secondary-button" href={journalHref(locale, decision)}>
            {labels.openJournal}
          </Link>
        </div>
      ) : detail ? (
        <p>{labels.noLinkedDecision}</p>
      ) : null}
      <Disclosure className="accounting-disclosure" label={copy.evidence}>
        <pre dir="ltr">{JSON.stringify(item.evidence, null, 2)}</pre>
      </Disclosure>
      {!terminal ? (
        <div className="alert-actions">
          <Button
            disabled={disabled || item.local_state === "acknowledged"}
            onClick={() => onAction(item, "acknowledge", null)}
          >
            {copy.acknowledge}
          </Button>
          <FormField
            id={id}
            label={copy.snoozeUntil}
            error={invalidSnooze ? labels.futureSnooze : undefined}
          >
            <Input
              aria-describedby={invalidSnooze ? `${id}-error` : undefined}
              aria-invalid={invalidSnooze || undefined}
              disabled={disabled}
              id={id}
              onChange={(event) => {
                setSnooze(event.target.value);
                setInvalidSnooze(false);
              }}
              type="datetime-local"
              value={snooze}
            />
          </FormField>
          <Button disabled={disabled} onClick={prepareSnooze} variant="secondary">
            {copy.snooze}
          </Button>
        </div>
      ) : null}
      <Disclosure
        className="accounting-disclosure"
        label={`${labels.alertHistory} (${localizeDigits(String(item.history.length), locale)})`}
      >
        {item.history.length ? (
          <ResponsiveRecordList as="ol" className="review-history" label={labels.alertHistory}>
            {item.history
              .toSorted((a, b) => b.state_version - a.state_version)
              .map((entry) => (
                <li key={entry.alert_history_id}>
                  <strong>
                    {labels.alertVersion.replace(
                      "{version}",
                      localizeDigits(String(entry.state_version), locale),
                    )}{" "}
                    · {copy.states[entry.state]}
                  </strong>
                  <time dateTime={entry.recorded_at}>
                    {formatTimestamp(entry.recorded_at, locale)}
                  </time>
                  {entry.snooze_until ? (
                    <small>
                      {copy.snoozeUntil} ·{" "}
                      <time dateTime={entry.snooze_until}>
                        {formatTimestamp(entry.snooze_until, locale)}
                      </time>
                    </small>
                  ) : null}
                </li>
              ))}
          </ResponsiveRecordList>
        ) : (
          <p>{labels.emptyAlertHistory}</p>
        )}
      </Disclosure>
    </li>
  );
}
