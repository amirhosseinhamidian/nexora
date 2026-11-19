import type { Locale } from "@/i18n/config";
import { ApiRequestError, apiRequest } from "@/lib/api-client";

export type ProviderStatus = {
  contract_version: string | null;
  generation: number | null;
  provider_version: string | null;
  reason_code: string;
  state: "degraded" | "disabled_incompatible" | "ready";
};

type SourceReference = {
  aggregate_id: string | null;
  aggregate_type: string | null;
  aggregate_version: number | null;
  checksum: string;
  event_id: string | null;
  observed_at: string;
  resource_id: string;
  resource_schema_version: string;
  resource_type: "candidate" | "decision_evaluation";
  schema_version: "nexora-source-reference-v1";
  source_product: "trd_bot";
  source_version: string;
};

export type DecisionFeedItem = {
  decision_kind: "candidate" | "portfolio_assessment";
  evidence: Record<string, unknown>;
  evidence_sha256: string;
  local_state: "accepted" | "deferred" | "rejected" | "review_pending";
  resource_id: string;
  resource_type: "candidate" | "decision_evaluation";
  source: SourceReference;
};

export type DecisionFeedPage = {
  items: DecisionFeedItem[];
  next_cursor: string | null;
  provider: ProviderStatus;
  schema_version: "nexora-decision-feed-v1";
};

type CandidateDetail = {
  candidate: DecisionFeedItem | null;
  provider: ProviderStatus;
  schema_version: "nexora-decision-feed-v1";
};

export type DecisionPolicyCheck = {
  actual_value: string;
  explanation: string;
  limit_value: string;
  name: string;
  passed: boolean;
};

export type RiskGateExplanation = {
  approved_candidate_id: string | null;
  candidate_id: string;
  checks: DecisionPolicyCheck[];
  decision: "approved" | "rejected";
  disposition: "accepted" | "rejected";
  evaluated_at: string;
  evidence_sha256: string;
  external_order_submission_allowed: false;
  offline_only: true;
  policy: { checksum: string; version: string };
  position_sizing_exposed: false;
  provider_reason_codes: Array<{ code: string; namespace: "trd_bot" }>;
  source: Omit<SourceReference, "resource_type"> & { resource_type: "risk_gate" };
  uncertainty: {
    reason_code: "TRD_BOT_RISK_UNCERTAINTY_NOT_SUPPLIED";
    state: "not_supplied";
    value: null;
  };
};

type RiskGateDetail = {
  provider: ProviderStatus;
  risk_gate: RiskGateExplanation | null;
  schema_version: "nexora-risk-gate-explanation-v1";
};

export type PortfolioAnalysis = {
  candidate_id: string;
  checks: DecisionPolicyCheck[];
  correlation: {
    evidence: string;
    maximum_absolute_correlation: string | null;
    status: "available" | "not_applicable" | "unavailable";
  };
  exposure: {
    candidate_notional: string;
    current_exposure_fraction: string;
    current_gross_notional: string;
    projected_asset_concentration_fraction: string;
    projected_exposure_fraction: string;
    projected_gross_notional: string;
  };
  recommendation: "accept" | "reject";
  scenarios: Array<{
    candidate_pnl: string;
    existing_pnl: string;
    loss_fraction: string;
    projected_equity: string;
    shock_fraction: string;
  }>;
  snapshot: {
    as_of: string;
    mode: "paper" | "shadow";
    open_positions: Array<unknown>;
    source: "empty_baseline" | "persisted_simulation";
  };
};

export type PortfolioImpact = {
  analysis: PortfolioAnalysis | null;
  analyzed_at: string;
  candidate_id: string | null;
  disposition: "accepted" | "rejected" | "unavailable";
  evidence_sha256: string;
  external_order_submission_allowed: false;
  order_intent_created: false;
  policy: { checksum: string; version: string };
  provider_reason_codes: Array<{ code: string; namespace: "trd_bot" }>;
  recommendation: "accept" | "reject" | "unavailable";
  risk_gate_checksum_cross_validated: true;
  snapshot_id: string | null;
  transaction_created: false;
  uncertainty: {
    reason_code: "TRD_BOT_PORTFOLIO_UNCERTAINTY_NOT_SUPPLIED";
    state: "not_supplied";
    value: null;
  };
};

type PortfolioImpactDetail = {
  portfolio_impact: PortfolioImpact | null;
  provider: ProviderStatus;
  schema_version: "nexora-portfolio-candidate-impact-v1";
};

export type ReviewAction = "accept" | "defer" | "reject";

export type DecisionReview = {
  action: ReviewAction;
  decision_id: string;
  delivery_status: "accepted" | "duplicate" | "pending";
  order_intent_created: false;
  reason_code: string;
  reason_note: string | null;
  recorded_at: string;
  review_id: string;
  review_version: number;
  portfolio_mode: "paper" | "shadow";
  revisit_at: string | null;
  supersedes_review_id: string | null;
  reviewed_at: string;
  transaction_created: false;
};

export type DecisionReviewContext = {
  current_version: number;
  decision_id: string;
  evidence_generation: number | null;
  latest_review_id: string | null;
  local_state: "accepted" | "deferred" | "rejected" | "review_pending";
  provider_delivery_required: boolean;
  reviewable: boolean;
  reviews: DecisionReview[];
  schema_version: "nexora-human-decision-review-v1";
  source_evidence_checksum: string | null;
};

export function decisionContextId(item: DecisionFeedItem | undefined): string | undefined {
  if (!item) return undefined;
  if (item.resource_type === "decision_evaluation") return item.resource_id;
  const evaluationId = item.evidence.evaluation_id;
  return typeof evaluationId === "string" && evaluationId ? evaluationId : undefined;
}

export const decisionPanels = ["evidence", "risk", "impact", "scenarios", "reviews"] as const;
export type DecisionPanel = (typeof decisionPanels)[number];
export type DecisionKind = "records" | "candidates";
export type DecisionRoute = { kind: DecisionKind; resourceId: string; panel: DecisionPanel };

export function decisionHref(locale: Locale, route: DecisionRoute): string {
  const base = `/${locale}/decisions/${route.kind}/${encodeURIComponent(route.resourceId)}`;
  return route.panel === "evidence" ? base : `${base}/${route.panel}`;
}

export function decisionFeedPage(cursor: string | null, signal: AbortSignal, limit = 25) {
  const query = new URLSearchParams({ limit: String(limit) });
  if (cursor) query.set("cursor", cursor);
  return apiRequest<DecisionFeedPage>(`/api/v1/decisions?${query}`, { signal });
}

async function optionalEvidence<T>(load: () => Promise<T>): Promise<T | null> {
  try {
    return await load();
  } catch (error) {
    if (error instanceof ApiRequestError && error.status === 404) return null;
    throw error;
  }
}

type DecisionEvidence = {
  item: DecisionFeedItem | null;
  provider?: ProviderStatus;
};

async function findEvidence(route: DecisionRoute, signal: AbortSignal): Promise<DecisionEvidence> {
  if (route.kind === "candidates") {
    const detail = await optionalEvidence(() =>
      apiRequest<CandidateDetail>(`/api/v1/candidates/${encodeURIComponent(route.resourceId)}`, {
        signal,
      }),
    );
    const item = detail?.candidate;
    return {
      item:
        item?.resource_type === "candidate" && item.resource_id === route.resourceId ? item : null,
      provider: detail?.provider,
    };
  }

  let cursor: string | null = null;
  const seen = new Set<string>();
  do {
    const page = await decisionFeedPage(cursor, signal, 100);
    const item = page.items.find(
      (row) => row.resource_type === "decision_evaluation" && row.resource_id === route.resourceId,
    );
    if (item || !page.next_cursor) return { item: item ?? null, provider: page.provider };
    cursor = page.next_cursor;
    if (seen.has(cursor)) throw new Error("The evidence cursor repeated");
    seen.add(cursor);
  } while (cursor);
  return { item: null };
}

export function readDecisionReviews(decisionId: string, signal: AbortSignal) {
  return apiRequest<DecisionReviewContext>(
    `/api/v1/decisions/${encodeURIComponent(decisionId)}/reviews`,
    { signal },
  );
}

export type ReviewSubmission = {
  key: string;
  body: {
    action: ReviewAction;
    evidence_generation: number;
    expected_version: number;
    portfolio_mode: "paper" | "shadow";
    reason_code: string;
    reason_note: string | null;
    revisit_at: string | null;
    reviewed_at: string;
    source_evidence_checksum: string;
    supersedes_review_id: string | null;
  };
};

export function writeDecisionReview(
  decisionId: string,
  submission: ReviewSubmission,
  signal: AbortSignal,
) {
  return apiRequest<DecisionReview>(`/api/v1/decisions/${encodeURIComponent(decisionId)}/reviews`, {
    body: submission.body,
    headers: { "Idempotency-Key": submission.key },
    method: "POST",
    signal,
  });
}

export type DecisionRecord = DecisionEvidence & {
  decisionId?: string;
  riskGate?: RiskGateExplanation | null;
  portfolioImpact?: PortfolioImpact | null;
  reviewContext?: DecisionReviewContext | null;
};

export async function loadDecisionRecord(
  route: DecisionRoute,
  signal: AbortSignal,
): Promise<DecisionRecord> {
  const evidence = await findEvidence(route, signal);
  const { item, provider } = evidence;
  const decisionId =
    route.kind === "records" ? route.resourceId : decisionContextId(item ?? undefined);
  const record = { ...evidence, decisionId };
  if (!decisionId || route.panel === "evidence") return record;
  const evaluation = encodeURIComponent(decisionId);
  const candidateId = item?.resource_type === "candidate" ? item.resource_id : undefined;

  if (route.panel === "reviews") {
    const context = await optionalEvidence(() => readDecisionReviews(decisionId, signal));
    return { ...record, reviewContext: context?.decision_id === decisionId ? context : null };
  }
  if (!item) return record;
  if (route.panel === "risk") {
    const response = await optionalEvidence(() =>
      apiRequest<RiskGateDetail>(`/api/v1/risk-gates/${evaluation}`, { signal }),
    );
    const riskGate = response?.risk_gate;
    const matches =
      response?.provider.generation === provider?.generation &&
      (!candidateId || riskGate?.candidate_id === candidateId);
    return { ...record, riskGate: matches ? (riskGate ?? null) : null };
  }
  const response = await optionalEvidence(() =>
    apiRequest<PortfolioImpactDetail>(`/api/v1/portfolio-impacts/${evaluation}`, { signal }),
  );
  const portfolioImpact = response?.portfolio_impact;
  const matches =
    response?.provider.generation === provider?.generation &&
    (!candidateId ||
      !portfolioImpact?.candidate_id ||
      portfolioImpact.candidate_id === candidateId);
  return { ...record, portfolioImpact: matches ? (portfolioImpact ?? null) : null };
}
