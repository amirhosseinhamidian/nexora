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
  Select,
  Spinner,
} from "@nexora/ui/primitives";
import { Binoculars, Plus, RefreshCw, Save, ShieldAlert } from "lucide-react";
import type { FormEvent } from "react";
import { useId, useCallback, useEffect, useState } from "react";

import type { Locale } from "@/i18n/config";
import type { Dictionary } from "@/i18n/dictionaries";
import { apiRequest } from "@/lib/api-client";

type ItemKind = "asset" | "candidate_source" | "market" | "strategy";
type PresentationOrder = "newest_first" | "oldest_first" | "severity_desc";
type MinimumSeverity = "critical" | "info" | "warning";

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
  preferences: {
    presentation_order: PresentationOrder;
    minimum_severity: MinimumSeverity;
    include_resolved: boolean;
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

export function WatchlistPanel({ dictionary, locale }: { dictionary: Dictionary; locale: Locale }) {
  const fieldId = useId();
  const copy = dictionary.watchlists;
  const [watchlists, setWatchlists] = useState<Watchlist[]>([]);
  const [selectedId, setSelectedId] = useState<string>();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [operationError, setOperationError] = useState(false);
  const [pending, setPending] = useState<PendingOperation>();
  const [name, setName] = useState("");
  const [itemKind, setItemKind] = useState<ItemKind>("asset");
  const [reference, setReference] = useState("");
  const [label, setLabel] = useState("");
  const selected = watchlists.find((item) => item.watchlist_id === selectedId) ?? watchlists[0];
  const [presentationOrder, setPresentationOrder] = useState<PresentationOrder>("newest_first");
  const [minimumSeverity, setMinimumSeverity] = useState<MinimumSeverity>("info");
  const [includeResolved, setIncludeResolved] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(false);
    try {
      const response = await apiRequest<WatchlistList>("/api/v1/watchlists?limit=50");
      const items = Array.isArray(response?.items) ? response.items.filter(isWatchlist) : [];
      setWatchlists(items);
      setSelectedId((current) =>
        current && items.some((item) => item.watchlist_id === current)
          ? current
          : items[0]?.watchlist_id,
      );
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
    const retry = pending?.operationKey === operation.operationKey ? pending : operation;
    setPending(retry);
    setSubmitting(true);
    setOperationError(false);
    try {
      const updated = await apiRequest<Watchlist>(retry.path, {
        body: retry.body,
        headers: { "Idempotency-Key": retry.key },
        method: "POST",
      });
      if (!isWatchlist(updated)) throw new Error("Invalid watchlist response");
      setPending(undefined);
      setWatchlists((current) => {
        const exists = current.some((item) => item.watchlist_id === updated.watchlist_id);
        return exists
          ? current.map((item) => (item.watchlist_id === updated.watchlist_id ? updated : item))
          : [...current, updated];
      });
      setSelectedId(updated.watchlist_id);
      return true;
    } catch {
      setOperationError(true);
      return false;
    } finally {
      setSubmitting(false);
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
      path: `/api/v1/watchlists/${selected.watchlist_id}/items`,
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
      path: `/api/v1/watchlists/${selected.watchlist_id}/preferences`,
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
            <Button className="primary-button" disabled={submitting || !name.trim()} type="submit">
              <Plus aria-hidden="true" size={16} />
              {submitting && pending?.operationKey === "create" ? copy.saving : copy.create}
            </Button>
          </form>

          {watchlists.length === 0 ? (
            <EmptyState
              className="empty-state-card"
              headingLevel={2}
              icon={<Binoculars aria-hidden="true" size={28} />}
              title={copy.emptyTitle}
            >
              <p>{copy.emptyDescription}</p>
            </EmptyState>
          ) : selected ? (
            <>
              <div className="watchlist-selector">
                <FormField id={`${fieldId}-select`} label={copy.select}>
                  <Select
                    id={`${fieldId}-select`}
                    onValueChange={(value) => setSelectedId(value)}
                    value={selected.watchlist_id}
                    options={watchlists.map((item) => ({
                      value: item.watchlist_id,
                      label: item.name,
                    }))}
                  />
                </FormField>
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
                      disabled={submitting || !reference.trim()}
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
                      className="watchlist-checkbox"
                      checked={includeResolved}
                      onChange={(event) => {
                        setIncludeResolved(event.target.checked);
                        changed(`preferences:${selected.watchlist_id}`);
                      }}
                    >
                      {copy.includeResolved}
                    </Checkbox>
                    <Button className="primary-button" disabled={submitting} type="submit">
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
