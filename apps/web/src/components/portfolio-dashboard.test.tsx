import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import en from "../../messages/en.json";
import { apiRequest } from "@/lib/api-client";
import { formatExactDecimal } from "@/lib/portfolio-analytics";
import { PortfolioDashboard } from "./portfolio-dashboard";

vi.mock("@/lib/api-client", () => ({ apiRequest: vi.fn() }));

const request = vi.mocked(apiRequest);

const portfolio = {
  base_asset_id: "asset-usd",
  kind: "personal",
  name: "Core portfolio",
  portfolio_id: "portfolio-1",
  portfolio_key: "core-portfolio",
  status: "active",
};
const snapshotTime = "2026-11-03T12:00:00Z";
const account = {
  account_id: "account-1",
  account_key: "private-broker",
  institution_name: "Private Broker",
  kind: "brokerage_manual",
  name: "Brokerage",
  portfolio_id: "portfolio-1",
  status: "active",
};
const assets = [
  { asset_id: "asset-usd", name: "US Dollar", status: "active", symbol: "USD" },
  { asset_id: "asset-btc", name: "Bitcoin", status: "active", symbol: "BTC" },
  { asset_id: "asset-eth", name: "Ether", status: "active", symbol: "ETH" },
];
const position = {
  account_id: account.account_id,
  evidence_at: snapshotTime,
  basis_status: "known",
  asset_id: "asset-btc",
  quantity: "0.00012345",
  market_value: "9000.00",
  state: "fresh",
};

describe("PortfolioDashboard", () => {
  beforeEach(() => request.mockReset());

  it("renders exact analytics, valuation health, allocation and owner accounts", async () => {
    request
      .mockResolvedValueOnce({ items: [portfolio] })
      .mockResolvedValueOnce({ items: [account] })
      .mockResolvedValueOnce({ items: assets })
      .mockResolvedValueOnce({
        as_of: snapshotTime,
        nav: "12345.675",
        positions: [
          position,
          { ...position, asset_id: "asset-eth", market_value: "3000", state: "stale" },
        ],
        priced_value: "12000",
        realized_pnl: "125.5",
        state: "stale",
        unrealized_pnl: "-42.125",
      })
      .mockResolvedValueOnce({
        as_of: snapshotTime,
        items: [
          { asset_id: "asset-btc", state: "fresh" },
          { asset_id: "asset-eth", state: "stale" },
          { asset_id: "asset-xau", state: "missing" },
        ],
      })
      .mockResolvedValueOnce({ points: [] });

    render(<PortfolioDashboard dictionary={en} locale="en" />);

    expect(await screen.findByText("12,345.68")).toBeInTheDocument();
    expect(screen.getByText("−42.13")).toBeInTheDocument();
    fireEvent.click(screen.getByText("Show allocation data"));
    const allocation = screen.getByRole("table", { name: "Allocation" });
    expect(allocation).toHaveTextContent("75.0%");
    expect(allocation).toHaveTextContent("25.0%");
    const holdings = screen.getByRole("table", { name: "Holdings" });
    expect(holdings).toHaveTextContent("0.00012345");
    expect(screen.getByRole("heading", { name: "Account registry" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Brokerage" })).toBeInTheDocument();
    expect(screen.getByText(/report includes stale valuation evidence/)).toBeInTheDocument();
  });

  it("keeps partial valuation and holdings visible if the valuation report cannot load", async () => {
    request
      .mockResolvedValueOnce({ items: [portfolio] })
      .mockResolvedValueOnce({ items: [account] })
      .mockResolvedValueOnce({ items: assets })
      .mockResolvedValueOnce({
        as_of: snapshotTime,
        nav: null,
        positions: [position],
        priced_value: "9000",
        realized_pnl: null,
        state: "missing",
        unrealized_pnl: null,
      })
      .mockRejectedValueOnce(new Error("valuation service unavailable"))
      .mockResolvedValueOnce({ points: [] });

    render(<PortfolioDashboard dictionary={en} locale="en" />);

    expect(await screen.findByRole("table", { name: "Holdings" })).toHaveTextContent("Bitcoin");
    expect(screen.getByText(/Value of holdings with a price/)).toHaveTextContent("9,000.00");
    expect(screen.getByText(/valuation report could not be loaded/)).toBeVisible();
  });

  it("renders a bounded empty state when no portfolio exists", async () => {
    request
      .mockResolvedValueOnce({ items: [] })
      .mockResolvedValueOnce({ items: [] })
      .mockResolvedValueOnce({ items: [] });

    render(<PortfolioDashboard dictionary={en} locale="en" />);
    expect(
      await screen.findByRole("heading", { name: "No portfolio is registered yet" }),
    ).toBeInTheDocument();
  });

  it("formats canonical decimals without binary floating point", () => {
    expect(formatExactDecimal("999999999999999999999999.995", "en")).toBe(
      "1,000,000,000,000,000,000,000,000.00",
    );
    expect(formatExactDecimal("-1234.5", "fa")).toBe("−۱٬۲۳۴٫۵۰");
  });
});
