"use client";

import {
  Alert,
  Button,
  ConfirmationDialog,
  EmptyState,
  ErrorState,
  IconButton,
  Spinner,
  ToastRegion,
} from "@nexora/ui/primitives";
import { useEffect, useRef, useState, type ReactNode } from "react";

import { AccountingImports } from "@/components/accounting-imports";
import { AccountingJournal } from "@/components/accounting-journal";
import { AccountingProjection } from "@/components/accounting-projection";
import { AccountingReconciliation } from "@/components/accounting-reconciliation";
import type { PortfolioWorkspaceContext } from "@/components/portfolio-dashboard";
import type { Locale } from "@/i18n/config";
import type { Dictionary } from "@/i18n/dictionaries";
import { ApiRequestError } from "@/lib/api-client";
import {
  decideAccountingCase,
  loadAccountingView,
  needsAccountingPortfolio,
  previewAccountingImport,
  publishAccountingImport,
  rebuildAccountingProjection,
  reviewAccountingImport,
  type AccountingData,
  type AccountingView,
  type CostBasisMethod,
} from "@/lib/portfolio-accounting";

type Action = (signal: AbortSignal) => Promise<unknown>;
type Confirmation = {
  description: ReactNode;
  label: string;
  perform: Action;
  sensitive?: boolean;
  title: string;
};

export function PortfolioOperations({
  basis,
  context,
  dictionary,
  locale,
  onBasisChange,
  onReauthenticate,
  onRefreshSession,
  recentlyReauthenticated,
  view,
}: {
  basis: CostBasisMethod;
  context?: PortfolioWorkspaceContext;
  dictionary: Dictionary;
  locale: Locale;
  onBasisChange: (basis: CostBasisMethod) => void;
  onReauthenticate?: Action;
  onRefreshSession?: Action;
  recentlyReauthenticated: boolean;
  view: AccountingView;
}) {
  const copy = dictionary.portfolioOperations;
  const portfolioId = context?.portfolioId;
  const needsPortfolio = needsAccountingPortfolio(view);
  const request = useRef<AbortController | null>(null);
  const [revision, setRevision] = useState(0);
  const [loaded, setLoaded] = useState<{ data: AccountingData; revision: number }>();
  const [failedRevision, setFailedRevision] = useState<number>();
  const [pending, setPending] = useState(false);
  const [confirmation, setConfirmation] = useState<Confirmation>();
  const [notice, setNotice] = useState<{ title: string; tone: "success" | "warning" | "danger" }>();

  const failed = failedRevision === revision;
  const refreshing = loaded?.revision !== revision && !failed;
  const busy = pending || refreshing || failed;

  useEffect(() => {
    if (needsPortfolio && !portfolioId) return;
    const controller = new AbortController();
    void loadAccountingView(view, portfolioId, basis, controller.signal).then(
      (data) => {
        if (!controller.signal.aborted) setLoaded({ data, revision });
      },
      () => {
        if (!controller.signal.aborted) setFailedRevision(revision);
      },
    );
    return () => controller.abort();
  }, [basis, needsPortfolio, portfolioId, revision, view]);

  useEffect(() => () => request.current?.abort(), []);

  useEffect(() => {
    if (notice?.tone !== "success") return;
    const timer = window.setTimeout(() => setNotice(undefined), 6000);
    return () => window.clearTimeout(timer);
  }, [notice]);

  function refresh() {
    setRevision((value) => value + 1);
  }

  async function run(
    perform: Action,
    options: { invalidInputMessage?: string; sensitive?: boolean; verifying?: boolean } = {},
  ) {
    if (request.current || busy || (options.sensitive && !recentlyReauthenticated)) return false;
    const controller = new AbortController();
    request.current = controller;
    setConfirmation(undefined);
    setNotice(undefined);
    setPending(true);
    try {
      await perform(controller.signal);
      if (controller.signal.aborted) return false;
      setNotice({
        title: options.verifying ? copy.reauthenticated : copy.actionSucceeded,
        tone: "success",
      });
      if (!options.verifying) refresh();
      return true;
    } catch (error) {
      if (controller.signal.aborted) return false;
      const status = error instanceof ApiRequestError ? error.status : undefined;
      if (status === 401 && (options.sensitive || options.verifying)) {
        // The API uses 401 for stale verification and expired sessions. Check the session before recovering.
        try {
          await onRefreshSession?.(controller.signal);
        } catch {
          /* The session client handles expiry. */
        }
      }
      if (controller.signal.aborted) return false;
      if (options.verifying) {
        setNotice({ title: copy.reauthenticationFailed, tone: "danger" });
      } else if (status === 409 || status === 404) {
        setNotice({ title: copy.changedRecord, tone: "warning" });
        refresh();
      } else if (status === 401 && options.sensitive) {
        setNotice({ title: copy.reauthenticationRequired, tone: "warning" });
      } else if (status === 413 && view === "imports") {
        setNotice({ title: copy.imports.sizeError, tone: "danger" });
      } else if (status === 400 || status === 422) {
        setNotice({ title: options.invalidInputMessage ?? copy.invalidInput, tone: "danger" });
      } else {
        setNotice({ title: copy.actionFailed, tone: "danger" });
        refresh();
      }
      return false;
    } finally {
      request.current = null;
      if (!controller.signal.aborted) setPending(false);
    }
  }

  function requestConfirmation(action: Confirmation) {
    if (request.current || busy || (action.sensitive && !recentlyReauthenticated)) return;
    setNotice(undefined);
    setConfirmation(action);
  }

  const data = loaded?.data;
  let panel: ReactNode;

  switch (data?.view) {
    case "journal":
      if (context)
        panel = (
          <AccountingJournal
            context={context}
            copy={copy}
            locale={locale}
            transactions={data.items}
          />
        );
      break;
    case "holdings":
    case "lots":
      if (context && portfolioId) {
        panel = (
          <AccountingProjection
            basis={basis}
            busy={busy}
            context={context}
            copy={copy}
            data={data}
            locale={locale}
            onBasisChange={onBasisChange}
            onRebuild={() =>
              requestConfirmation({
                description: (
                  <>
                    <bdi>{context.portfolioName}</bdi> ·{" "}
                    {basis === "fifo" ? copy.holdings.fifo : copy.holdings.weightedAverage}
                    <br />
                    {copy.holdings.confirmDescription}
                  </>
                ),
                label: copy.holdings.rebuild,
                perform: (signal) => rebuildAccountingProjection(portfolioId, basis, signal),
                title: copy.holdings.confirmTitle,
              })
            }
          />
        );
      }
      break;
    case "imports":
      panel = (
        <AccountingImports
          busy={busy}
          copy={copy}
          imports={data.items}
          locale={locale}
          onDryRun={(format, text) =>
            run((signal) => previewAccountingImport(format, text, signal), {
              invalidInputMessage: copy.imports.formatError,
            })
          }
          onPublish={(batch) =>
            requestConfirmation({
              description: (
                <>
                  <code dir="ltr">{batch.import_batch_id}</code>
                  <br />
                  {copy.imports.publishDescription}
                </>
              ),
              label: copy.imports.publish,
              perform: (signal) => publishAccountingImport(batch.import_batch_id, signal),
              sensitive: true,
              title: copy.imports.publishTitle,
            })
          }
          onReview={(batch, reason) =>
            requestConfirmation({
              description: (
                <>
                  <code dir="ltr">{batch.import_batch_id}</code>
                  <br />
                  {copy.imports.reviewDescription}
                  <br />
                  <bdi>{reason}</bdi>
                </>
              ),
              label: copy.imports.review,
              perform: (signal) => reviewAccountingImport(batch.import_batch_id, reason, signal),
              title: copy.imports.reviewTitle,
            })
          }
          recentlyReauthenticated={recentlyReauthenticated}
        />
      );
      break;
    case "reconciliation":
      panel = (
        <AccountingReconciliation
          busy={busy}
          cases={data.items}
          copy={copy}
          locale={locale}
          onDecide={(item, state, reason) =>
            requestConfirmation({
              description: (
                <>
                  <code dir="ltr">{item.reconciliation_case_id}</code>
                  <br />
                  {copy.reconciliationState[state]} · <bdi>{reason}</bdi>
                  <br />
                  {copy.reconciliation.confirmDescription}
                </>
              ),
              label: copy.reconciliation.apply,
              perform: (signal) => decideAccountingCase(item, state, reason, signal),
              sensitive: true,
              title: copy.reconciliation.confirmTitle,
            })
          }
          recentlyReauthenticated={recentlyReauthenticated}
        />
      );
      break;
  }

  const gated =
    (data?.view === "imports" &&
      data.items.some((batch) => batch.status === "reviewed" && batch.quarantined_count === 0)) ||
    (data?.view === "reconciliation" && data.items.some((item) => item.state === "open"));

  return (
    <section
      aria-labelledby="portfolio-operations-title"
      className="portfolio-operations"
      id="portfolio-operations"
    >
      <div className="operations-heading">
        <div>
          <h2 id="portfolio-operations-title">{copy.title}</h2>
          <p>{needsPortfolio ? copy.description : copy.ownerScope}</p>
        </div>
        {needsPortfolio && context ? (
          <span className="operations-context">{context.portfolioName}</span>
        ) : null}
      </div>
      <ToastRegion
        label={copy.notifications}
        messages={
          notice
            ? [
                {
                  ...notice,
                  id: "accounting-result",
                  action: (
                    <IconButton
                      aria-label={copy.dismissNotification}
                      onClick={() => setNotice(undefined)}
                      size="sm"
                    >
                      <span aria-hidden="true">×</span>
                    </IconButton>
                  ),
                },
              ]
            : []
        }
      />
      {needsPortfolio && !portfolioId ? (
        <EmptyState title={copy.noPortfolio} />
      ) : (
        <>
          {refreshing || pending ? <Spinner label={pending ? copy.saving : copy.loading} /> : null}
          {failed ? (
            <ErrorState
              title={copy.loadError}
              action={
                <Button onClick={refresh} variant="secondary">
                  {copy.retry}
                </Button>
              }
            >
              {copy.retryHint}
            </ErrorState>
          ) : null}
          {!recentlyReauthenticated && gated ? (
            <Alert className="reauth-notice" tone="warning">
              <p>{copy.reauthenticationRequired}</p>
              {onReauthenticate ? (
                <Button
                  disabled={busy}
                  onClick={() => void run(onReauthenticate, { verifying: true })}
                  variant="secondary"
                >
                  {copy.reauthenticate}
                </Button>
              ) : null}
            </Alert>
          ) : null}
          {panel ? <div className="operations-panel">{panel}</div> : null}
        </>
      )}
      {confirmation ? (
        <ConfirmationDialog
          cancelLabel={copy.cancel}
          confirmLabel={confirmation.label}
          description={confirmation.description}
          destructive={confirmation.sensitive}
          onCancel={() => setConfirmation(undefined)}
          onConfirm={() => void run(confirmation.perform, { sensitive: confirmation.sensitive })}
          open
          title={confirmation.title}
        />
      ) : null}
    </section>
  );
}
