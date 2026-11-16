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
          approved_candidate_id: "candidate-1",
          candidate_id: "candidate-1",
          checks: [
            {
              actual_value: "0.25",
              explanation: "Ranking score must meet the policy floor.",
              limit_value: "0.30",
              name: "ranking_score",
              passed: true,
            },
          ],
          decision: "approved",
          disposition: "accepted",
          evaluated_at: "2026-11-14T10:00:00Z",
          evidence_sha256: "c".repeat(64),
          external_order_submission_allowed: false,
          offline_only: true,
          policy: { checksum: "d".repeat(64), version: "decision-risk-v1" },
          position_sizing_exposed: false,
          provider_reason_codes: [],
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
      })
      .mockResolvedValueOnce({
        portfolio_impact: {
          analysis: {
            candidate_id: "candidate-1",
            checks: [
              {
                actual_value: "unavailable",
                explanation: "Unavailable correlation fails closed.",
                limit_value: "0.850000",
                name: "candidate_correlation",
                passed: false,
              },
            ],
            correlation: {
              evidence: "Pinned data cannot estimate cross-asset correlation.",
              maximum_absolute_correlation: null,
              status: "unavailable",
            },
            exposure: {
              candidate_notional: "1000.00000000",
              current_exposure_fraction: "0.000000",
              current_gross_notional: "0.00000000",
              projected_asset_concentration_fraction: "0.100000",
              projected_exposure_fraction: "0.100000",
              projected_gross_notional: "1000.00000000",
            },
            recommendation: "reject",
            scenarios: [
              {
                candidate_pnl: "-100.00000000",
                existing_pnl: "0.00000000",
                loss_fraction: "0.010000",
                projected_equity: "9900.00000000",
                shock_fraction: "-0.100000",
              },
            ],
            snapshot: {
              as_of: "2026-11-14T10:00:00Z",
              mode: "paper",
              open_positions: [],
              source: "empty_baseline",
            },
          },
          analyzed_at: "2026-11-14T10:00:00Z",
          candidate_id: "candidate-1",
          disposition: "rejected",
          evidence_sha256: "f".repeat(64),
          external_order_submission_allowed: false,
          order_intent_created: false,
          policy: { checksum: "9".repeat(64), version: "decision-portfolio-v1" },
          provider_reason_codes: [{ code: "portfolio_policy_rejected", namespace: "trd_bot" }],
          recommendation: "reject",
          risk_gate_checksum_cross_validated: true,
          snapshot_id: "snapshot-1",
          transaction_created: false,
          uncertainty: {
            reason_code: "TRD_BOT_PORTFOLIO_UNCERTAINTY_NOT_SUPPLIED",
            state: "not_supplied",
            value: null,
          },
        },
        provider,
        schema_version: "nexora-portfolio-candidate-impact-v1",
      })
      .mockResolvedValueOnce({
        current_version: 0,
        decision_id: "decision-evaluation-1",
        evidence_generation: 3,
        latest_review_id: null,
        local_state: "review_pending",
        provider_delivery_required: true,
        reviewable: true,
        reviews: [],
        schema_version: "nexora-human-decision-review-v1",
        source_evidence_checksum: `sha256:${"a".repeat(64)}`,
      });

    render(<DecisionFeed dictionary={en} locale="en" />);

    expect(await screen.findByRole("heading", { name: "candidate-1" })).toBeInTheDocument();
    expect(screen.getByText("trd-bot-candidate-v1")).toBeInTheDocument();
    expect(screen.getByText(`sha256:${"a".repeat(64)}`)).toBeInTheDocument();
    expect(screen.getByText(/cannot submit an order/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /candidate-1/i }));
    await waitFor(() => {
      expect(request).toHaveBeenCalledWith("/api/v1/risk-gates/decision-evaluation-1");
      expect(request).toHaveBeenCalledWith("/api/v1/portfolio-impacts/decision-evaluation-1");
      expect(request).toHaveBeenCalledWith("/api/v1/decisions/decision-evaluation-1/reviews");
    });
    expect(await screen.findByText("observe")).toBeInTheDocument();
    expect(screen.getByText("decision-risk-v1")).toBeInTheDocument();
    expect(screen.getByText("decision-portfolio-v1")).toBeInTheDocument();
    expect(screen.getByText("portfolio_policy_rejected")).toBeInTheDocument();
    expect(screen.getByText("Bounded what-if scenarios")).toBeInTheDocument();
    expect(screen.getAllByText("Provider did not supply uncertainty")).toHaveLength(2);
    expect(screen.getByRole("heading", { name: "Accept, reject or defer" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Record immutable review" })).toBeEnabled();
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
