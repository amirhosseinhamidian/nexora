"use client";

import { AlertTriangle, Bell, Check, Clock3, LoaderCircle, RefreshCw } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import type { Locale } from "@/i18n/config";
import type { Dictionary } from "@/i18n/dictionaries";
import { apiRequest } from "@/lib/api-client";

type ProviderStatus = {
  contract_version: string | null;
  generation: number | null;
  provider_version: string | null;
  reason_code: string;
  state: "degraded" | "disabled_incompatible" | "ready";
};

type AlertState = "acknowledged" | "expired" | "open" | "resolved" | "snoozed";

type AlertSource = {
  aggregate_id: string | null;
  aggregate_type: string | null;
  aggregate_version: number | null;
  checksum: string;
  event_id: string | null;
  observed_at: string;
  resource_id: string;
  resource_schema_version: string;
  resource_type: "alert";
  schema_version: "nexora-source-reference-v1";
  source_product: "trd_bot";
  source_version: string;
};

type AlertHistory = {
  alert_history_id: string;
  evidence_generation: number;
  occurred_at: string;
  reason_code: string;
  recorded_at: string;
  snooze_until: string | null;
  source_evidence_checksum: string;
  state: AlertState;
  state_version: number;
};

type AlertItem = {
  alert_id: string;
  current_version: number;
  evidence: Record<string, unknown>;
  evidence_sha256: string;
  history: AlertHistory[];
  local_state: AlertState;
  snooze_until: string | null;
  source: AlertSource;
};

type AlertInboxResponse = {
  items: AlertItem[];
  notification_delivery_enabled: false;
  provider: ProviderStatus;
  schema_version: "nexora-alert-inbox-v1";
};

type PendingSubmission = {
  action: "acknowledge" | "snooze";
  alertId: string;
  body: Record<string, unknown>;
  key: string;
};

function defaultSnoozeValue(): string {
  const value = new Date(Date.now() + 60 * 60 * 1000);
  const offset = value.getTimezoneOffset() * 60_000;
  return new Date(value.getTime() - offset).toISOString().slice(0, 16);
}

export function AlertInbox({ dictionary, locale }: { dictionary: Dictionary; locale: Locale }) {
  const copy = dictionary.alertInbox;
  const [inbox, setInbox] = useState<AlertInboxResponse>();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [transitionError, setTransitionError] = useState<string>();
  const [pending, setPending] = useState<PendingSubmission>();
  const [submitting, setSubmitting] = useState(false);
  const [snoozeValues, setSnoozeValues] = useState<Record<string, string>>({});
  const initialSnooze = useMemo(() => defaultSnoozeValue(), []);

  const load = useCallback(async () => {
    setLoading(true);
    setError(false);
    try {
      setInbox(await apiRequest<AlertInboxResponse>("/api/v1/alerts?limit=50"));
    } catch {
      setError(true);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const initialLoad = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(initialLoad);
  }, [load]);

  async function transition(item: AlertItem, action: "acknowledge" | "snooze") {
    if (!inbox?.provider.generation) return;
    const retry =
      pending?.alertId === item.alert_id && pending.action === action ? pending : undefined;
    const snooze = snoozeValues[item.alert_id] ?? initialSnooze;
    const submission = retry ?? {
      action,
      alertId: item.alert_id,
      body: {
        action,
        evidence_generation: inbox.provider.generation,
        expected_version: item.current_version,
        occurred_at: new Date().toISOString(),
        snooze_until: action === "snooze" ? new Date(snooze).toISOString() : null,
        source_evidence_checksum: item.source.checksum,
      },
      key: `nexora-alert-${crypto.randomUUID()}`,
    };
    setPending(submission);
    setSubmitting(true);
    setTransitionError(undefined);
    try {
      await apiRequest<AlertHistory>(
        `/api/v1/alerts/${encodeURIComponent(item.alert_id)}/state-transitions`,
        {
          body: submission.body,
          headers: { "Idempotency-Key": submission.key },
          method: "POST",
        },
      );
      setPending(undefined);
      await load();
    } catch {
      setTransitionError(item.alert_id);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section className="alert-inbox" id="alerts">
      <div className="section-heading">
        <div>
          <p className="eyebrow">{copy.eyebrow}</p>
          <h2>{copy.title}</h2>
          <p>{copy.description}</p>
        </div>
        <Bell aria-hidden="true" size={28} />
      </div>

      {loading ? (
        <div className="alert-inbox-state" role="status">
          <LoaderCircle aria-hidden="true" className="spin" size={22} />
          <span>{copy.loading}</span>
        </div>
      ) : error ? (
        <div className="alert-inbox-state error" role="alert">
          <AlertTriangle aria-hidden="true" size={22} />
          <span>{copy.error}</span>
          <button className="secondary-button" onClick={() => void load()} type="button">
            <RefreshCw aria-hidden="true" size={16} />
            {copy.retry}
          </button>
        </div>
      ) : (
        <>
          {inbox?.provider?.state !== "ready" ? (
            <div className="provider-state" role="status">
              <AlertTriangle aria-hidden="true" size={20} />
              <div>
                <strong>{copy.providerDegraded}</strong>
                <p>{copy.providerStates[inbox?.provider?.state ?? "degraded"]}</p>
              </div>
            </div>
          ) : null}

          {inbox?.items?.length ? (
            <ul aria-label={copy.listLabel} className="alert-list">
              {inbox.items.map((item) => {
                const terminal = item.local_state === "resolved" || item.local_state === "expired";
                const itemPending = submitting && pending?.alertId === item.alert_id;
                return (
                  <li className="alert-card" key={item.alert_id}>
                    <div className="alert-card-heading">
                      <div>
                        <p className="eyebrow">{copy.sourceAlert}</p>
                        <h3>{item.alert_id}</h3>
                      </div>
                      <span className={`evidence-state ${item.local_state}`}>
                        {copy.states[item.local_state]}
                      </span>
                    </div>

                    <dl className="alert-lineage">
                      <div>
                        <dt>{copy.observedAt}</dt>
                        <dd>
                          {new Intl.DateTimeFormat(locale, {
                            dateStyle: "medium",
                            timeStyle: "short",
                          }).format(new Date(item.source.observed_at))}
                        </dd>
                      </div>
                      <div>
                        <dt>{copy.sourceSchema}</dt>
                        <dd>{item.source.resource_schema_version}</dd>
                      </div>
                      <div className="wide">
                        <dt>{copy.sourceChecksum}</dt>
                        <dd>
                          <code dir="ltr">{item.source.checksum}</code>
                        </dd>
                      </div>
                    </dl>

                    <details>
                      <summary>{copy.evidence}</summary>
                      <pre dir="ltr">{JSON.stringify(item.evidence, null, 2)}</pre>
                    </details>

                    {!terminal ? (
                      <div className="alert-actions">
                        <button
                          className="primary-button"
                          disabled={itemPending || item.local_state === "acknowledged"}
                          onClick={() => void transition(item, "acknowledge")}
                          type="button"
                        >
                          <Check aria-hidden="true" size={16} />
                          {itemPending && pending?.action === "acknowledge"
                            ? copy.saving
                            : copy.acknowledge}
                        </button>
                        <label>
                          <span>{copy.snoozeUntil}</span>
                          <input
                            min={initialSnooze}
                            onChange={(event) =>
                              setSnoozeValues((current) => ({
                                ...current,
                                [item.alert_id]: event.target.value,
                              }))
                            }
                            type="datetime-local"
                            value={snoozeValues[item.alert_id] ?? initialSnooze}
                          />
                        </label>
                        <button
                          className="secondary-button"
                          disabled={itemPending}
                          onClick={() => void transition(item, "snooze")}
                          type="button"
                        >
                          <Clock3 aria-hidden="true" size={16} />
                          {itemPending && pending?.action === "snooze" ? copy.saving : copy.snooze}
                        </button>
                      </div>
                    ) : null}

                    {transitionError === item.alert_id ? (
                      <p className="form-error" role="alert">
                        {copy.transitionError}
                      </p>
                    ) : null}
                    <small className="alert-history-count">
                      {copy.historyCount.replace("{count}", String(item.history.length))}
                    </small>
                  </li>
                );
              })}
            </ul>
          ) : (
            <div className="empty-state-card">
              <Bell aria-hidden="true" size={28} />
              <div>
                <h2>{copy.emptyTitle}</h2>
                <p>{copy.emptyDescription}</p>
              </div>
            </div>
          )}

          <p className="alert-boundary">{copy.notificationDeferred}</p>
        </>
      )}
    </section>
  );
}
