"use client";

import { AlertTriangle, ChevronRight, Database, LoaderCircle, RefreshCw } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import type { Locale } from "@/i18n/config";
import type { Dictionary } from "@/i18n/dictionaries";
import { apiRequest } from "@/lib/api-client";

type ProviderStatus = {
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

type DecisionFeedItem = {
  decision_kind: "candidate" | "portfolio_assessment";
  evidence: Record<string, unknown>;
  evidence_sha256: string;
  local_state: "review_pending";
  resource_id: string;
  resource_type: "candidate" | "decision_evaluation";
  source: SourceReference;
};

type DecisionFeedPage = {
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

type RiskGateExplanation = {
  approved_candidate_id: string | null;
  candidate_id: string;
  checks: Array<{
    actual_value: string;
    explanation: string;
    limit_value: string;
    name: string;
    passed: boolean;
  }>;
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

function displayValue(value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

function formatTimestamp(value: string, locale: Locale): string {
  return new Intl.DateTimeFormat(locale === "fa" ? "fa-IR" : "en-GB", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function EvidencePanel({
  copy,
  item,
  locale,
}: {
  copy: Dictionary["decisionFeed"];
  item: DecisionFeedItem;
  locale: Locale;
}) {
  return (
    <article className="decision-evidence" aria-label={copy.detailTitle}>
      <div className="decision-evidence-heading">
        <div>
          <p className="eyebrow">{copy.detailEyebrow}</p>
          <h3>{item.resource_id}</h3>
        </div>
        <span className="evidence-state">{copy.reviewPending}</span>
      </div>
      <dl className="source-reference-grid">
        <div>
          <dt>{copy.observedAt}</dt>
          <dd>{formatTimestamp(item.source.observed_at, locale)}</dd>
        </div>
        <div>
          <dt>{copy.providerVersion}</dt>
          <dd dir="ltr">TRD Bot {item.source.source_version}</dd>
        </div>
        <div>
          <dt>{copy.sourceSchema}</dt>
          <dd dir="ltr">{item.source.resource_schema_version}</dd>
        </div>
        <div>
          <dt>{copy.aggregateVersion}</dt>
          <dd dir="ltr">{item.source.aggregate_version ?? "—"}</dd>
        </div>
        <div className="wide">
          <dt>{copy.sourceChecksum}</dt>
          <dd className="checksum" dir="ltr">
            {item.source.checksum}
          </dd>
        </div>
        <div className="wide">
          <dt>{copy.evidenceChecksum}</dt>
          <dd className="checksum" dir="ltr">
            sha256:{item.evidence_sha256}
          </dd>
        </div>
      </dl>
      <h4>{copy.evidenceTitle}</h4>
      <dl className="evidence-payload">
        {Object.entries(item.evidence).map(([key, value]) => (
          <div key={key}>
            <dt dir="ltr">{key}</dt>
            <dd dir="ltr">{displayValue(value)}</dd>
          </div>
        ))}
      </dl>
      <p className="advisory-boundary">{copy.advisoryBoundary}</p>
    </article>
  );
}

function RiskGatePanel({
  copy,
  riskGate,
}: {
  copy: Dictionary["decisionFeed"];
  riskGate: RiskGateExplanation | null;
}) {
  if (!riskGate) {
    return (
      <section className="risk-explanation unavailable" aria-label={copy.riskTitle}>
        <h4>{copy.riskTitle}</h4>
        <p>{copy.riskUnavailable}</p>
      </section>
    );
  }
  return (
    <section className="risk-explanation" aria-label={copy.riskTitle}>
      <div className="risk-heading">
        <div>
          <p className="eyebrow">{copy.riskEyebrow}</p>
          <h4>{copy.riskTitle}</h4>
        </div>
        <span className={`risk-decision ${riskGate.decision}`}>
          {copy.riskDecisions[riskGate.decision]}
        </span>
      </div>
      <dl className="risk-policy-grid">
        <div>
          <dt>{copy.policyVersion}</dt>
          <dd dir="ltr">{riskGate.policy.version}</dd>
        </div>
        <div>
          <dt>{copy.evaluatedAt}</dt>
          <dd dir="ltr">{riskGate.evaluated_at}</dd>
        </div>
        <div className="wide">
          <dt>{copy.policyChecksum}</dt>
          <dd className="checksum" dir="ltr">
            {riskGate.policy.checksum}
          </dd>
        </div>
      </dl>
      <h5>{copy.providerReasons}</h5>
      {riskGate.provider_reason_codes.length ? (
        <ul className="risk-reasons">
          {riskGate.provider_reason_codes.map((reason) => (
            <li key={`${reason.namespace}:${reason.code}`} dir="ltr">
              <span>{reason.namespace}</span>
              <strong>{reason.code}</strong>
            </li>
          ))}
        </ul>
      ) : (
        <p className="risk-empty-reasons">{copy.noProviderReasons}</p>
      )}
      <h5>{copy.policyChecks}</h5>
      <div className="risk-checks">
        {riskGate.checks.map((check) => (
          <article className={check.passed ? "passed" : "failed"} key={check.name}>
            <div>
              <strong dir="ltr">{check.name}</strong>
              <span>{check.passed ? copy.checkPassed : copy.checkFailed}</span>
            </div>
            <p>{check.explanation}</p>
            <small dir="ltr">
              {copy.actualValue}: {check.actual_value} · {copy.limitValue}: {check.limit_value}
            </small>
          </article>
        ))}
      </div>
      <div className="risk-uncertainty" role="status">
        <strong>{copy.uncertainty}</strong>
        <p>{copy.uncertaintyNotSupplied}</p>
        <code>{riskGate.uncertainty.reason_code}</code>
      </div>
      <p className="advisory-boundary">{copy.riskBoundary}</p>
    </section>
  );
}

export function DecisionFeed({ dictionary, locale }: { dictionary: Dictionary; locale: Locale }) {
  const copy = dictionary.decisionFeed;
  const [state, setState] = useState<"error" | "loading" | "ready">("loading");
  const [page, setPage] = useState<DecisionFeedPage>();
  const [selected, setSelected] = useState<DecisionFeedItem>();
  const [riskGate, setRiskGate] = useState<RiskGateExplanation | null>();
  const [detailLoading, setDetailLoading] = useState(false);
  const [revision, setRevision] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    async function load() {
      setState("loading");
      try {
        const response = await apiRequest<DecisionFeedPage>("/api/v1/decisions?limit=25", {
          signal: controller.signal,
        });
        if (controller.signal.aborted) return;
        setPage(response);
        setSelected(response.items[0]);
        setRiskGate(undefined);
        setState("ready");
      } catch {
        if (!controller.signal.aborted) setState("error");
      }
    }
    void load();
    return () => controller.abort();
  }, [revision]);

  const selectItem = useCallback(async (item: DecisionFeedItem) => {
    setRiskGate(undefined);
    if (item.resource_type !== "candidate") {
      setSelected(item);
      return;
    }
    setDetailLoading(true);
    try {
      const detail = await apiRequest<CandidateDetail>(
        `/api/v1/candidates/${encodeURIComponent(item.resource_id)}`,
      );
      if (detail.candidate) {
        setSelected(detail.candidate);
        const evaluationId = detail.candidate.evidence.evaluation_id;
        if (typeof evaluationId === "string" && evaluationId) {
          try {
            const risk = await apiRequest<RiskGateDetail>(
              `/api/v1/risk-gates/${encodeURIComponent(evaluationId)}`,
            );
            if (risk.provider.generation !== detail.provider.generation) {
              throw new Error("risk projection generation changed");
            }
            setRiskGate(risk.risk_gate);
          } catch {
            setRiskGate(null);
          }
        } else {
          setRiskGate(null);
        }
      }
    } catch {
      setState("error");
    } finally {
      setDetailLoading(false);
    }
  }, []);

  async function loadMore() {
    if (!page?.next_cursor) return;
    try {
      const response = await apiRequest<DecisionFeedPage>(
        `/api/v1/decisions?limit=25&cursor=${encodeURIComponent(page.next_cursor)}`,
      );
      setPage({ ...response, items: [...page.items, ...response.items] });
    } catch {
      setState("error");
    }
  }

  return (
    <section className="decision-feed" id="decisions">
      <div className="operations-heading">
        <div>
          <p className="eyebrow">{copy.eyebrow}</p>
          <h2>{copy.title}</h2>
          <p>{copy.description}</p>
        </div>
        <Database aria-hidden="true" size={28} />
      </div>

      {state === "loading" ? (
        <div className="inline-state">
          <LoaderCircle className="spin" size={20} /> {copy.loading}
        </div>
      ) : state === "error" ? (
        <div className="inline-state warning">
          <AlertTriangle size={20} />
          <span>{copy.error}</span>
          <button
            className="secondary-button"
            onClick={() => setRevision((value) => value + 1)}
            type="button"
          >
            <RefreshCw size={16} /> {copy.retry}
          </button>
        </div>
      ) : page ? (
        <>
          {page.provider.state !== "ready" && (
            <div className="provider-state" role="status">
              <AlertTriangle aria-hidden="true" size={19} />
              <div>
                <strong>{copy.providerDegraded}</strong>
                <p>{copy.providerStates[page.provider.state]}</p>
              </div>
            </div>
          )}
          {page.items.length === 0 ? (
            <div className="empty-state-card">
              <h3>{copy.emptyTitle}</h3>
              <p>{copy.emptyDescription}</p>
            </div>
          ) : (
            <div className="decision-workspace">
              <div className="decision-list" aria-label={copy.listLabel}>
                {page.items.map((item) => (
                  <button
                    aria-pressed={selected?.resource_id === item.resource_id}
                    className="decision-list-item"
                    key={`${item.resource_type}:${item.resource_id}`}
                    onClick={() => void selectItem(item)}
                    type="button"
                  >
                    <span>
                      <strong>{item.resource_id}</strong>
                      <small>
                        {copy.resourceTypes[item.resource_type]} ·{" "}
                        {formatTimestamp(item.source.observed_at, locale)}
                      </small>
                    </span>
                    <ChevronRight aria-hidden="true" size={18} />
                  </button>
                ))}
                {page.next_cursor && (
                  <button
                    className="secondary-button"
                    onClick={() => void loadMore()}
                    type="button"
                  >
                    {copy.loadMore}
                  </button>
                )}
              </div>
              <div className="decision-detail">
                {detailLoading ? (
                  <div className="inline-state">
                    <LoaderCircle className="spin" size={20} /> {copy.loadingDetail}
                  </div>
                ) : selected ? (
                  <>
                    <EvidencePanel copy={copy} item={selected} locale={locale} />
                    {selected.resource_type === "candidate" && riskGate !== undefined ? (
                      <RiskGatePanel copy={copy} riskGate={riskGate} />
                    ) : null}
                  </>
                ) : null}
              </div>
            </div>
          )}
        </>
      ) : null}
    </section>
  );
}
