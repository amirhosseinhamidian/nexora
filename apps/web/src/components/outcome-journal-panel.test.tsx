import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import en from "../../messages/en.json";
import { apiRequest } from "@/lib/api-client";
import { OutcomeJournalPanel } from "./outcome-journal-panel";

vi.mock("@/lib/api-client", () => ({ apiRequest: vi.fn() }));

const request = vi.mocked(apiRequest);
const occurredAtInput = "2026-11-17T10:00";
const occurredAt = new Date(occurredAtInput).toISOString();
const entry = {
  ai_generated: false,
  append_only: true,
  author_kind: "owner",
  content: "Observe without changing the evidence.",
  decision_evidence_checksum: `sha256:${"a".repeat(64)}`,
  decision_evidence_generation: 3,
  decision_id: "decision-1",
  entry_id: "871b8a59-d278-4bce-a034-80b52f45ee03",
  entry_kind: "owner_note",
  occurred_at: occurredAt,
  portfolio_id: null,
  provider_rewritable: false,
  recorded_at: "2026-11-17T10:01:00Z",
  review_id: null,
  simulated_position_reference: null,
  source_lineage: null,
  supersedes_entry_id: null,
  uncertainty_level: "unknown",
  uncertainty_note: null,
};

describe("OutcomeJournalPanel", () => {
  beforeEach(() => {
    request.mockReset();
    vi.stubGlobal("crypto", {
      randomUUID: vi.fn().mockReturnValueOnce("journal-key-1").mockReturnValueOnce("journal-key-2"),
    });
  });

  it("loads an explicit empty Decision journal", async () => {
    request.mockResolvedValueOnce({
      decision_id: "decision-1",
      items: [],
      schema_version: "nexora-outcome-journal-v1",
    });

    render(<OutcomeJournalPanel dictionary={en} locale="en" />);

    expect(
      screen.getByText("Enter a Decision ID to inspect its immutable journal."),
    ).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Decision ID"), { target: { value: "decision-1" } });
    fireEvent.click(screen.getByRole("button", { name: "Load journal" }));

    expect(
      await screen.findByRole("heading", { name: "No journal entry yet" }),
    ).toBeInTheDocument();
    expect(request).toHaveBeenCalledWith("/api/v1/decisions/decision-1/journal?limit=50");
  });

  it("keeps the same idempotency key when an unchanged append is retried", async () => {
    request
      .mockResolvedValueOnce({
        decision_id: "decision-1",
        items: [],
        schema_version: "nexora-outcome-journal-v1",
      })
      .mockRejectedValueOnce(new Error("connection interrupted"))
      .mockResolvedValueOnce(entry);

    render(<OutcomeJournalPanel dictionary={en} locale="en" />);
    fireEvent.change(screen.getByLabelText("Decision ID"), { target: { value: "decision-1" } });
    fireEvent.click(screen.getByRole("button", { name: "Load journal" }));
    expect(
      await screen.findByRole("heading", { name: "No journal entry yet" }),
    ).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Occurred at"), { target: { value: occurredAtInput } });
    fireEvent.change(screen.getByLabelText("Owner-authored content"), {
      target: { value: "Observe without changing the evidence." },
    });
    fireEvent.click(screen.getByRole("button", { name: "Append entry" }));
    expect(await screen.findByText(/Retry keeps the same idempotency key/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Append entry" }));
    await waitFor(() => expect(request).toHaveBeenCalledTimes(3));
    const expectedOptions = {
      body: {
        content: "Observe without changing the evidence.",
        entry_kind: "owner_note",
        occurred_at: occurredAt,
        portfolio_id: null,
        review_id: null,
        simulated_position_reference: null,
        source_lineage: null,
        supersedes_entry_id: null,
        uncertainty_level: "unknown",
        uncertainty_note: null,
      },
      headers: { "Idempotency-Key": "nexora-outcome-journal-journal-key-1" },
      method: "POST",
    };
    expect(request).toHaveBeenNthCalledWith(
      2,
      "/api/v1/decisions/decision-1/journal",
      expectedOptions,
    );
    expect(request).toHaveBeenNthCalledWith(
      3,
      "/api/v1/decisions/decision-1/journal",
      expectedOptions,
    );
  });

  it("loads the Decision selected by the integrated evidence workflow", async () => {
    request.mockResolvedValueOnce({
      decision_id: "decision-1",
      items: [],
      schema_version: "nexora-outcome-journal-v1",
    });

    render(<OutcomeJournalPanel decisionId="decision-1" dictionary={en} locale="en" />);

    expect(
      await screen.findByRole("heading", { name: "No journal entry yet" }),
    ).toBeInTheDocument();
    expect(screen.getByLabelText("Decision ID")).toHaveValue("decision-1");
    expect(request).toHaveBeenCalledWith("/api/v1/decisions/decision-1/journal?limit=50");
  });
});
