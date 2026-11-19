"use client";

import { Alert, Button, EmptyState, ErrorState, Spinner } from "@nexora/ui/primitives";
import { ChevronRight } from "lucide-react";
import Link from "next/link";
import { type KeyboardEvent, useEffect, useRef, useState } from "react";

import { EvidencePanel } from "@/components/decision-evidence";
import { WorkspaceTime } from "@/components/workspace-time";
import type { Locale } from "@/i18n/config";
import type { Dictionary } from "@/i18n/dictionaries";
import {
  decisionContextId,
  decisionFeedPage,
  decisionHref,
  type DecisionFeedItem,
  type DecisionFeedPage,
} from "@/lib/decision-intelligence";

type FeedState =
  { status: "loading" | "error" } | { status: "ready"; page: DecisionFeedPage; selected: number };

export function DecisionFeed({
  dictionary,
  locale,
  onDecisionChange,
}: {
  dictionary: Dictionary;
  locale: Locale;
  onDecisionChange?: (decisionId: string | undefined) => void;
}) {
  const copy = dictionary.decisionFeed;
  const [state, setState] = useState<FeedState>({ status: "loading" });
  const [revision, setRevision] = useState(0);
  const [loadingMore, setLoadingMore] = useState(false);
  const [pageError, setPageError] = useState(false);
  const buttons = useRef<Array<HTMLButtonElement | null>>([]);
  const pagination = useRef<AbortController | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    async function load() {
      setState({ status: "loading" });
      setPageError(false);
      onDecisionChange?.(undefined);
      try {
        const page = await decisionFeedPage(null, controller.signal);
        if (controller.signal.aborted) return;
        setState({ status: "ready", page, selected: 0 });
        onDecisionChange?.(decisionContextId(page.items[0]));
      } catch {
        if (!controller.signal.aborted) setState({ status: "error" });
      }
    }
    void load();
    return () => {
      controller.abort();
      pagination.current?.abort();
      pagination.current = null;
    };
  }, [onDecisionChange, revision]);

  const selected = state.status === "ready" ? state.page.items[state.selected] : undefined;

  function select(index: number) {
    if (state.status !== "ready") return;
    setState({ ...state, selected: index });
    onDecisionChange?.(decisionContextId(state.page.items[index]));
  }

  function navigateDecisions(event: KeyboardEvent<HTMLButtonElement>, index: number) {
    if (state.status !== "ready") return;
    const last = state.page.items.length - 1;
    const nextIndex =
      event.key === "ArrowDown"
        ? Math.min(index + 1, last)
        : event.key === "ArrowUp"
          ? Math.max(index - 1, 0)
          : event.key === "Home"
            ? 0
            : event.key === "End"
              ? last
              : undefined;
    if (nextIndex === undefined) return;
    event.preventDefault();
    buttons.current[nextIndex]?.focus();
    select(nextIndex);
  }

  async function loadMore() {
    if (state.status !== "ready" || !state.page.next_cursor || pagination.current) return;
    const controller = new AbortController();
    pagination.current = controller;
    setLoadingMore(true);
    setPageError(false);
    try {
      const page = await decisionFeedPage(state.page.next_cursor, controller.signal);
      if (controller.signal.aborted) return;
      if (page.provider.generation !== state.page.provider.generation) {
        setPageError(true);
        return;
      }
      setState((current) =>
        current.status === "ready"
          ? {
              ...current,
              page: { ...page, items: [...current.page.items, ...page.items] },
            }
          : current,
      );
    } catch {
      if (!controller.signal.aborted) setPageError(true);
    } finally {
      if (pagination.current === controller) {
        pagination.current = null;
        setLoadingMore(false);
      }
    }
  }

  function reload() {
    setLoadingMore(false);
    setRevision((value) => value + 1);
  }

  return (
    <section className="decision-feed" id="decisions">
      <div className="operations-heading">
        <div>
          <h2>{copy.title}</h2>
          <p>{copy.description}</p>
        </div>
      </div>
      {state.status === "loading" ? (
        <Alert className="inline-state" role="status">
          <Spinner label="" /> {copy.loading}
        </Alert>
      ) : null}
      {state.status === "error" ? (
        <ErrorState
          title={copy.error}
          action={
            <Button onClick={reload} variant="secondary">
              {copy.retry}
            </Button>
          }
        />
      ) : null}
      {state.status === "ready" ? (
        <>
          {state.page.provider.state !== "ready" ? (
            <Alert tone="warning" className="provider-state" role="status">
              <strong>{copy.providerDegraded}</strong>
              <p>{copy.providerStates[state.page.provider.state]}</p>
            </Alert>
          ) : null}
          {!selected ? (
            <EmptyState className="empty-state-card" title={copy.emptyTitle}>
              {copy.emptyDescription}
            </EmptyState>
          ) : (
            <div className="decision-workspace">
              <div aria-label={copy.listLabel} className="decision-list" role="group">
                {state.page.items.map((item: DecisionFeedItem, index) => (
                  <Button
                    aria-pressed={state.selected === index}
                    className="decision-list-item"
                    key={`${item.resource_type}:${item.resource_id}`}
                    onClick={() => select(index)}
                    onKeyDown={(event) => navigateDecisions(event, index)}
                    ref={(element) => {
                      buttons.current[index] = element;
                    }}
                    tabIndex={state.selected === index ? 0 : -1}
                    variant="ghost"
                  >
                    <span>
                      <strong>{item.resource_id}</strong>
                      <small>
                        {copy.resourceTypes[item.resource_type]} ·{" "}
                        <WorkspaceTime dateTime={item.source.observed_at} locale={locale} />
                      </small>
                    </span>
                    <ChevronRight aria-hidden="true" size={18} />
                  </Button>
                ))}
                {pageError ? (
                  <Alert tone="warning">
                    <p>{dictionary.decisionPages.feedChanged}</p>
                    <Button variant="secondary" onClick={reload}>
                      {copy.retry}
                    </Button>
                  </Alert>
                ) : state.page.next_cursor ? (
                  <Button
                    disabled={loadingMore}
                    variant="secondary"
                    onClick={() => void loadMore()}
                  >
                    {copy.loadMore}
                  </Button>
                ) : null}
              </div>
              <div className="decision-detail">
                <EvidencePanel copy={copy} item={selected} locale={locale} />
                <Link
                  className="secondary-button decision-open-record"
                  href={decisionHref(locale, {
                    kind: selected.resource_type === "candidate" ? "candidates" : "records",
                    panel: "evidence",
                    resourceId: selected.resource_id,
                  })}
                >
                  {dictionary.decisionPages.openEvidence}
                </Link>
              </div>
            </div>
          )}
        </>
      ) : null}
    </section>
  );
}
