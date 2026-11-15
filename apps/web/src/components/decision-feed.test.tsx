import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import en from "../../messages/en.json";
import { apiRequest } from "@/lib/api-client";
import { DecisionFeed } from "./decision-feed";

vi.mock("@/lib/api-client", () => ({ apiRequest: vi.fn() }));

const request = vi.mocked(apiRequest);

const provider = {
  contract_version: "nexora-trd-integration-v1",
  generation: 3,
  provider_version: "0.3.1",
  reason_code: "ACTIVE_PROJECTION_READY",
  state: "ready",
};

const candidate = {
  decision_kind: "candidate",
  evidence: {
    candidate_id: "candidate-1",
    evaluation_id: "decision-evaluation-1",
    external_order_submission_allowed: false,
    offline_only: true,
  },
  evidence_sha256: "b".repeat(64),
  local_state: "review_pending",
  resource_id: "candidate-1",
  resource_type: "candidate",
  source: {
    aggregate_id: "candidate-1",
    aggregate_type: "candidate",
    aggregate_version: 2,
    checksum: `sha256:${"a".repeat(64)}`,
    event_id: "event-2",
    observed_at: "2026-11-14T10:00:00Z",
    resource_id: "candidate-1",
    resource_schema_version: "trd-bot-candidate-v1",
    resource_type: "candidate",
    schema_version: "nexora-source-reference-v1",
    source_product: "trd_bot",
    source_version: "0.3.1",
  },
};

describe("DecisionFeed", () => {
  beforeEach(() => request.mockReset());

  it("shows owner evidence and fetches Candidate detail through the private API", async () => {
    request
      .mockResolvedValueOnce({
        items: [candidate],
        next_cursor: null,
        provider,
        schema_version: "nexora-decision-feed-v1",
      })
      .mockResolvedValueOnce({
        candidate: { ...candidate, evidence: { ...candidate.evidence, signal: "observe" } },
        provider,
        schema_version: "nexora-decision-feed-v1",
      })
      .mockResolvedValueOnce({
        provider,
        risk_gate: {
          approved_candidate_id: null,
          candidate_id: "candidate-1",
          checks: [
            {
              actual_value: "0.25",
              explanation: "Ranking score must meet the policy floor.",
              limit_value: "0.30",
              name: "ranking_score",
              passed: false,
            },
          ],
          decision: "rejected",
          disposition: "rejected",
          evaluated_at: "2026-11-14T10:00:00Z",
          evidence_sha256: "c".repeat(64),
          external_order_submission_allowed: false,
          offline_only: true,
          policy: { checksum: "d".repeat(64), version: "decision-risk-v1" },
          position_sizing_exposed: false,
          provider_reason_codes: [{ code: "risk_policy_rejected", namespace: "trd_bot" }],
          source: {
            aggregate_id: "decision-evaluation-1",
            aggregate_type: "risk_gate",
            aggregate_version: 1,
            checksum: `sha256:${"e".repeat(64)}`,
            event_id: null,
            observed_at: "2026-11-14T10:00:00Z",
            resource_id: "decision-evaluation-1",
            resource_schema_version: "trd-bot-risk-gate-v1",
            resource_type: "risk_gate",
            schema_version: "nexora-source-reference-v1",
            source_product: "trd_bot",
            source_version: "0.3.1",
          },
          uncertainty: {
            reason_code: "TRD_BOT_RISK_UNCERTAINTY_NOT_SUPPLIED",
            state: "not_supplied",
            value: null,
          },
        },
        schema_version: "nexora-risk-gate-explanation-v1",
      });

    render(<DecisionFeed dictionary={en} locale="en" />);

    expect(await screen.findByRole("heading", { name: "candidate-1" })).toBeInTheDocument();
    expect(screen.getByText("trd-bot-candidate-v1")).toBeInTheDocument();
    expect(screen.getByText(`sha256:${"a".repeat(64)}`)).toBeInTheDocument();
    expect(screen.getByText(/cannot submit an order/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /candidate-1/i }));
    await waitFor(() =>
      expect(request).toHaveBeenLastCalledWith("/api/v1/risk-gates/decision-evaluation-1"),
    );
    expect(await screen.findByText("observe")).toBeInTheDocument();
    expect(screen.getByText("decision-risk-v1")).toBeInTheDocument();
    expect(screen.getByText("risk_policy_rejected")).toBeInTheDocument();
    expect(screen.getByText("Provider did not supply uncertainty")).toBeInTheDocument();
  });

  it("renders an explicit degraded empty state", async () => {
    request.mockResolvedValueOnce({
      items: [],
      next_cursor: null,
      provider: {
        contract_version: null,
        generation: null,
        provider_version: null,
        reason_code: "ACTIVE_PROJECTION_UNAVAILABLE",
        state: "degraded",
      },
      schema_version: "nexora-decision-feed-v1",
    });

    render(<DecisionFeed dictionary={en} locale="en" />);

    expect(await screen.findByText("Provider evidence is degraded")).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "No Decision or Candidate evidence" }),
    ).toBeInTheDocument();
  });
});
