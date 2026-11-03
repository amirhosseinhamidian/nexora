import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import en from "../../messages/en.json";
import { apiRequest } from "@/lib/api-client";
import { formatExactDecimal, PortfolioDashboard } from "./portfolio-dashboard";

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

describe("PortfolioDashboard", () => {
  beforeEach(() => request.mockReset());

  it("renders exact analytics, valuation health, allocation and owner accounts", async () => {
    request
      .mockResolvedValueOnce({ items: [portfolio] })
      .mockResolvedValueOnce({
        items: [
          {
            account_id: "account-1",
            account_key: "private-broker",
            institution_name: "Private Broker",
            kind: "brokerage_manual",
            name: "Brokerage",
            portfolio_id: "portfolio-1",
            status: "active",
          },
        ],
      })
      .mockResolvedValueOnce({
        items: [
          { asset_id: "asset-usd", name: "US Dollar", status: "active", symbol: "USD" },
          { asset_id: "asset-btc", name: "Bitcoin", status: "active", symbol: "BTC" },
          { asset_id: "asset-eth", name: "Ether", status: "active", symbol: "ETH" },
        ],
      })
      .mockResolvedValueOnce({
        as_of: "2026-11-03T12:00:00Z",
        nav: "12345.675",
        positions: [
          { asset_id: "asset-btc", market_value: "9000.00", state: "fresh" },
          { asset_id: "asset-eth", market_value: "3000", state: "stale" },
        ],
        priced_value: "12000",
        realized_pnl: "125.5",
        state: "stale",
        unrealized_pnl: "-42.125",
      })
      .mockResolvedValueOnce({
        as_of: "2026-11-03T12:00:00Z",
        items: [
          { asset_id: "asset-btc", state: "fresh" },
          { asset_id: "asset-eth", state: "stale" },
          { asset_id: "asset-xau", state: "missing" },
        ],
      });

    render(<PortfolioDashboard dictionary={en} locale="en" />);

    expect(await screen.findByText("12,345.68")).toBeInTheDocument();
    expect(screen.getByText("−42.13")).toBeInTheDocument();
    expect(screen.getByText("75.0%")).toBeInTheDocument();
    expect(screen.getByText("25.0%")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Account registry" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Brokerage" })).toBeInTheDocument();
    expect(screen.getByText(/NAV includes stale valuation evidence/)).toBeInTheDocument();
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
