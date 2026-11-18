import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import en from "../../messages/en.json";
import { apiRequest } from "@/lib/api-client";
import { AuthenticatedShell } from "./authenticated-shell";

vi.mock("@/components/foundation-controls", () => ({
  FoundationControls: () => <div>controls</div>,
}));
vi.mock("next/navigation", () => ({ usePathname: () => "/en/overview" }));
vi.mock("@/lib/api-client", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api-client")>("@/lib/api-client");
  return { ...actual, apiRequest: vi.fn() };
});

const request = vi.mocked(apiRequest);

describe("AuthenticatedShell", () => {
  beforeEach(() => {
    request.mockReset();
    vi.stubGlobal("matchMedia", () => ({
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    }));
  });
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("renders the owner shell and logs out through the CSRF-aware client", async () => {
    request
      .mockResolvedValueOnce({
        owner_id: "113f777b-f75b-46e5-91da-91d9601c03ea",
        recently_reauthenticated: true,
        rotation_required: false,
      })
      .mockResolvedValueOnce({ status: "ready" })
      .mockResolvedValueOnce({ status: "completed" });

    render(
      <AuthenticatedShell dictionary={en} locale="en">
        <h1>Private page</h1>
      </AuthenticatedShell>,
    );
    expect(screen.queryByRole("heading", { name: "Private page" })).not.toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "Private page" })).toBeInTheDocument();
    expect(screen.getByText("113f777b…")).toBeInTheDocument();
    expect(await screen.findByTitle("Ready")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Overview" })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("link", { name: "Transactions" })).toHaveAttribute(
      "href",
      "/en/transactions",
    );

    fireEvent.click(screen.getByRole("button", { name: "Sign out" }));
    await waitFor(() =>
      expect(request).toHaveBeenLastCalledWith("/api/v1/auth/logout", { body: {}, method: "POST" }),
    );
    expect(await screen.findByRole("heading", { name: "Session expired" })).toBeInTheDocument();
  });
});
