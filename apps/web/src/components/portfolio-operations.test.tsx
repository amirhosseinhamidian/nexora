import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import en from "../../messages/en.json";
import { apiRequest } from "@/lib/api-client";
import { PortfolioOperations } from "./portfolio-operations";

vi.mock("@/lib/api-client", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api-client")>("@/lib/api-client");
  return { ...actual, apiRequest: vi.fn() };
});

const request = vi.mocked(apiRequest);
const context = {
  accounts: [
    {
      account_id: "account-1",
      account_key: "broker",
      institution_name: "Private Broker",
      kind: "brokerage_manual" as const,
      name: "Brokerage",
      portfolio_id: "portfolio-1",
      status: "active" as const,
    },
  ],
  assets: [
    { asset_id: "asset-btc", name: "Bitcoin", status: "active" as const, symbol: "BTC" },
    { asset_id: "asset-usd", name: "US Dollar", status: "active" as const, symbol: "USD" },
  ],
  portfolioId: "portfolio-1",
  portfolioName: "Core portfolio",
};

const checkpoint = {
  cost_basis_method: "fifo",
  holdings_rebuild_id: "rebuild-1",
  journal_sha256: "a".repeat(64),
  journal_transaction_count: 1,
  last_transaction_id: "transaction-1",
  portfolio_id: "portfolio-1",
  projection_version: "holdings-v1",
  rebuilt_at: "2026-11-03T12:00:00Z",
};

function mockWorkspace({
  imports = [],
  reconciliation = [],
}: { imports?: object[]; reconciliation?: object[] } = {}) {
  request
    .mockResolvedValueOnce({
      items: [
        {
          correction_kind: null,
          correction_of_transaction_id: null,
          legs: [
            {
              account_id: "account-1",
              asset_id: "asset-btc",
              external_counterparty: null,
              quantity: "1.25000000",
              sequence: 1,
              transaction_leg_id: "leg-1",
            },
            {
              account_id: null,
              asset_id: "asset-usd",
              external_counterparty: "market",
              quantity: "-10000.00",
              sequence: 2,
              transaction_leg_id: "leg-2",
            },
          ],
          memo: "Opening evidence",
          occurred_at: "2026-11-03T10:00:00Z",
          recorded_at: "2026-11-03T10:01:00Z",
          source_kind: "manual",
          source_reference: "owner-entry",
          transaction_id: "transaction-1",
          transaction_kind: "buy",
        },
      ],
    })
    .mockResolvedValueOnce({
      checkpoint,
      items: [
        {
          account_id: "account-1",
          asset_id: "asset-btc",
          average_unit_cost: "8000.00",
          basis_status: "known",
          cost_basis_asset_id: "asset-usd",
          quantity: "1.25000000",
          total_cost_basis: "10000.00",
        },
      ],
    })
    .mockResolvedValueOnce({
      checkpoint,
      items: [
        {
          account_id: "account-1",
          acquired_at: "2026-11-03T10:00:00Z",
          acquisition_transaction_id: "transaction-1",
          asset_id: "asset-btc",
          basis_status: "known",
          cost_basis_asset_id: "asset-usd",
          lot_key: "lot-1",
          original_cost_basis: "10000.00",
          original_quantity: "1.25000000",
          remaining_cost_basis: "10000.00",
          remaining_quantity: "1.25000000",
        },
      ],
    })
    .mockResolvedValueOnce({ items: imports })
    .mockResolvedValueOnce({ items: reconciliation });
}

describe("PortfolioOperations", () => {
  beforeEach(() => request.mockReset());

  it("renders immutable journal evidence and exact decimal legs", async () => {
    mockWorkspace();
    render(
      <PortfolioOperations context={context} dictionary={en} locale="en" recentlyReauthenticated />,
    );

    expect(await screen.findByText("Opening evidence")).toBeInTheDocument();
    expect(screen.getByText("1.25000000 BTC")).toBeInTheDocument();
    expect(screen.getByText("-10000.00 USD")).toBeInTheDocument();
    expect(request).toHaveBeenCalledWith("/api/v1/transactions?portfolio_id=portfolio-1", {
      signal: expect.any(AbortSignal),
    });
  });

  it("shows checkpoint-bound holdings and lots", async () => {
    mockWorkspace();
    render(
      <PortfolioOperations context={context} dictionary={en} locale="en" recentlyReauthenticated />,
    );
    await screen.findByText("Opening evidence");
    fireEvent.click(screen.getByRole("tab", { name: "Holdings & lots" }));

    expect(screen.getByText("holdings-v1")).toBeInTheDocument();
    expect(screen.getAllByText("Bitcoin")).toHaveLength(2);
    expect(screen.getAllByText("Known basis")).toHaveLength(2);
  });

  it("creates a mandatory dry-run preview through the CSRF-aware client", async () => {
    mockWorkspace();
    render(
      <PortfolioOperations context={context} dictionary={en} locale="en" recentlyReauthenticated />,
    );
    await screen.findByText("Opening evidence");
    fireEvent.click(screen.getByRole("tab", { name: "Import preview" }));
    fireEvent.change(screen.getByLabelText("Import content"), {
      target: { value: "external_row_id,portfolio_key\nrow-1,core" },
    });
    request.mockResolvedValueOnce({
      content_sha256: "b".repeat(64),
      created_at: "2026-11-03T12:00:00Z",
      duplicate_count: 0,
      import_batch_id: "batch-1",
      published_at: null,
      quarantined_count: 0,
      ready_count: 1,
      review_reason: null,
      reviewed_at: null,
      row_count: 1,
      rows: [],
      source_format: "csv",
      status: "dry_run",
    });
    fireEvent.click(screen.getByRole("button", { name: "Create dry-run preview" }));

    await waitFor(() =>
      expect(request).toHaveBeenLastCalledWith("/api/v1/imports/dry-runs", {
        body: {
          content: "external_row_id,portfolio_key\nrow-1,core",
          source_format: "csv",
        },
        method: "POST",
      }),
    );
    expect(await screen.findByText("Dry run")).toBeInTheDocument();
  });

  it("blocks publication until the owner recently reauthenticates", async () => {
    mockWorkspace({
      imports: [
        {
          content_sha256: "c".repeat(64),
          created_at: "2026-11-03T12:00:00Z",
          duplicate_count: 0,
          import_batch_id: "batch-reviewed",
          published_at: null,
          quarantined_count: 0,
          ready_count: 1,
          review_reason: "Owner checked every normalized row",
          reviewed_at: "2026-11-03T12:05:00Z",
          row_count: 1,
          rows: [],
          source_format: "csv",
          status: "reviewed",
        },
      ],
    });
    render(
      <PortfolioOperations
        context={context}
        dictionary={en}
        locale="en"
        recentlyReauthenticated={false}
      />,
    );
    await screen.findByText("Opening evidence");
    fireEvent.click(screen.getByRole("tab", { name: "Import preview" }));

    expect(screen.getByRole("button", { name: "Publish atomically" })).toBeDisabled();
    expect(screen.getByText(/Recent passkey authentication is required/)).toBeInTheDocument();
  });

  it("records a version-checked reconciliation decision with an owner reason", async () => {
    const reconciliationCase = {
      created_at: "2026-11-04T08:00:00Z",
      difference_code: "QUANTITY_MISMATCH",
      import_batch_id: "batch-1",
      import_row_id: "row-1",
      reason: null,
      reconciliation_case_id: "case-1",
      row_version: 3,
      state: "open",
      transaction_id: null,
      updated_at: "2026-11-04T08:00:00Z",
    };
    mockWorkspace({ reconciliation: [reconciliationCase] });
    render(
      <PortfolioOperations context={context} dictionary={en} locale="en" recentlyReauthenticated />,
    );
    await screen.findByText("Opening evidence");
    fireEvent.click(screen.getByRole("tab", { name: "Reconciliation" }));
    fireEvent.change(screen.getByLabelText("Owner reason"), {
      target: { value: "Matched against the owner statement" },
    });
    request.mockResolvedValueOnce({
      ...reconciliationCase,
      reason: "Matched against the owner statement",
      row_version: 4,
      state: "matched",
    });
    fireEvent.click(screen.getByRole("button", { name: "Record decision" }));

    await waitFor(() =>
      expect(request).toHaveBeenLastCalledWith("/api/v1/reconciliation-cases/case-1/decisions", {
        body: {
          expected_row_version: 3,
          reason: "Matched against the owner statement",
          state: "matched",
        },
        method: "POST",
      }),
    );
  });
});
