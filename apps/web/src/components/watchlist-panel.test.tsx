import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import en from "../../messages/en.json";
import { apiRequest } from "@/lib/api-client";
import { WatchlistPanel } from "./watchlist-panel";

vi.mock("@/lib/api-client", () => ({ apiRequest: vi.fn() }));

const request = vi.mocked(apiRequest);
const watchlist = {
  created_at: "2026-11-17T12:00:00Z",
  creates_trade_instruction: false,
  items: [],
  name: "Decision candidates",
  preferences: {
    include_resolved: false,
    minimum_severity: "info",
    notification_delivery_enabled: false,
    presentation_order: "newest_first",
    provider_subscription_management_enabled: false,
    updated_at: "2026-11-17T12:00:00Z",
  },
  row_version: 0,
  updated_at: "2026-11-17T12:00:00Z",
  watchlist_id: "d4d13930-24e5-44a2-93ef-16a603074c13",
};

describe("WatchlistPanel", () => {
  beforeEach(() => {
    request.mockReset();
    vi.stubGlobal("crypto", {
      randomUUID: vi.fn().mockReturnValueOnce("fixture-key-1").mockReturnValueOnce("fixture-key-2"),
    });
  });

  it("creates an owner watchlist with a stable idempotency key", async () => {
    request
      .mockResolvedValueOnce({ items: [], schema_version: "nexora-watchlists-v1" })
      .mockResolvedValueOnce(watchlist);

    render(<WatchlistPanel dictionary={en} locale="en" />);

    expect(await screen.findByRole("heading", { name: "No watchlist yet" })).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Watchlist name"), {
      target: { value: "Decision candidates" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create watchlist" }));

    await waitFor(() =>
      expect(request).toHaveBeenCalledWith("/api/v1/watchlists", {
        body: { name: "Decision candidates" },
        headers: { "Idempotency-Key": "nexora-watchlist-fixture-key-1" },
        method: "POST",
      }),
    );
    expect(await screen.findByRole("option", { name: "Decision candidates" })).toBeInTheDocument();
    expect(screen.getByText(/cannot create trade instructions/)).toBeInTheDocument();
  });

  it("renders an explicit loading failure without changing preferences", async () => {
    request.mockRejectedValueOnce(new Error("offline"));

    render(<WatchlistPanel dictionary={en} locale="en" />);

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Watchlists could not be loaded. No preference was changed.",
    );
    expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument();
  });

  it("reuses the failed mutation key when the owner retries unchanged input", async () => {
    request
      .mockResolvedValueOnce({ items: [], schema_version: "nexora-watchlists-v1" })
      .mockRejectedValueOnce(new Error("connection interrupted"))
      .mockResolvedValueOnce(watchlist);

    render(<WatchlistPanel dictionary={en} locale="en" />);

    expect(await screen.findByRole("heading", { name: "No watchlist yet" })).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Watchlist name"), {
      target: { value: "Decision candidates" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create watchlist" }));
    expect(await screen.findByText(/Retry keeps the same idempotency key/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Create watchlist" }));

    await waitFor(() => expect(request).toHaveBeenCalledTimes(3));
    expect(request).toHaveBeenNthCalledWith(2, "/api/v1/watchlists", {
      body: { name: "Decision candidates" },
      headers: { "Idempotency-Key": "nexora-watchlist-fixture-key-1" },
      method: "POST",
    });
    expect(request).toHaveBeenNthCalledWith(3, "/api/v1/watchlists", {
      body: { name: "Decision candidates" },
      headers: { "Idempotency-Key": "nexora-watchlist-fixture-key-1" },
      method: "POST",
    });
  });
});
