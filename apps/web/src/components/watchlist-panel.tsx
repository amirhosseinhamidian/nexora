"use client";

import {
  Alert,
  EmptyState,
  ResponsiveRecordList,
  Button,
  Checkbox,
  FieldError,
  FormField,
  Input,
  IconButton,
  Select,
  Spinner,
  ToastRegion,
} from "@nexora/ui/primitives";
import { Binoculars, Plus, RefreshCw, Save, ShieldAlert } from "lucide-react";
import Link from "next/link";
import type { FormEvent } from "react";
import { useId, useCallback, useEffect, useRef, useState } from "react";

import type { Locale } from "@/i18n/config";
import type { Dictionary } from "@/i18n/dictionaries";
import { apiRequest } from "@/lib/api-client";
import { alertsHref, monitoringFailure, type MonitoringPreferences } from "@/lib/monitoring";

type ItemKind = "asset" | "candidate_source" | "market" | "strategy";
type PresentationOrder = MonitoringPreferences["presentation_order"];
type MinimumSeverity = MonitoringPreferences["minimum_severity"];

type WatchlistItem = {
  watchlist_item_id: string;
  item_kind: ItemKind;
  reference: string;
  label: string | null;
  created_at: string;
};

type Watchlist = {
  watchlist_id: string;
  name: string;
  row_version: number;
  created_at: string;
  updated_at: string;
  creates_trade_instruction: false;
  preferences: MonitoringPreferences & {
    updated_at: string;
    notification_delivery_enabled: false;
    provider_subscription_management_enabled: false;
  };
  items: WatchlistItem[];
};

type WatchlistList = {
  schema_version: "nexora-watchlists-v1";
  items: Watchlist[];
};

type PendingOperation = {
  body: Record<string, unknown>;
  key: string;
  operationKey: string;
  path: string;
};

function isWatchlist(value: unknown): value is Watchlist {
  if (!value || typeof value !== "object") return false;
  const candidate = value as Partial<Watchlist>;
  return (
    typeof candidate.watchlist_id === "string" &&
    typeof candidate.name === "string" &&
    typeof candidate.row_version === "number" &&
    typeof candidate.updated_at === "string" &&
    Array.isArray(candidate.items) &&
    Boolean(candidate.preferences)
  );
}

export function WatchlistPanel({
  dictionary,
  initialWatchlistId,
  locale,
}: {
  dictionary: Dictionary;
  initialWatchlistId?: string;
  locale: Locale;
}) {
  const fieldId = useId();
  const copy = dictionary.watchlists;
  const labels = dictionary.monitoring;
  const [watchlists, setWatchlists] = useState<Watchlist[]>([]);
  const [selectedId, setSelectedId] = useState(initialWatchlistId);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [operationError, setOperationError] = useState(false);
  const [notice, setNotice] = useState<{ title: string; tone: "success" | "warning" | "danger" }>();
  const [pending, setPending] = useState<PendingOperation>();
  const [name, setName] = useState("");
  const [itemKind, setItemKind] = useState<ItemKind>("asset");
  const [reference, setReference] = useState("");
  const [label, setLabel] = useState("");
  const selected = watchlists.find((item) => item.watchlist_id === selectedId);
  const read = useRef<AbortController | null>(null);
  const write = useRef<AbortController | null>(null);
  const [presentationOrder, setPresentationOrder] = useState<PresentationOrder>("newest_first");
  const [minimumSeverity, setMinimumSeverity] = useState<MinimumSeverity>("info");
  const [includeResolved, setIncludeResolved] = useState(false);

  const load = useCallback(async () => {
    read.current?.abort();
    const controller = new AbortController();
    read.current = controller;
    setLoading(true);
    setError(false);
    try {
      const response = await apiRequest<WatchlistList>("/api/v1/watchlists?limit=100", {
        signal: controller.signal,
      });
      if (controller.signal.aborted) return;
      const items = Array.isArray(response?.items) ? response.items.filter(isWatchlist) : [];
      setWatchlists(items);
      setSelectedId((current) => current ?? items[0]?.watchlist_id);
    } catch {
      if (!controller.signal.aborted) setError(true);
    } finally {
      if (!controller.signal.aborted) setLoading(false);
    }
  }, []);

  useEffect(() => {
    const initialLoad = window.setTimeout(() => void load(), 0);
    return () => {
      window.clearTimeout(initialLoad);
      read.current?.abort();
      write.current?.abort();
    };
  }, [load]);

  useEffect(() => {
    if (!selected) return;
    const synchronize = window.setTimeout(() => {
      setPresentationOrder(selected.preferences.presentation_order);
      setMinimumSeverity(selected.preferences.minimum_severity);
      setIncludeResolved(selected.preferences.include_resolved);
    }, 0);
    return () => window.clearTimeout(synchronize);
  }, [selected]);

  function changed(operationKey: string) {
    if (pending?.operationKey === operationKey) setPending(undefined);
    setOperationError(false);
  }

  async function submit(operation: PendingOperation) {
    if (loading || write.current || (pending && pending.operationKey !== operation.operationKey))
      return false;
    const retry = pending?.operationKey === operation.operationKey ? pending : operation;
    const controller = new AbortController();
    write.current = controller;
    setPending(retry);
    setSubmitting(true);
    setOperationError(false);
    setNotice(undefined);
    try {
      const updated = await apiRequest<Watchlist>(retry.path, {
        body: retry.body,
        headers: { "Idempotency-Key": retry.key },
        method: "POST",
        signal: controller.signal,
      });
      if (controller.signal.aborted) return false;
      if (!isWatchlist(updated)) throw new Error("Invalid watchlist response");
      setPending(undefined);
      setWatchlists((current) => {
        const exists = current.some((item) => item.watchlist_id === updated.watchlist_id);
        return exists
          ? current.map((item) => (item.watchlist_id === updated.watchlist_id ? updated : item))
          : [...current, updated];
      });
      setSelectedId(updated.watchlist_id);
      setNotice({ title: labels.watchlistSaved, tone: "success" });
      return true;
    } catch (error) {
      if (controller.signal.aborted) return false;
      const outcome = monitoringFailure(error);
      if (outcome === "unconfirmed") {
        setOperationError(true);
      } else {
        setPending(undefined);
        const conflict = outcome === "conflict";
        setNotice({
          title: conflict ? labels.watchlistChanged : labels.watchlistRejected,
          tone: conflict ? "warning" : "danger",
        });
        if (conflict) await load();
      }
      return false;
    } finally {
      write.current = null;
      if (!controller.signal.aborted) setSubmitting(false);
    }
  }

  async function createWatchlist(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!name.trim()) return;
    const succeeded = await submit({
      body: { name: name.trim() },
      key: `nexora-watchlist-${crypto.randomUUID()}`,
      operationKey: "create",
      path: "/api/v1/watchlists",
    });
    if (succeeded) setName("");
  }

  async function addItem(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selected || !reference.trim()) return;
    const succeeded = await submit({
      body: {
        expected_version: selected.row_version,
        item_kind: itemKind,
        label: label.trim() || null,
        reference: reference.trim(),
      },
      key: `nexora-watchlist-item-${crypto.randomUUID()}`,
      operationKey: `item:${selected.watchlist_id}`,
      path: `/api/v1/watchlists/${encodeURIComponent(selected.watchlist_id)}/items`,
    });
    if (succeeded) {
      setReference("");
      setLabel("");
    }
  }

  async function updatePreferences(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selected) return;
    await submit({
      body: {
        expected_version: selected.row_version,
        include_resolved: includeResolved,
        minimum_severity: minimumSeverity,
        presentation_order: presentationOrder,
      },
      key: `nexora-watchlist-preferences-${crypto.randomUUID()}`,
      operationKey: `preferences:${selected.watchlist_id}`,
      path: `/api/v1/watchlists/${encodeURIComponent(selected.watchlist_id)}/preferences`,
    });
  }

  return (
    <section className="watchlist-panel" id="watchlists">
      <div className="section-heading">
        <div>
          <p className="eyebrow">{copy.eyebrow}</p>
          <h2>{copy.title}</h2>
          <p>{copy.description}</p>
        </div>
        <Binoculars aria-hidden="true" size={28} />
      </div>
      <ToastRegion
        label={labels.notifications}
        messages={
          notice
            ? [
                {
                  ...notice,
                  id: "watchlist-update",
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

      {loading ? (
        <Alert className="watchlist-state" role="status">
          <Spinner label="" />
          {copy.loading}
        </Alert>
      ) : error ? (
        <Alert tone="danger" className="watchlist-state error" role="alert">
          <ShieldAlert aria-hidden="true" size={22} />
          <span>{copy.error}</span>
          <Button
            variant="secondary"
            className="secondary-button"
            onClick={() => void load()}
            type="button"
          >
            <RefreshCw aria-hidden="true" size={16} />
            {copy.retry}
          </Button>
        </Alert>
      ) : (
        <div className="watchlist-workspace">
          <form className="watchlist-create" onSubmit={(event) => void createWatchlist(event)}>
            <FormField id={`${fieldId}-name`} label={copy.name}>
              <Input
                disabled={submitting}
                id={`${fieldId}-name`}
                maxLength={120}
                onChange={(event) => {
                  setName(event.target.value);
                  changed("create");
                }}
                placeholder={copy.namePlaceholder}
                required
                value={name}
              />
            </FormField>
            <Button
              className="primary-button"
              disabled={
                submitting || !name.trim() || !!(pending && pending.operationKey !== "create")
              }
              type="submit"
            >
              <Plus aria-hidden="true" size={16} />
              {submitting && pending?.operationKey === "create" ? copy.saving : copy.create}
            </Button>
          </form>

          {watchlists.length ? (
            <div className="watchlist-selector">
              <FormField id={`${fieldId}-select`} label={copy.select}>
                <Select
                  disabled={submitting || !!pending}
                  id={`${fieldId}-select`}
                  onValueChange={setSelectedId}
                  placeholder={copy.select}
                  value={selected?.watchlist_id ?? ""}
                  options={watchlists.map((item) => ({
                    value: item.watchlist_id,
                    label: item.name,
                  }))}
                />
              </FormField>
              {selected ? (
                <Link
                  className="secondary-button"
                  href={alertsHref(locale, { watchlist: selected.watchlist_id })}
                >
                  {labels.viewFilteredAlerts}
                </Link>
              ) : (
                <p>{labels.watchlistUnavailable}</p>
              )}
            </div>
          ) : (
            <EmptyState
              className="empty-state-card"
              headingLevel={2}
              icon={<Binoculars aria-hidden="true" size={28} />}
              title={copy.emptyTitle}
            >
              <p>{copy.emptyDescription}</p>
            </EmptyState>
          )}
          {selected ? (
            <>
              <div className="watchlist-selector">
                <small>
                  {copy.version.replace("{version}", String(selected.row_version))} · {copy.updated}{" "}
                  {new Intl.DateTimeFormat(locale, {
                    dateStyle: "medium",
                    timeStyle: "short",
                  }).format(new Date(selected.updated_at))}
                </small>
              </div>

              <div className="watchlist-columns">
                <section aria-label={copy.itemsTitle} className="watchlist-card">
                  <h3>{copy.itemsTitle}</h3>
                  {selected.items.length ? (
                    <ResponsiveRecordList className="watchlist-items" label={copy.itemsTitle}>
                      {selected.items.map((item) => (
                        <li key={item.watchlist_item_id}>
                          <span className="evidence-state">{copy.itemKinds[item.item_kind]}</span>
                          <strong>{item.label ?? item.reference}</strong>
                          {item.label ? <code dir="ltr">{item.reference}</code> : null}
                        </li>
                      ))}
                    </ResponsiveRecordList>
                  ) : (
                    <p>{copy.noItems}</p>
                  )}
                  <form className="watchlist-form" onSubmit={(event) => void addItem(event)}>
                    <FormField id={`${fieldId}-item-kind`} label={copy.itemKind}>
                      <Select
                        disabled={submitting}
                        id={`${fieldId}-item-kind`}
                        onValueChange={(value) => {
                          setItemKind(value as ItemKind);
                          changed(`item:${selected.watchlist_id}`);
                        }}
                        value={itemKind}
                        options={Object.entries(copy.itemKinds).map(([value, text]) => ({
                          value: value,
                          label: text,
                        }))}
                      />
                    </FormField>
                    <FormField id={`${fieldId}-reference`} label={copy.reference}>
                      <Input
                        disabled={submitting}
                        id={`${fieldId}-reference`}
                        maxLength={160}
                        onChange={(event) => {
                          setReference(event.target.value);
                          changed(`item:${selected.watchlist_id}`);
                        }}
                        required
                        value={reference}
                      />
                    </FormField>
                    <FormField id={`${fieldId}-label`} label={copy.label}>
                      <Input
                        disabled={submitting}
                        id={`${fieldId}-label`}
                        maxLength={120}
                        onChange={(event) => {
                          setLabel(event.target.value);
                          changed(`item:${selected.watchlist_id}`);
                        }}
                        value={label}
                      />
                    </FormField>
                    <Button
                      variant="secondary"
                      className="secondary-button"
                      disabled={
                        submitting ||
                        !reference.trim() ||
                        !!(pending && pending.operationKey !== `item:${selected.watchlist_id}`)
                      }
                      type="submit"
                    >
                      <Plus aria-hidden="true" size={16} />
                      {copy.addItem}
                    </Button>
                  </form>
                </section>

                <section aria-label={copy.preferencesTitle} className="watchlist-card">
                  <h3>{copy.preferencesTitle}</h3>
                  <form
                    className="watchlist-form"
                    onSubmit={(event) => void updatePreferences(event)}
                  >
                    <FormField id={`${fieldId}-presentation-order`} label={copy.presentationOrder}>
                      <Select
                        disabled={submitting}
                        id={`${fieldId}-presentation-order`}
                        onValueChange={(value) => {
                          setPresentationOrder(value as PresentationOrder);
                          changed(`preferences:${selected.watchlist_id}`);
                        }}
                        value={presentationOrder}
                        options={Object.entries(copy.presentationOrders).map(([value, text]) => ({
                          value: value,
                          label: text,
                        }))}
                      />
                    </FormField>
                    <FormField id={`${fieldId}-minimum-severity`} label={copy.minimumSeverity}>
                      <Select
                        disabled={submitting}
                        id={`${fieldId}-minimum-severity`}
                        onValueChange={(value) => {
                          setMinimumSeverity(value as MinimumSeverity);
                          changed(`preferences:${selected.watchlist_id}`);
                        }}
                        value={minimumSeverity}
                        options={Object.entries(copy.severities).map(([value, text]) => ({
                          value: value,
                          label: text,
                        }))}
                      />
                    </FormField>
                    <Checkbox
                      disabled={submitting}
                      className="watchlist-checkbox"
                      checked={includeResolved}
                      onChange={(event) => {
                        setIncludeResolved(event.target.checked);
                        changed(`preferences:${selected.watchlist_id}`);
                      }}
                    >
                      {copy.includeResolved}
                    </Checkbox>
                    <Button
                      className="primary-button"
                      disabled={
                        submitting ||
                        !!(
                          pending && pending.operationKey !== `preferences:${selected.watchlist_id}`
                        )
                      }
                      type="submit"
                    >
                      <Save aria-hidden="true" size={16} />
                      {copy.savePreferences}
                    </Button>
                  </form>
                </section>
              </div>
            </>
          ) : null}

          {operationError ? (
            <FieldError className="form-error">{copy.operationError}</FieldError>
          ) : null}
          <p className="watchlist-boundary">{copy.boundary}</p>
        </div>
      )}
    </section>
  );
}
