import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import en from "../../messages/en.json";
import { apiRequest } from "@/lib/api-client";
import { AlertInbox } from "./alert-inbox";

vi.mock("@/lib/api-client", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api-client")>()),
  apiRequest: vi.fn(),
}));

const request = vi.mocked(apiRequest);
const checksum = `sha256:${"a".repeat(64)}`;
const provider = {
  contract_version: "nexora-trd-integration-v1",
  generation: 4,
  provider_version: "0.3.1",
  reason_code: "ACTIVE_PROJECTION_READY",
  state: "ready",
};
const alert = {
  alert_id: "alert-1",
  current_version: 0,
  evidence: { message: "Candidate needs attention", severity: "warning", state: "open" },
  evidence_sha256: "b".repeat(64),
  history: [],
  local_state: "open",
  snooze_until: null,
  source: {
    aggregate_id: "alert-1",
    aggregate_type: "alert",
    aggregate_version: 1,
    checksum,
    event_id: "event-1",
    observed_at: "2026-11-17T10:00:00Z",
    resource_id: "alert-1",
    resource_schema_version: "trd-bot-alert-v1",
    resource_type: "alert",
    schema_version: "nexora-source-reference-v1",
    source_product: "trd_bot",
    source_version: "0.3.1",
  },
};

describe("AlertInbox", () => {
  beforeEach(() => {
    request.mockReset();
    vi.stubGlobal("crypto", { randomUUID: vi.fn(() => "fixture-idempotency-key") });
  });

  it("renders source lineage and records an acknowledgement", async () => {
    request
      .mockResolvedValueOnce({
        items: [alert],
        notification_delivery_enabled: false,
        provider,
        schema_version: "nexora-alert-inbox-v1",
      })
      .mockResolvedValueOnce({
        alert_history_id: "87f4b04c-3ed1-4a52-abaa-6b606c16ad72",
        evidence_generation: 4,
        occurred_at: "2026-11-17T10:05:00Z",
        reason_code: "owner.alert.acknowledged",
        recorded_at: "2026-11-17T10:05:01Z",
        snooze_until: null,
        source_evidence_checksum: checksum,
        state: "acknowledged",
        state_version: 1,
      })
      .mockResolvedValueOnce({
        items: [{ ...alert, current_version: 1, local_state: "acknowledged" }],
        notification_delivery_enabled: false,
        provider,
        schema_version: "nexora-alert-inbox-v1",
      });

    render(<AlertInbox dictionary={en} locale="en" />);

    expect(await screen.findByRole("heading", { name: "alert-1" })).toBeInTheDocument();
    expect(screen.getByText("trd-bot-alert-v1")).toBeInTheDocument();
    expect(screen.getByText(checksum)).toBeInTheDocument();
    expect(screen.getByText(/Notification delivery is deferred/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Acknowledge" }));
    expect(request).toHaveBeenCalledTimes(1);
    const dialog = screen.getByRole("dialog", { name: "Acknowledge this alert?" });
    fireEvent.click(within(dialog).getByRole("button", { name: "Acknowledge" }));
    await waitFor(() =>
      expect(request).toHaveBeenCalledWith(
        "/api/v1/alerts/alert-1/state-transitions",
        expect.objectContaining({
          headers: { "Idempotency-Key": "nexora-alert-fixture-idempotency-key" },
          method: "POST",
        }),
      ),
    );
    expect(await screen.findByText("Acknowledged")).toBeInTheDocument();
  });

  it("renders explicit degraded and empty states", async () => {
    request.mockResolvedValueOnce({
      items: [],
      notification_delivery_enabled: false,
      provider: {
        contract_version: null,
        generation: null,
        provider_version: null,
        reason_code: "ACTIVE_PROJECTION_UNAVAILABLE",
        state: "degraded",
      },
      schema_version: "nexora-alert-inbox-v1",
    });

    render(<AlertInbox dictionary={en} locale="en" />);

    expect(await screen.findByText("Provider alert evidence is degraded")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "No active alerts" })).toBeInTheDocument();
  });

  it("keeps an invalid snooze local and omits ambiguous Decision links", async () => {
    request.mockResolvedValueOnce({
      items: [{ ...alert, evidence: { evaluation_id: "decision-1", decision_id: "decision-2" } }],
      provider,
    });
    render(<AlertInbox alertId="alert-1" dictionary={en} locale="en" />);
    const input = await screen.findByLabelText("Resume alert at");
    fireEvent.change(input, { target: { value: "" } });
    fireEvent.click(screen.getByRole("button", { name: "Snooze" }));
    expect(
      screen.getByText("Choose a time in the future to resume this alert."),
    ).toBeInTheDocument();
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Open outcome journal" })).not.toBeInTheDocument();
    expect(request).toHaveBeenCalledTimes(1);
  });
});
