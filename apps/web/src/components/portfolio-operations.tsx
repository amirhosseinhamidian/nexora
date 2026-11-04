"use client";

import {
  AlertTriangle,
  ArrowLeftRight,
  Boxes,
  CheckCircle2,
  FileInput,
  History,
  LoaderCircle,
  RefreshCw,
  Scale,
  ShieldAlert,
} from "lucide-react";
import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";

import type { PortfolioWorkspaceContext } from "@/components/portfolio-dashboard";
import type { Locale } from "@/i18n/config";
import type { Dictionary } from "@/i18n/dictionaries";
import { ApiRequestError, apiRequest } from "@/lib/api-client";

type TransactionLeg = {
  account_id: string | null;
  asset_id: string;
  external_counterparty: string | null;
  quantity: string;
  sequence: number;
  transaction_leg_id: string;
};

type Transaction = {
  correction_kind: "reversal" | "supersession" | null;
  correction_of_transaction_id: string | null;
  legs: TransactionLeg[];
  memo: string | null;
  occurred_at: string;
  recorded_at: string;
  source_kind: "import" | "manual" | "trd_bot";
  source_reference: string;
  transaction_id: string;
  transaction_kind:
    | "adjustment"
    | "airdrop"
    | "buy"
    | "deposit"
    | "fee"
    | "income"
    | "opening_balance"
    | "reward"
    | "sell"
    | "transfer"
    | "withdrawal";
};

type ProjectionCheckpoint = {
  cost_basis_method: CostBasisMethod;
  journal_sha256: string;
  journal_transaction_count: number;
  projection_version: string;
  rebuilt_at: string;
};

type BasisStatus = "known" | "mixed" | "unknown";
type CostBasisMethod = "fifo" | "weighted_average";

type Holding = {
  account_id: string;
  asset_id: string;
  average_unit_cost: string | null;
  basis_status: BasisStatus;
  cost_basis_asset_id: string | null;
  quantity: string;
  total_cost_basis: string | null;
};

type Lot = {
  account_id: string;
  acquired_at: string;
  acquisition_transaction_id: string;
  asset_id: string;
  basis_status: BasisStatus;
  cost_basis_asset_id: string | null;
  lot_key: string;
  original_cost_basis: string | null;
  original_quantity: string;
  remaining_cost_basis: string | null;
  remaining_quantity: string;
};

type ImportRow = {
  external_row_id: string | null;
  import_row_id: string;
  normalized_payload: Record<string, unknown> | null;
  reason_code: string | null;
  row_number: number;
  status: "duplicate" | "published" | "quarantined" | "ready";
};

type ImportBatch = {
  content_sha256: string;
  created_at: string;
  duplicate_count: number;
  import_batch_id: string;
  published_at: string | null;
  quarantined_count: number;
  ready_count: number;
  review_reason: string | null;
  reviewed_at: string | null;
  row_count: number;
  rows: ImportRow[];
  source_format: "csv" | "nexora_json";
  status: "dry_run" | "published" | "quarantined" | "reviewed";
};

type ReconciliationCase = {
  created_at: string;
  difference_code: string;
  import_batch_id: string;
  import_row_id: string;
  reason: string | null;
  reconciliation_case_id: string;
  row_version: number;
  state: "accepted_difference" | "ignored_with_reason" | "matched" | "open" | "resolved";
  transaction_id: string | null;
  updated_at: string;
};

type ListResponse<T> = { items: T[] };
type HoldingListResponse = { checkpoint: ProjectionCheckpoint; items: Holding[] };
type LotListResponse = { checkpoint: ProjectionCheckpoint; items: Lot[] };
type Tab = "holdings" | "imports" | "journal" | "reconciliation";
type ViewState = "error" | "loading" | "ready";

type WorkspaceData = {
  holdings?: HoldingListResponse;
  imports: ImportBatch[];
  lots?: LotListResponse;
  reconciliation: ReconciliationCase[];
  transactions: Transaction[];
};

const emptyData: WorkspaceData = {
  imports: [],
  reconciliation: [],
  transactions: [],
};

function localizeDigits(value: string, locale: Locale): string {
  if (locale === "en") return value;
  return value.replace(/[0-9]/g, (digit) => "۰۱۲۳۴۵۶۷۸۹"[Number(digit)]);
}

function exactDecimal(value: string | null, locale: Locale): string {
  if (value === null) return "—";
  if (locale === "en") return value;
  return localizeDigits(value.replace("-", "−").replace(".", "٫"), locale);
}

function formatTimestamp(value: string, locale: Locale): string {
  return new Intl.DateTimeFormat(locale === "fa" ? "fa-IR" : "en-GB", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function shortId(value: string): string {
  return `${value.slice(0, 8)}…`;
}

async function optionalProjection<T>(path: string, signal: AbortSignal): Promise<T | undefined> {
  try {
    return await apiRequest<T>(path, { signal });
  } catch (error) {
    if (error instanceof ApiRequestError && error.status === 404) return undefined;
    throw error;
  }
}

export function PortfolioOperations({
  context,
  dictionary,
  locale,
  recentlyReauthenticated,
}: {
  context?: PortfolioWorkspaceContext;
  dictionary: Dictionary;
  locale: Locale;
  recentlyReauthenticated: boolean;
}) {
  const copy = dictionary.portfolioOperations;
  const [activeTab, setActiveTab] = useState<Tab>("journal");
  const [basisMethod, setBasisMethod] = useState<CostBasisMethod>("fifo");
  const [data, setData] = useState<WorkspaceData>(emptyData);
  const [state, setState] = useState<ViewState>(context ? "loading" : "ready");
  const [revision, setRevision] = useState(0);
  const [busyAction, setBusyAction] = useState<string>();
  const [feedback, setFeedback] = useState<{ error: boolean; text: string }>();
  const [importFormat, setImportFormat] = useState<"csv" | "nexora_json">("csv");
  const [importContent, setImportContent] = useState("");
  const [reviewReasons, setReviewReasons] = useState<Record<string, string>>({});
  const [decisionReasons, setDecisionReasons] = useState<Record<string, string>>({});
  const [decisionStates, setDecisionStates] = useState<
    Record<string, Exclude<ReconciliationCase["state"], "open">>
  >({});

  useEffect(() => {
    if (!context) return;
    const currentContext = context;
    const controller = new AbortController();
    async function load() {
      setState("loading");
      setFeedback(undefined);
      const portfolio = encodeURIComponent(currentContext.portfolioId);
      const method = encodeURIComponent(basisMethod);
      try {
        const [transactions, holdings, lots, imports, reconciliation] = await Promise.all([
          apiRequest<ListResponse<Transaction>>(`/api/v1/transactions?portfolio_id=${portfolio}`, {
            signal: controller.signal,
          }),
          optionalProjection<HoldingListResponse>(
            `/api/v1/portfolios/${portfolio}/holdings?cost_basis_method=${method}`,
            controller.signal,
          ),
          optionalProjection<LotListResponse>(
            `/api/v1/portfolios/${portfolio}/lots?cost_basis_method=${method}`,
            controller.signal,
          ),
          apiRequest<ListResponse<ImportBatch>>("/api/v1/imports", { signal: controller.signal }),
          apiRequest<ListResponse<ReconciliationCase>>("/api/v1/reconciliation-cases", {
            signal: controller.signal,
          }),
        ]);
        if (controller.signal.aborted) return;
        setData({
          holdings,
          imports: imports.items,
          lots,
          reconciliation: reconciliation.items,
          transactions: transactions.items,
        });
        setState("ready");
      } catch {
        if (!controller.signal.aborted) setState("error");
      }
    }
    void load();
    return () => controller.abort();
  }, [basisMethod, context, revision]);

  const accounts = useMemo(
    () => new Map((context?.accounts ?? []).map((account) => [account.account_id, account])),
    [context?.accounts],
  );
  const assets = useMemo(
    () => new Map((context?.assets ?? []).map((asset) => [asset.asset_id, asset])),
    [context?.assets],
  );
  const retry = useCallback(() => setRevision((value) => value + 1), []);

  async function mutate<T>(key: string, action: () => Promise<T>): Promise<T | undefined> {
    setBusyAction(key);
    setFeedback(undefined);
    try {
      const result = await action();
      setFeedback({ error: false, text: copy.actionSucceeded });
      return result;
    } catch (error) {
      const code = error instanceof ApiRequestError ? error.code : "UNEXPECTED_ERROR";
      setFeedback({ error: true, text: `${copy.actionFailed} (${code})` });
      return undefined;
    } finally {
      setBusyAction(undefined);
    }
  }

  async function rebuildHoldings() {
    if (!context) return;
    const portfolio = encodeURIComponent(context.portfolioId);
    const result = await mutate("rebuild", () =>
      apiRequest(`/api/v1/portfolios/${portfolio}/holdings/rebuilds`, {
        body: { cost_basis_method: basisMethod },
        method: "POST",
      }),
    );
    if (result) retry();
  }

  async function createDryRun(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const created = await mutate<ImportBatch>("dry-run", () =>
      apiRequest("/api/v1/imports/dry-runs", {
        body: { content: importContent, source_format: importFormat },
        method: "POST",
      }),
    );
    if (created) {
      setImportContent("");
      setData((current) => ({ ...current, imports: [created, ...current.imports] }));
    }
  }

  async function reviewBatch(batch: ImportBatch) {
    const reason = reviewReasons[batch.import_batch_id]?.trim() ?? "";
    if (reason.length < 8) {
      setFeedback({ error: true, text: copy.reasonRequired });
      return;
    }
    const reviewed = await mutate<ImportBatch>(`review-${batch.import_batch_id}`, () =>
      apiRequest(`/api/v1/imports/${encodeURIComponent(batch.import_batch_id)}/reviews`, {
        body: { reason },
        method: "POST",
      }),
    );
    if (reviewed) {
      setData((current) => ({
        ...current,
        imports: current.imports.map((item) =>
          item.import_batch_id === reviewed.import_batch_id ? reviewed : item,
        ),
      }));
    }
  }

  async function publishBatch(batch: ImportBatch) {
    const published = await mutate<ImportBatch>(`publish-${batch.import_batch_id}`, () =>
      apiRequest(`/api/v1/imports/${encodeURIComponent(batch.import_batch_id)}/publication`, {
        body: {},
        method: "POST",
      }),
    );
    if (published) {
      setData((current) => ({
        ...current,
        imports: current.imports.map((item) =>
          item.import_batch_id === published.import_batch_id ? published : item,
        ),
      }));
      retry();
    }
  }

  async function decideCase(item: ReconciliationCase) {
    const reason = decisionReasons[item.reconciliation_case_id]?.trim() ?? "";
    if (reason.length < 8) {
      setFeedback({ error: true, text: copy.reasonRequired });
      return;
    }
    const nextState = decisionStates[item.reconciliation_case_id] ?? "matched";
    const decided = await mutate<ReconciliationCase>(
      `decision-${item.reconciliation_case_id}`,
      () =>
        apiRequest(
          `/api/v1/reconciliation-cases/${encodeURIComponent(item.reconciliation_case_id)}/decisions`,
          {
            body: { expected_row_version: item.row_version, reason, state: nextState },
            method: "POST",
          },
        ),
    );
    if (decided) {
      setData((current) => ({
        ...current,
        reconciliation: current.reconciliation.map((candidate) =>
          candidate.reconciliation_case_id === decided.reconciliation_case_id ? decided : candidate,
        ),
      }));
    }
  }

  const tabs: Array<{ icon: typeof History; id: Tab; label: string }> = [
    { icon: History, id: "journal", label: copy.tabs.journal },
    { icon: Boxes, id: "holdings", label: copy.tabs.holdings },
    { icon: FileInput, id: "imports", label: copy.tabs.imports },
    { icon: Scale, id: "reconciliation", label: copy.tabs.reconciliation },
  ];

  return (
    <section
      aria-labelledby="portfolio-operations-title"
      className="portfolio-operations"
      id="portfolio-operations"
    >
      <div className="operations-heading">
        <div>
          <p className="section-kicker">{copy.eyebrow}</p>
          <h2 id="portfolio-operations-title">{copy.title}</h2>
          <p>{copy.description}</p>
        </div>
        {context && <span className="operations-context">{context.portfolioName}</span>}
      </div>

      {!context ? (
        <div className="dashboard-state compact">
          <Boxes aria-hidden="true" size={24} />
          <p>{copy.noPortfolio}</p>
        </div>
      ) : (
        <>
          <div aria-label={copy.tabs.label} className="operations-tabs" role="tablist">
            {tabs.map(({ icon: Icon, id, label }) => (
              <button
                aria-controls={`operations-panel-${id}`}
                aria-selected={activeTab === id}
                className={activeTab === id ? "active" : ""}
                id={`operations-tab-${id}`}
                key={id}
                onClick={() => setActiveTab(id)}
                role="tab"
                type="button"
              >
                <Icon aria-hidden="true" size={18} />
                {label}
              </button>
            ))}
          </div>

          {feedback && (
            <div
              className={`operations-feedback ${feedback.error ? "error" : "success"}`}
              role="status"
            >
              {feedback.error ? (
                <AlertTriangle aria-hidden="true" size={18} />
              ) : (
                <CheckCircle2 aria-hidden="true" size={18} />
              )}
              <span>{feedback.text}</span>
            </div>
          )}

          {state === "loading" ? (
            <div aria-live="polite" className="dashboard-state compact">
              <LoaderCircle aria-hidden="true" className="spin" size={24} />
              <p>{copy.loading}</p>
            </div>
          ) : state === "error" ? (
            <div className="dashboard-state compact error" role="alert">
              <ShieldAlert aria-hidden="true" size={24} />
              <div>
                <p>{copy.loadError}</p>
                <button className="secondary-button" onClick={retry} type="button">
                  <RefreshCw aria-hidden="true" size={17} />
                  {copy.retry}
                </button>
              </div>
            </div>
          ) : (
            <>
              <div
                aria-labelledby="operations-tab-journal"
                className="operations-panel"
                hidden={activeTab !== "journal"}
                id="operations-panel-journal"
                role="tabpanel"
              >
                <div className="panel-heading">
                  <div>
                    <h3>{copy.journal.title}</h3>
                    <p>{copy.journal.description}</p>
                  </div>
                  <span className="count-badge">
                    {localizeDigits(String(data.transactions.length), locale)}
                  </span>
                </div>
                {data.transactions.length === 0 ? (
                  <p className="inline-empty">{copy.journal.empty}</p>
                ) : (
                  <div className="operations-card-list">
                    {data.transactions.map((transaction) => (
                      <article className="operation-card" key={transaction.transaction_id}>
                        <div className="operation-card-heading">
                          <div>
                            <span className="status-badge active">
                              {copy.transactionKind[transaction.transaction_kind]}
                            </span>
                            {transaction.correction_kind && (
                              <span className="status-badge archived">
                                {copy.correctionKind[transaction.correction_kind]}
                              </span>
                            )}
                          </div>
                          <time dateTime={transaction.occurred_at}>
                            {formatTimestamp(transaction.occurred_at, locale)}
                          </time>
                        </div>
                        <p>{transaction.memo ?? copy.journal.noMemo}</p>
                        <ul className="journal-legs">
                          {transaction.legs.map((leg) => (
                            <li key={leg.transaction_leg_id}>
                              <span>
                                {leg.account_id
                                  ? (accounts.get(leg.account_id)?.name ?? shortId(leg.account_id))
                                  : (leg.external_counterparty ?? copy.journal.external)}
                              </span>
                              <strong dir="ltr">
                                {exactDecimal(leg.quantity, locale)}{" "}
                                {assets.get(leg.asset_id)?.symbol ?? shortId(leg.asset_id)}
                              </strong>
                            </li>
                          ))}
                        </ul>
                        <div className="operation-lineage">
                          <code dir="ltr">{shortId(transaction.transaction_id)}</code>
                          <span>{copy.sourceKind[transaction.source_kind]}</span>
                          <code dir="ltr">{transaction.source_reference}</code>
                        </div>
                      </article>
                    ))}
                  </div>
                )}
              </div>

              <div
                aria-labelledby="operations-tab-holdings"
                className="operations-panel"
                hidden={activeTab !== "holdings"}
                id="operations-panel-holdings"
                role="tabpanel"
              >
                <div className="panel-heading holdings-controls">
                  <div>
                    <h3>{copy.holdings.title}</h3>
                    <p>{copy.holdings.description}</p>
                  </div>
                  <div>
                    <label>
                      <span>{copy.holdings.method}</span>
                      <select
                        onChange={(event) => setBasisMethod(event.target.value as CostBasisMethod)}
                        value={basisMethod}
                      >
                        <option value="fifo">{copy.holdings.fifo}</option>
                        <option value="weighted_average">{copy.holdings.weightedAverage}</option>
                      </select>
                    </label>
                    <button
                      className="secondary-button"
                      disabled={busyAction === "rebuild"}
                      onClick={() => void rebuildHoldings()}
                      type="button"
                    >
                      {busyAction === "rebuild" ? (
                        <LoaderCircle aria-hidden="true" className="spin" size={17} />
                      ) : (
                        <RefreshCw aria-hidden="true" size={17} />
                      )}
                      {copy.holdings.rebuild}
                    </button>
                  </div>
                </div>
                {!data.holdings || !data.lots ? (
                  <div className="inline-empty projection-empty">
                    <AlertTriangle aria-hidden="true" size={20} />
                    <span>{copy.holdings.notBuilt}</span>
                  </div>
                ) : (
                  <>
                    <div className="projection-checkpoint">
                      <span>
                        {copy.holdings.version}:{" "}
                        <b>{data.holdings.checkpoint.projection_version}</b>
                      </span>
                      <span>
                        {copy.holdings.transactions}:{" "}
                        <b>
                          {localizeDigits(
                            String(data.holdings.checkpoint.journal_transaction_count),
                            locale,
                          )}
                        </b>
                      </span>
                      <code dir="ltr">{shortId(data.holdings.checkpoint.journal_sha256)}</code>
                    </div>
                    <h4 className="subsection-title">{copy.holdings.positions}</h4>
                    {data.holdings.items.length === 0 ? (
                      <p className="inline-empty">{copy.holdings.empty}</p>
                    ) : (
                      <div className="responsive-data-grid">
                        {data.holdings.items.map((holding) => (
                          <article
                            className="data-card"
                            key={`${holding.account_id}-${holding.asset_id}`}
                          >
                            <div>
                              <strong>
                                {assets.get(holding.asset_id)?.name ?? shortId(holding.asset_id)}
                              </strong>
                              <span className={`basis-badge ${holding.basis_status}`}>
                                {copy.basisStatus[holding.basis_status]}
                              </span>
                            </div>
                            <dl>
                              <div>
                                <dt>{copy.holdings.account}</dt>
                                <dd>
                                  {accounts.get(holding.account_id)?.name ??
                                    shortId(holding.account_id)}
                                </dd>
                              </div>
                              <div>
                                <dt>{copy.holdings.quantity}</dt>
                                <dd dir="ltr">{exactDecimal(holding.quantity, locale)}</dd>
                              </div>
                              <div>
                                <dt>{copy.holdings.costBasis}</dt>
                                <dd dir="ltr">{exactDecimal(holding.total_cost_basis, locale)}</dd>
                              </div>
                            </dl>
                          </article>
                        ))}
                      </div>
                    )}
                    <h4 className="subsection-title">{copy.holdings.lots}</h4>
                    {data.lots.items.length === 0 ? (
                      <p className="inline-empty">{copy.holdings.noLots}</p>
                    ) : (
                      <div className="responsive-data-grid">
                        {data.lots.items.map((lot) => (
                          <article className="data-card" key={lot.lot_key}>
                            <div>
                              <strong>
                                {assets.get(lot.asset_id)?.name ?? shortId(lot.asset_id)}
                              </strong>
                              <span className={`basis-badge ${lot.basis_status}`}>
                                {copy.basisStatus[lot.basis_status]}
                              </span>
                            </div>
                            <dl>
                              <div>
                                <dt>{copy.holdings.acquired}</dt>
                                <dd>{formatTimestamp(lot.acquired_at, locale)}</dd>
                              </div>
                              <div>
                                <dt>{copy.holdings.remaining}</dt>
                                <dd dir="ltr">{exactDecimal(lot.remaining_quantity, locale)}</dd>
                              </div>
                              <div>
                                <dt>{copy.holdings.costBasis}</dt>
                                <dd dir="ltr">{exactDecimal(lot.remaining_cost_basis, locale)}</dd>
                              </div>
                            </dl>
                          </article>
                        ))}
                      </div>
                    )}
                  </>
                )}
              </div>

              <div
                aria-labelledby="operations-tab-imports"
                className="operations-panel"
                hidden={activeTab !== "imports"}
                id="operations-panel-imports"
                role="tabpanel"
              >
                <div className="panel-heading">
                  <div>
                    <h3>{copy.imports.title}</h3>
                    <p>{copy.imports.description}</p>
                  </div>
                </div>
                <form className="import-form" onSubmit={(event) => void createDryRun(event)}>
                  <label>
                    <span>{copy.imports.format}</span>
                    <select
                      onChange={(event) =>
                        setImportFormat(event.target.value as "csv" | "nexora_json")
                      }
                      value={importFormat}
                    >
                      <option value="csv">CSV</option>
                      <option value="nexora_json">Nexora JSON</option>
                    </select>
                  </label>
                  <label>
                    <span>{copy.imports.content}</span>
                    <textarea
                      maxLength={1_048_576}
                      onChange={(event) => setImportContent(event.target.value)}
                      placeholder={copy.imports.placeholder}
                      required
                      rows={8}
                      value={importContent}
                    />
                  </label>
                  <p>{copy.imports.dryRunNotice}</p>
                  <button
                    className="primary-button compact-action"
                    disabled={busyAction === "dry-run" || !importContent.trim()}
                    type="submit"
                  >
                    {busyAction === "dry-run" ? (
                      <LoaderCircle aria-hidden="true" className="spin" size={18} />
                    ) : (
                      <FileInput aria-hidden="true" size={18} />
                    )}
                    {copy.imports.preview}
                  </button>
                </form>
                <div className="operations-card-list import-batches">
                  {data.imports.map((batch) => (
                    <article className="operation-card" key={batch.import_batch_id}>
                      <div className="operation-card-heading">
                        <div>
                          <span className={`status-badge ${batch.status}`}>
                            {copy.importStatus[batch.status]}
                          </span>
                          <b>{batch.source_format === "csv" ? "CSV" : "Nexora JSON"}</b>
                        </div>
                        <time dateTime={batch.created_at}>
                          {formatTimestamp(batch.created_at, locale)}
                        </time>
                      </div>
                      <div className="import-counts">
                        <span>
                          {copy.imports.rows}: {localizeDigits(String(batch.row_count), locale)}
                        </span>
                        <span>
                          {copy.imports.ready}: {localizeDigits(String(batch.ready_count), locale)}
                        </span>
                        <span>
                          {copy.imports.duplicates}:{" "}
                          {localizeDigits(String(batch.duplicate_count), locale)}
                        </span>
                        <span>
                          {copy.imports.quarantined}:{" "}
                          {localizeDigits(String(batch.quarantined_count), locale)}
                        </span>
                      </div>
                      {batch.rows.length > 0 && (
                        <details className="import-preview">
                          <summary>{copy.imports.showRows}</summary>
                          {batch.rows.slice(0, 20).map((row) => (
                            <div className="import-row" key={row.import_row_id}>
                              <div>
                                <b>#{localizeDigits(String(row.row_number), locale)}</b>
                                <span className={`status-badge ${row.status}`}>
                                  {copy.importRowStatus[row.status]}
                                </span>
                                {row.reason_code && <code dir="ltr">{row.reason_code}</code>}
                              </div>
                              {row.normalized_payload && (
                                <pre dir="ltr">
                                  {JSON.stringify(row.normalized_payload, null, 2)}
                                </pre>
                              )}
                            </div>
                          ))}
                        </details>
                      )}
                      {batch.status === "dry_run" && batch.quarantined_count === 0 && (
                        <div className="bounded-action-form">
                          <label>
                            <span>{copy.reason}</span>
                            <input
                              minLength={8}
                              onChange={(event) =>
                                setReviewReasons((current) => ({
                                  ...current,
                                  [batch.import_batch_id]: event.target.value,
                                }))
                              }
                              value={reviewReasons[batch.import_batch_id] ?? ""}
                            />
                          </label>
                          <button
                            className="secondary-button"
                            disabled={busyAction === `review-${batch.import_batch_id}`}
                            onClick={() => void reviewBatch(batch)}
                            type="button"
                          >
                            {copy.imports.review}
                          </button>
                        </div>
                      )}
                      {batch.status === "reviewed" && (
                        <button
                          className="secondary-button"
                          disabled={
                            !recentlyReauthenticated ||
                            busyAction === `publish-${batch.import_batch_id}`
                          }
                          onClick={() => void publishBatch(batch)}
                          type="button"
                        >
                          {copy.imports.publish}
                        </button>
                      )}
                      {batch.status === "reviewed" && !recentlyReauthenticated && (
                        <p className="reauth-notice">{copy.reauthenticationRequired}</p>
                      )}
                      <div className="operation-lineage">
                        <code dir="ltr">{shortId(batch.import_batch_id)}</code>
                        <code dir="ltr">sha256:{shortId(batch.content_sha256)}</code>
                      </div>
                    </article>
                  ))}
                  {data.imports.length === 0 && (
                    <p className="inline-empty">{copy.imports.empty}</p>
                  )}
                </div>
              </div>

              <div
                aria-labelledby="operations-tab-reconciliation"
                className="operations-panel"
                hidden={activeTab !== "reconciliation"}
                id="operations-panel-reconciliation"
                role="tabpanel"
              >
                <div className="panel-heading">
                  <div>
                    <h3>{copy.reconciliation.title}</h3>
                    <p>{copy.reconciliation.description}</p>
                  </div>
                  <span className="count-badge">
                    {localizeDigits(String(data.reconciliation.length), locale)}
                  </span>
                </div>
                {data.reconciliation.length === 0 ? (
                  <p className="inline-empty">{copy.reconciliation.empty}</p>
                ) : (
                  <div className="operations-card-list">
                    {data.reconciliation.map((item) => (
                      <article className="operation-card" key={item.reconciliation_case_id}>
                        <div className="operation-card-heading">
                          <div>
                            <span className={`status-badge ${item.state}`}>
                              {copy.reconciliationState[item.state]}
                            </span>
                            <code dir="ltr">{item.difference_code}</code>
                          </div>
                          <time dateTime={item.updated_at}>
                            {formatTimestamp(item.updated_at, locale)}
                          </time>
                        </div>
                        {item.reason && <p>{item.reason}</p>}
                        {item.state === "open" && (
                          <div className="decision-form">
                            <label>
                              <span>{copy.reconciliation.decision}</span>
                              <select
                                onChange={(event) =>
                                  setDecisionStates((current) => ({
                                    ...current,
                                    [item.reconciliation_case_id]: event.target.value as Exclude<
                                      ReconciliationCase["state"],
                                      "open"
                                    >,
                                  }))
                                }
                                value={decisionStates[item.reconciliation_case_id] ?? "matched"}
                              >
                                {(
                                  [
                                    "matched",
                                    "accepted_difference",
                                    "resolved",
                                    "ignored_with_reason",
                                  ] as const
                                ).map((state) => (
                                  <option key={state} value={state}>
                                    {copy.reconciliationState[state]}
                                  </option>
                                ))}
                              </select>
                            </label>
                            <label>
                              <span>{copy.reason}</span>
                              <input
                                minLength={8}
                                onChange={(event) =>
                                  setDecisionReasons((current) => ({
                                    ...current,
                                    [item.reconciliation_case_id]: event.target.value,
                                  }))
                                }
                                value={decisionReasons[item.reconciliation_case_id] ?? ""}
                              />
                            </label>
                            <button
                              className="secondary-button"
                              disabled={
                                !recentlyReauthenticated ||
                                busyAction === `decision-${item.reconciliation_case_id}`
                              }
                              onClick={() => void decideCase(item)}
                              type="button"
                            >
                              <ArrowLeftRight aria-hidden="true" size={17} />
                              {copy.reconciliation.apply}
                            </button>
                            {!recentlyReauthenticated && (
                              <p className="reauth-notice">{copy.reauthenticationRequired}</p>
                            )}
                          </div>
                        )}
                        <div className="operation-lineage">
                          <code dir="ltr">{shortId(item.reconciliation_case_id)}</code>
                          <span>v{localizeDigits(String(item.row_version), locale)}</span>
                          {item.transaction_id && (
                            <code dir="ltr">{shortId(item.transaction_id)}</code>
                          )}
                        </div>
                      </article>
                    ))}
                  </div>
                )}
              </div>
            </>
          )}
        </>
      )}
    </section>
  );
}
