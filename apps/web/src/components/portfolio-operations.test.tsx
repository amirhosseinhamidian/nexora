import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import en from "../../messages/en.json";
import { ApiRequestError, apiRequest } from "@/lib/api-client";
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

const batch = {
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
};
const reconciliationCase = {
  created_at: "2026-11-04T08:00:00Z",
  difference_code: "ROW_VALIDATION_FAILED",
  import_batch_id: "batch-1",
  import_row_id: "row-1",
  reason: null,
  reconciliation_case_id: "case-1",
  row_version: 3,
  state: "open",
  transaction_id: null,
  updated_at: "2026-11-04T08:00:00Z",
};
const props = {
  basis: "fifo" as const,
  dictionary: en,
  locale: "en" as const,
  onBasisChange: vi.fn(),
  recentlyReauthenticated: true,
};

describe("PortfolioOperations", () => {
  beforeEach(() => request.mockReset());

  it("reads only the selected portfolio's journal and displays its exact entry lines", async () => {
    request.mockResolvedValueOnce({
      items: [
        {
          correction_kind: "reversal",
          correction_of_transaction_id: "original-transaction",
          legs: [
            {
              account_id: "account-1",
              asset_id: "asset-btc",
              external_counterparty: null,
              quantity: "-1.25000000",
              sequence: 1,
              transaction_leg_id: "leg-1",
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
    });
    render(<PortfolioOperations {...props} context={context} view="journal" />);

    expect(await screen.findByText("Opening evidence")).toBeInTheDocument();
    expect(screen.getByText("-1.25000000 BTC")).toBeInTheDocument();
    expect(screen.getByText("original-transaction")).toBeInTheDocument();
    expect(request).toHaveBeenCalledExactlyOnceWith(
      "/api/v1/transactions?portfolio_id=portfolio-1",
      {
        signal: expect.any(AbortSignal),
      },
    );
  });

  it.each([
    { view: "holdings" as const, empty: "This calculation has no holdings." },
    { view: "lots" as const, empty: "This calculation has no open purchase lots." },
  ])("loads the $view calculation for the requested method", async ({ view, empty }) => {
    request.mockResolvedValueOnce({ checkpoint, items: [] });
    render(
      <PortfolioOperations {...props} basis="weighted_average" context={context} view={view} />,
    );

    expect(await screen.findByText("holdings-v1")).toBeInTheDocument();
    expect(screen.getByText(empty)).toBeInTheDocument();
    expect(request).toHaveBeenCalledExactlyOnceWith(
      `/api/v1/portfolios/portfolio-1/${view}?cost_basis_method=weighted_average`,
      { signal: expect.any(AbortSignal) },
    );
  });

  it("asks for confirmation before rebuilding a missing calculation", async () => {
    request.mockRejectedValueOnce(new ApiRequestError(404, "NOT_FOUND"));
    render(<PortfolioOperations {...props} context={context} view="holdings" />);
    const rebuild = await screen.findByRole("button", { name: "Rebuild from journal" });
    fireEvent.click(rebuild);
    const dialog = screen.getByRole("dialog", { name: "Rebuild accounting calculations?" });
    expect(request).toHaveBeenCalledTimes(1);

    request.mockResolvedValueOnce(checkpoint).mockResolvedValueOnce({ checkpoint, items: [] });
    fireEvent.click(within(dialog).getByRole("button", { name: "Rebuild from journal" }));

    expect(await screen.findByText("holdings-v1")).toBeInTheDocument();
    expect(request).toHaveBeenNthCalledWith(2, "/api/v1/portfolios/portfolio-1/holdings/rebuilds", {
      body: { cost_basis_method: "fifo" },
      method: "POST",
      signal: expect.any(AbortSignal),
    });
  });

  it("creates a preview only after submission and refreshes the owner's imports", async () => {
    const content = "external_row_id,portfolio_key\nrow-1,core";
    request.mockResolvedValueOnce({ items: [] });
    render(<PortfolioOperations {...props} view="imports" />);
    fireEvent.change(await screen.findByLabelText("Import content"), {
      target: { value: content },
    });
    expect(request).toHaveBeenCalledTimes(1);

    request.mockResolvedValueOnce(batch).mockResolvedValueOnce({ items: [batch] });
    fireEvent.click(screen.getByRole("button", { name: "Create preview" }));

    expect(await screen.findByText("Preview")).toBeInTheDocument();
    expect(request).toHaveBeenNthCalledWith(2, "/api/v1/imports/dry-runs", {
      body: { content, source_format: "csv" },
      method: "POST",
      signal: expect.any(AbortSignal),
    });
    expect(request).toHaveBeenLastCalledWith("/api/v1/imports", {
      signal: expect.any(AbortSignal),
    });
  });

  it("requires a fresh passkey and a separate confirmation to publish a reviewed import", async () => {
    const reviewed = { ...batch, status: "reviewed", review_reason: "Checked the ready rows" };
    const onReauthenticate = vi.fn().mockResolvedValue(undefined);
    request.mockResolvedValueOnce({ items: [reviewed] });
    const { rerender } = render(
      <PortfolioOperations
        {...props}
        onReauthenticate={onReauthenticate}
        recentlyReauthenticated={false}
        view="imports"
      />,
    );
    expect(await screen.findByRole("button", { name: "Publish import" })).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "Verify with your passkey" }));
    expect(
      await screen.findByText("Passkey verified. You can now confirm the action."),
    ).toBeInTheDocument();
    expect(onReauthenticate).toHaveBeenCalledExactlyOnceWith(expect.any(AbortSignal));
    expect(request).toHaveBeenCalledTimes(1);

    rerender(<PortfolioOperations {...props} view="imports" />);
    fireEvent.click(screen.getByRole("button", { name: "Publish import" }));
    const dialog = screen.getByRole("dialog", { name: "Publish this import?" });
    expect(within(dialog).getByText("batch-1")).toBeInTheDocument();
    expect(request).toHaveBeenCalledTimes(1);
    const published = { ...reviewed, status: "published" };
    request.mockResolvedValueOnce(published).mockResolvedValueOnce({ items: [published] });
    fireEvent.click(within(dialog).getByRole("button", { name: "Publish import" }));

    expect(await screen.findByText("Published")).toBeInTheDocument();
    expect(request).toHaveBeenNthCalledWith(2, "/api/v1/imports/batch-1/publication", {
      body: {},
      method: "POST",
      signal: expect.any(AbortSignal),
      signalSessionExpiry: false,
    });
  });

  it("rechecks the session after publication loses its recent verification", async () => {
    const onRefreshSession = vi.fn().mockResolvedValue(undefined);
    request
      .mockResolvedValueOnce({ items: [{ ...batch, status: "reviewed" }] })
      .mockRejectedValueOnce(new ApiRequestError(401, "AUTHENTICATION_DENIED"));
    render(<PortfolioOperations {...props} onRefreshSession={onRefreshSession} view="imports" />);
    fireEvent.click(await screen.findByRole("button", { name: "Publish import" }));
    const dialog = screen.getByRole("dialog", { name: "Publish this import?" });
    fireEvent.click(within(dialog).getByRole("button", { name: "Publish import" }));

    expect(
      await screen.findByText(/Recent passkey authentication is required/),
    ).toBeInTheDocument();
    expect(onRefreshSession).toHaveBeenCalledExactlyOnceWith(expect.any(AbortSignal));
    expect(request).toHaveBeenCalledTimes(2);
  });

  it("refreshes a conflicting reconciliation case without replaying a confirmed decision", async () => {
    const reason = "Matched against the owner statement";
    request.mockResolvedValueOnce({ items: [reconciliationCase] });
    render(<PortfolioOperations {...props} view="reconciliation" />);
    fireEvent.change(await screen.findByLabelText("Reason"), { target: { value: reason } });
    fireEvent.click(screen.getByRole("button", { name: "Record decision" }));
    const dialog = screen.getByRole("dialog", { name: "Record this decision?" });
    expect(within(dialog).getByText(reason)).toBeInTheDocument();
    expect(request).toHaveBeenCalledTimes(1);

    request
      .mockRejectedValueOnce(new ApiRequestError(409, "CONFLICT"))
      .mockResolvedValueOnce({ items: [{ ...reconciliationCase, row_version: 4 }] });
    fireEvent.click(within(dialog).getByRole("button", { name: "Record decision" }));

    expect(await screen.findByText(/This record has changed/)).toBeInTheDocument();
    await waitFor(() => expect(request).toHaveBeenCalledTimes(3));
    expect(request).toHaveBeenNthCalledWith(2, "/api/v1/reconciliation-cases/case-1/decisions", {
      body: { expected_row_version: 3, reason, state: "matched" },
      method: "POST",
      signal: expect.any(AbortSignal),
      signalSessionExpiry: false,
    });
    expect(request).toHaveBeenLastCalledWith("/api/v1/reconciliation-cases", {
      signal: expect.any(AbortSignal),
    });
    expect(screen.getByLabelText("Reason")).toHaveValue(reason);
  });
});
