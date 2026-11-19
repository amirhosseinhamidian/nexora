import { fireEvent, render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import en from "../../messages/en.json";
import { ApiRequestError, apiRequest } from "@/lib/api-client";
import { loadDecisionRecord, type DecisionReviewContext } from "@/lib/decision-intelligence";
import { DecisionReviewPanel } from "./decision-review";
import { DecisionFeed } from "./decision-feed";

vi.mock("@/lib/api-client", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api-client")>()),
  apiRequest: vi.fn(),
}));

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

  it("shows owner evidence and links to the Candidate record without extra requests", async () => {
    request.mockResolvedValueOnce({ items: [candidate], next_cursor: null, provider });
    render(<DecisionFeed dictionary={en} locale="en" />);

    expect(await screen.findByRole("heading", { name: "candidate-1" })).toBeInTheDocument();
    expect(screen.getByText("trd-bot-candidate-v1")).toBeInTheDocument();
    expect(screen.getByText(`sha256:${"a".repeat(64)}`)).toBeInTheDocument();
    expect(screen.getByText(/cannot submit an order/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open evidence" })).toHaveAttribute(
      "href",
      "/en/decisions/candidates/candidate-1",
    );
    expect(request).toHaveBeenCalledExactlyOnceWith("/api/v1/decisions?limit=25", {
      signal: expect.any(AbortSignal),
    });
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

  it("publishes the active Decision context for the integrated journal", async () => {
    const onDecisionChange = vi.fn();
    request.mockResolvedValueOnce({
      items: [candidate],
      next_cursor: null,
      provider,
      schema_version: "nexora-decision-feed-v1",
    });

    render(<DecisionFeed dictionary={en} locale="en" onDecisionChange={onDecisionChange} />);

    expect(await screen.findByRole("heading", { name: "candidate-1" })).toBeInTheDocument();
    expect(onDecisionChange).toHaveBeenCalledWith("decision-evaluation-1");
  });
});

describe("routed Decision evidence", () => {
  beforeEach(() => request.mockReset());

  it.each([
    { generation: 3, candidateId: "candidate-1", matches: true },
    { generation: 4, candidateId: "candidate-1", matches: false },
    { generation: 3, candidateId: "another-candidate", matches: false },
  ])(
    "checks candidate and generation before displaying risk evidence ($generation, $candidateId)",
    async ({ generation, candidateId, matches }) => {
      const riskGate = { candidate_id: candidateId };
      request
        .mockResolvedValueOnce({ candidate, provider })
        .mockResolvedValueOnce({ provider: { ...provider, generation }, risk_gate: riskGate });
      const { signal } = new AbortController();
      const record = await loadDecisionRecord(
        { kind: "candidates", resourceId: "candidate-1", panel: "risk" },
        signal,
      );
      expect(record.riskGate).toEqual(matches ? riskGate : null);
      expect(request.mock.calls).toEqual([
        ["/api/v1/candidates/candidate-1", { signal }],
        ["/api/v1/risk-gates/decision-evaluation-1", { signal }],
      ]);
    },
  );

  it("looks up a specific Decision on later owner feed pages", async () => {
    const decision = {
      ...candidate,
      resource_type: "decision_evaluation",
      resource_id: "evaluation-2",
    };
    request
      .mockResolvedValueOnce({ items: [candidate], next_cursor: "next", provider })
      .mockResolvedValueOnce({ items: [decision], next_cursor: null, provider });
    const { signal } = new AbortController();
    const record = await loadDecisionRecord(
      { kind: "records", resourceId: "evaluation-2", panel: "evidence" },
      signal,
    );
    expect(record.item).toEqual(decision);
    expect(request).toHaveBeenLastCalledWith("/api/v1/decisions?limit=100&cursor=next", { signal });
  });
});

describe("routed Decision review", () => {
  const context: DecisionReviewContext = {
    current_version: 0,
    decision_id: "decision-evaluation-1",
    evidence_generation: 3,
    latest_review_id: null,
    local_state: "review_pending",
    provider_delivery_required: true,
    reviewable: true,
    reviews: [],
    schema_version: "nexora-human-decision-review-v1",
    source_evidence_checksum: candidate.source.checksum,
  };

  beforeEach(() => request.mockReset());

  it("retries an uncertain review with the exact confirmed body and key", async () => {
    request
      .mockRejectedValueOnce(new ApiRequestError(503, "UNAVAILABLE"))
      .mockResolvedValueOnce({ decision_id: context.decision_id })
      .mockResolvedValueOnce(context);
    render(
      <DecisionReviewPanel
        context={context}
        decisionId={context.decision_id}
        dictionary={en}
        generation={3}
        locale="en"
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Record immutable review" }));
    expect(request).not.toHaveBeenCalled();

    const confirm = () =>
      fireEvent.click(
        within(screen.getByRole("dialog", { name: "Record this review?" })).getByRole("button", {
          name: "Record immutable review",
        }),
      );
    confirm();
    fireEvent.click(await screen.findByRole("button", { name: "Retry the same review" }));
    confirm();
    expect(await screen.findByText("Review recorded.")).toBeInTheDocument();

    const [initial, retry, refresh] = request.mock.calls;
    expect(initial[1]).toMatchObject({
      method: "POST",
      body: {
        expected_version: 0,
        evidence_generation: 3,
        source_evidence_checksum: candidate.source.checksum,
        supersedes_review_id: null,
      },
      headers: { "Idempotency-Key": expect.stringMatching(/^nexora-review-/) },
    });
    expect(retry).toEqual([initial[0], { ...initial[1], signal: expect.any(AbortSignal) }]);
    expect(refresh).toEqual([initial[0], { signal: expect.any(AbortSignal) }]);
  });

  it("shows review availability without allowing a write against another generation", () => {
    render(
      <DecisionReviewPanel
        context={context}
        decisionId={context.decision_id}
        dictionary={en}
        generation={4}
        locale="en"
      />,
    );
    expect(screen.getByText(en.decisionFeed.reviewUnavailable)).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Record immutable review" }),
    ).not.toBeInTheDocument();
  });
});
