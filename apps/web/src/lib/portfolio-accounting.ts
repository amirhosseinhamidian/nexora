import type { Locale } from "@/i18n/config";
import { ApiRequestError, apiRequest } from "@/lib/api-client";
import { localizeDigits } from "@/lib/portfolio-analytics";

type TransactionLeg = {
  account_id: string | null;
  asset_id: string;
  external_counterparty: string | null;
  quantity: string;
  sequence: number;
  transaction_leg_id: string;
};

export type Transaction = {
  correction_kind: "reversal" | "supersession" | null;
  correction_of_transaction_id: string | null;
  correction_reason: string | null;
  legs: TransactionLeg[];
  memo: string | null;
  occurred_at: string;
  recorded_at: string;
  source_kind: "import" | "manual" | "trd_bot";
  source_payload_sha256: string;
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
export type CostBasisMethod = "fifo" | "weighted_average";

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

export type ImportBatch = {
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

export type ReconciliationCase = {
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

export const accountingViews = [
  "journal",
  "holdings",
  "lots",
  "imports",
  "reconciliation",
] as const;
export type AccountingView = (typeof accountingViews)[number];
export type AccountingQuery = { portfolio?: string | string[]; basis?: string | string[] };
export type ImportFormat = ImportBatch["source_format"];
export type ReconciliationDecision = Exclude<ReconciliationCase["state"], "open">;
export const maxImportBytes = 1_048_576;

export function accountingHref(
  locale: Locale,
  view: AccountingView,
  portfolio: string | undefined,
  basis: CostBasisMethod,
) {
  const query = new URLSearchParams();
  if (portfolio) query.set("portfolio", portfolio);
  if (basis === "weighted_average") query.set("basis", basis);
  const search = query.size ? `?${query}` : "";
  return `/${locale}/transactions${view === "journal" ? "" : `/${view}`}${search}`;
}

export function needsAccountingPortfolio(view: AccountingView) {
  return view === "journal" || view === "holdings" || view === "lots";
}

export function exactDecimal(value: string | null, locale: Locale): string {
  if (value === null) return "—";
  return locale === "en"
    ? value
    : localizeDigits(value.replace("-", "−").replace(".", "٫"), locale);
}

export type AccountingData =
  | { view: "journal"; items: Transaction[] }
  | { view: "holdings"; projection?: HoldingListResponse }
  | { view: "lots"; projection?: LotListResponse }
  | { view: "imports"; items: ImportBatch[] }
  | { view: "reconciliation"; items: ReconciliationCase[] };

async function optionalProjection<T>(path: string, signal: AbortSignal): Promise<T | undefined> {
  try {
    return await apiRequest<T>(path, { signal });
  } catch (error) {
    if (error instanceof ApiRequestError && error.status === 404) return undefined;
    throw error;
  }
}

export async function loadAccountingView(
  view: AccountingView,
  portfolioId: string | undefined,
  basis: CostBasisMethod,
  signal: AbortSignal,
): Promise<AccountingData> {
  if (needsAccountingPortfolio(view) && !portfolioId) throw new Error("Select a portfolio");
  const portfolio = encodeURIComponent(portfolioId ?? "");
  const method = encodeURIComponent(basis);
  switch (view) {
    case "journal": {
      const { items } = await apiRequest<ListResponse<Transaction>>(
        `/api/v1/transactions?portfolio_id=${portfolio}`,
        { signal },
      );
      return { view, items };
    }
    case "holdings":
      return {
        view,
        projection: await optionalProjection<HoldingListResponse>(
          `/api/v1/portfolios/${portfolio}/holdings?cost_basis_method=${method}`,
          signal,
        ),
      };
    case "lots":
      return {
        view,
        projection: await optionalProjection<LotListResponse>(
          `/api/v1/portfolios/${portfolio}/lots?cost_basis_method=${method}`,
          signal,
        ),
      };
    case "imports": {
      const { items } = await apiRequest<ListResponse<ImportBatch>>("/api/v1/imports", { signal });
      return { view, items };
    }
    case "reconciliation": {
      const { items } = await apiRequest<ListResponse<ReconciliationCase>>(
        "/api/v1/reconciliation-cases",
        { signal },
      );
      return { view, items };
    }
  }
}

export function rebuildAccountingProjection(
  portfolioId: string,
  basis: CostBasisMethod,
  signal: AbortSignal,
) {
  return apiRequest(`/api/v1/portfolios/${encodeURIComponent(portfolioId)}/holdings/rebuilds`, {
    body: { cost_basis_method: basis },
    method: "POST",
    signal,
  });
}

export function accountingImportBody(format: ImportFormat, content: string) {
  return { content, source_format: format };
}

export function previewAccountingImport(
  format: ImportFormat,
  content: string,
  signal: AbortSignal,
) {
  return apiRequest<ImportBatch>("/api/v1/imports/dry-runs", {
    body: accountingImportBody(format, content),
    method: "POST",
    signal,
  });
}

export function reviewAccountingImport(batchId: string, reason: string, signal: AbortSignal) {
  return apiRequest<ImportBatch>(`/api/v1/imports/${encodeURIComponent(batchId)}/reviews`, {
    body: { reason },
    method: "POST",
    signal,
  });
}

export function publishAccountingImport(batchId: string, signal: AbortSignal) {
  return apiRequest<ImportBatch>(`/api/v1/imports/${encodeURIComponent(batchId)}/publication`, {
    body: {},
    method: "POST",
    signal,
    signalSessionExpiry: false,
  });
}

export function decideAccountingCase(
  item: ReconciliationCase,
  state: ReconciliationDecision,
  reason: string,
  signal: AbortSignal,
) {
  return apiRequest<ReconciliationCase>(
    `/api/v1/reconciliation-cases/${encodeURIComponent(item.reconciliation_case_id)}/decisions`,
    {
      body: { expected_row_version: item.row_version, reason, state },
      method: "POST",
      signal,
      signalSessionExpiry: false,
    },
  );
}
