"use client";

import {
  Alert,
  Button,
  ConfirmationDialog,
  EmptyState,
  ErrorState,
  IconButton,
  ResponsiveRecordList,
  Spinner,
  ToastRegion,
} from "@nexora/ui/primitives";
import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";

import { AlertRecordCard } from "@/components/alert-record-card";
import type { Locale } from "@/i18n/config";
import type { Dictionary } from "@/i18n/dictionaries";
import { apiRequest } from "@/lib/api-client";
import {
  alertDecisionId,
  alertsHref,
  monitoringFailure,
  visibleAlerts,
  watchlistsHref,
  type AlertAction,
  type AlertHistory,
  type AlertInboxResponse,
  type AlertItem,
  type MonitoringPreferences,
} from "@/lib/monitoring";
import { formatTimestamp } from "@/lib/portfolio-analytics";

type PresentationWatchlist = {
  watchlist_id: string;
  name: string;
  preferences: MonitoringPreferences;
};

type PendingSubmission = {
  alertId: string;
  body: {
    action: AlertAction;
    evidence_generation: number;
    expected_version: number;
    occurred_at: string;
    snooze_until: string | null;
    source_evidence_checksum: string;
  };
  key: string;
};

export function AlertInbox({
  alertId,
  decisionId,
  dictionary,
  locale,
  watchlistId,
}: {
  alertId?: string;
  decisionId?: string;
  dictionary: Dictionary;
  locale: Locale;
  watchlistId?: string;
}) {
  const copy = dictionary.alertInbox;
  const labels = dictionary.monitoring;
  const [inbox, setInbox] = useState<AlertInboxResponse>();
  const [watchlist, setWatchlist] = useState<PresentationWatchlist>();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [confirmation, setConfirmation] = useState<PendingSubmission>();
  const [pending, setPending] = useState<PendingSubmission>();
  const [submitting, setSubmitting] = useState(false);
  const [notice, setNotice] = useState<{ title: string; tone: "success" | "warning" | "danger" }>();
  const read = useRef<AbortController | null>(null);
  const write = useRef<AbortController | null>(null);

  const load = useCallback(async () => {
    read.current?.abort();
    const controller = new AbortController();
    read.current = controller;
    setLoading(true);
    setError(false);
    const { signal } = controller;
    try {
      const [result, list] = await Promise.all([
        apiRequest<AlertInboxResponse>("/api/v1/alerts?limit=100", { signal }),
        watchlistId
          ? apiRequest<{ items: PresentationWatchlist[] }>("/api/v1/watchlists?limit=100", {
              signal,
            })
          : undefined,
      ]);
      if (signal.aborted) return;
      setInbox(result);
      setWatchlist(list?.items.find((item) => item.watchlist_id === watchlistId));
    } catch {
      if (!signal.aborted) setError(true);
    } finally {
      if (!signal.aborted) setLoading(false);
    }
  }, [watchlistId]);

  useEffect(() => {
    const initialLoad = window.setTimeout(() => void load(), 0);
    return () => {
      window.clearTimeout(initialLoad);
      read.current?.abort();
      write.current?.abort();
    };
  }, [load]);

  function prepare(item: AlertItem, action: AlertAction, snoozeUntil: string | null) {
    if (loading || write.current || pending || !inbox?.provider.generation) return;
    setConfirmation({
      alertId: item.alert_id,
      body: {
        action,
        evidence_generation: inbox.provider.generation,
        expected_version: item.current_version,
        occurred_at: new Date().toISOString(),
        snooze_until: snoozeUntil,
        source_evidence_checksum: item.source.checksum,
      },
      key: `nexora-alert-${crypto.randomUUID()}`,
    });
  }

  async function transition(submission: PendingSubmission) {
    if (write.current || loading) return;
    if (submission.body.snooze_until && Date.parse(submission.body.snooze_until) <= Date.now()) {
      setPending(undefined);
      setConfirmation(undefined);
      setNotice({ title: labels.futureSnooze, tone: "warning" });
      if (pending) await load();
      return;
    }
    const controller = new AbortController();
    write.current = controller;
    const { signal } = controller;
    setConfirmation(undefined);
    setSubmitting(true);
    setNotice(undefined);
    try {
      await apiRequest<AlertHistory>(
        `/api/v1/alerts/${encodeURIComponent(submission.alertId)}/state-transitions`,
        {
          body: submission.body,
          headers: { "Idempotency-Key": submission.key },
          method: "POST",
          signal,
        },
      );
      if (signal.aborted) return;
      setPending(undefined);
      setNotice({ title: labels.alertSaved, tone: "success" });
      await load();
    } catch (error) {
      if (signal.aborted) return;
      switch (monitoringFailure(error)) {
        case "conflict":
          setPending(undefined);
          setNotice({ title: labels.alertChanged, tone: "warning" });
          await load();
          break;
        case "rejected":
          setPending(undefined);
          setNotice({ title: labels.alertRejected, tone: "danger" });
          break;
        case "unconfirmed":
          setPending(submission);
          setNotice({ title: labels.alertUnconfirmed, tone: "warning" });
          break;
      }
    } finally {
      write.current = null;
      if (!signal.aborted) setSubmitting(false);
    }
  }

  const filterUnavailable = !!watchlistId && !watchlist && !alertId;
  const items = (inbox?.items ?? []).filter(
    (item) => !decisionId || alertDecisionId(item.evidence) === decisionId,
  );
  const visible = alertId
    ? items.filter((item) => item.alert_id === alertId)
    : watchlist
      ? visibleAlerts(items, watchlist.preferences)
      : items;
  const actionLabel = confirmation?.body.action === "snooze" ? copy.snooze : copy.acknowledge;

  return (
    <section className="alert-inbox" id="alerts">
      <div className="section-heading">
        <div>
          <h2>{copy.title}</h2>
          <p>{copy.description}</p>
        </div>
      </div>
      {alertId ? (
        <Link
          className="secondary-button"
          href={alertsHref(locale, { decision: decisionId, watchlist: watchlistId })}
        >
          {labels.backToAlerts}
        </Link>
      ) : null}
      {decisionId ? (
        <div className="monitoring-filter">
          <p>
            {labels.alertsForDecision} <bdi>{decisionId}</bdi>
          </p>
          <Link className="secondary-button" href={alertsHref(locale, { watchlist: watchlistId })}>
            {labels.showAllAlerts}
          </Link>
        </div>
      ) : null}
      <ToastRegion
        label={labels.notifications}
        messages={
          notice
            ? [
                {
                  ...notice,
                  id: "alert-transition",
                  action: (
                    <IconButton aria-label={labels.dismiss} onClick={() => setNotice(undefined)}>
                      <span aria-hidden="true">×</span>
                    </IconButton>
                  ),
                },
              ]
            : []
        }
      />
      {pending && !loading && !error ? (
        <Button disabled={submitting} onClick={() => setConfirmation(pending)} variant="secondary">
          {labels.retryAction}
        </Button>
      ) : null}
      {loading ? (
        <Alert className="alert-inbox-state" role="status">
          <Spinner label="" />
          <span>{copy.loading}</span>
        </Alert>
      ) : error ? (
        <ErrorState
          title={copy.error}
          action={
            <Button onClick={() => void load()} variant="secondary">
              {copy.retry}
            </Button>
          }
        />
      ) : (
        <>
          {inbox?.provider.state !== "ready" ? (
            <Alert tone="warning" className="provider-state" role="status">
              <div>
                <strong>{copy.providerDegraded}</strong>
                <p>{copy.providerStates[inbox?.provider.state ?? "degraded"]}</p>
              </div>
            </Alert>
          ) : null}
          {watchlist && !alertId ? (
            <div className="monitoring-filter">
              <p>
                {labels.usingPreferences} <bdi>{watchlist.name}</bdi>. {labels.preferencesScope}
              </p>
              <div className="monitoring-links">
                <Link
                  className="secondary-button"
                  href={watchlistsHref(locale, watchlist.watchlist_id)}
                >
                  {labels.editPreferences}
                </Link>
                <Link
                  className="secondary-button"
                  href={alertsHref(locale, { decision: decisionId })}
                >
                  {labels.clearPreferences}
                </Link>
              </div>
            </div>
          ) : null}
          {filterUnavailable ? (
            <EmptyState
              title={labels.watchlistUnavailable}
              action={
                <Link
                  className="secondary-button"
                  href={alertsHref(locale, { decision: decisionId })}
                >
                  {labels.clearPreferences}
                </Link>
              }
            />
          ) : visible.length ? (
            <ResponsiveRecordList className="alert-list" label={copy.listLabel}>
              {visible.map((item) => (
                <AlertRecordCard
                  decisionFilter={decisionId}
                  detail={!!alertId}
                  dictionary={dictionary}
                  disabled={submitting || !!pending || !inbox?.provider.generation}
                  item={item}
                  key={item.alert_id}
                  locale={locale}
                  onAction={prepare}
                  watchlistId={watchlistId}
                />
              ))}
            </ResponsiveRecordList>
          ) : (
            <EmptyState
              className="empty-state-card"
              headingLevel={2}
              title={
                alertId
                  ? labels.alertUnavailable
                  : watchlist || decisionId
                    ? labels.noMatchingAlerts
                    : copy.emptyTitle
              }
            >
              {!alertId && !watchlist && !decisionId ? <p>{copy.emptyDescription}</p> : null}
            </EmptyState>
          )}
          <p className="alert-boundary">{copy.notificationDeferred}</p>
        </>
      )}
      {confirmation ? (
        <ConfirmationDialog
          cancelLabel={labels.cancel}
          confirmLabel={actionLabel}
          description={
            <>
              <bdi>{confirmation.alertId}</bdi>
              {confirmation.body.snooze_until ? (
                <> · {formatTimestamp(confirmation.body.snooze_until, locale)}</>
              ) : null}
            </>
          }
          onCancel={() => setConfirmation(undefined)}
          onConfirm={() => void transition(confirmation)}
          open
          title={
            confirmation.body.action === "snooze" ? labels.confirmSnooze : labels.confirmAcknowledge
          }
        />
      ) : null}
    </section>
  );
}
