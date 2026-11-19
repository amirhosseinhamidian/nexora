import {
  Alert,
  Button,
  ConfirmationDialog,
  FieldError,
  FormField,
  IconButton,
  Input,
  ResponsiveRecordList,
  Select,
  Textarea,
  ToastRegion,
} from "@nexora/ui/primitives";
import { useEffect, useId, useRef, useState, type FormEvent } from "react";

import type { Locale } from "@/i18n/config";
import type { Dictionary } from "@/i18n/dictionaries";
import { ApiRequestError } from "@/lib/api-client";
import {
  readDecisionReviews,
  writeDecisionReview,
  type DecisionReviewContext,
  type ReviewAction,
  type ReviewSubmission,
} from "@/lib/decision-intelligence";
import { formatTimestamp, localizeDigits } from "@/lib/portfolio-analytics";

const reviewReasons = {
  accept: [
    "owner.accept.evidence_sufficient",
    "owner.accept.portfolio_fit",
    "owner.accept.risk_within_policy",
    "owner.accept.observe_in_paper_shadow",
    "owner.accept.other_with_note",
  ],
  reject: [
    "owner.reject.stale_context",
    "owner.reject.low_confidence",
    "owner.reject.data_quality",
    "owner.reject.regime_mismatch",
    "owner.reject.exposure",
    "owner.reject.concentration",
    "owner.reject.policy_limit",
    "owner.reject.uncertainty",
    "owner.reject.portfolio_conflict",
    "owner.reject.other_with_note",
  ],
  defer: [
    "owner.defer.evidence_pending",
    "owner.defer.market_context_pending",
    "owner.defer.valuation_missing",
    "owner.defer.provider_degraded",
    "owner.defer.review_later",
    "owner.defer.other_with_note",
  ],
} as const;

export function DecisionReviewPanel({
  context: initialContext,
  decisionId,
  dictionary,
  generation,
  locale,
  onReloadEvidence,
  sourceChecksum,
}: {
  context: DecisionReviewContext | null;
  decisionId?: string;
  dictionary: Dictionary;
  generation?: number;
  locale: Locale;
  onReloadEvidence?: () => void;
  sourceChecksum?: string;
}) {
  const copy = dictionary.decisionFeed;
  const labels = dictionary.decisionPages;
  const id = useId();
  const request = useRef<AbortController | null>(null);
  const [context, setContext] = useState(initialContext);
  const [action, setAction] = useState<ReviewAction>("accept");
  const [reasonCode, setReasonCode] = useState<string>(reviewReasons.accept[0]);
  const [reasonNote, setReasonNote] = useState("");
  const [revisitAt, setRevisitAt] = useState("");
  const [mode, setMode] = useState<"paper" | "shadow">("paper");
  const [busy, setBusy] = useState(false);
  const [confirmation, setConfirmation] = useState<ReviewSubmission>();
  const [retrySubmission, setRetrySubmission] = useState<ReviewSubmission>();
  const [needsRefresh, setNeedsRefresh] = useState(false);
  const [formError, setFormError] = useState("");
  const [notice, setNotice] = useState<{ title: string; tone: "success" | "warning" | "danger" }>();

  useEffect(() => () => request.current?.abort(), []);

  const reviewable = !!(
    decisionId &&
    context?.reviewable &&
    generation &&
    context.evidence_generation === generation &&
    context.source_evidence_checksum &&
    (!sourceChecksum || context.source_evidence_checksum === sourceChecksum)
  );
  const disabled = busy || !reviewable || needsRefresh || !!retrySubmission;
  const reasonLabel = (code: string) =>
    Object.hasOwn(labels.reasons, code)
      ? labels.reasons[code as keyof typeof labels.reasons]
      : labels.unknownReason;

  function prepare(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (disabled || !context?.source_evidence_checksum || !generation) return;
    setFormError("");
    const note = reasonNote.trim();
    if (reasonCode.endsWith(".other_with_note") && !note) {
      setFormError(labels.noteRequired);
      return;
    }
    const reviewedAt = new Date();
    const revisit = action === "defer" && revisitAt ? new Date(revisitAt) : null;
    if (revisit && (!Number.isFinite(revisit.getTime()) || revisit <= reviewedAt)) {
      setFormError(labels.revisitInFuture);
      return;
    }
    setConfirmation({
      key: `nexora-review-${crypto.randomUUID()}`,
      body: {
        action,
        evidence_generation: generation,
        expected_version: context.current_version,
        portfolio_mode: mode,
        reason_code: reasonCode,
        reason_note: note || null,
        revisit_at: revisit?.toISOString() ?? null,
        reviewed_at: reviewedAt.toISOString(),
        source_evidence_checksum: context.source_evidence_checksum,
        supersedes_review_id: context.latest_review_id,
      },
    });
  }

  async function refresh(signal: AbortSignal) {
    if (!decisionId) return;
    try {
      const next = await readDecisionReviews(decisionId, signal);
      if (signal.aborted) return;
      if (next.decision_id !== decisionId) throw new Error("Review context mismatch");
      setContext(next);
      setNeedsRefresh(false);
    } catch {
      if (!signal.aborted) setNeedsRefresh(true);
    }
  }

  async function run(submission?: ReviewSubmission) {
    if (!decisionId || request.current || (submission && !reviewable)) return;
    const controller = new AbortController();
    request.current = controller;
    setConfirmation(undefined);
    setBusy(true);
    if (submission) setNotice(undefined);
    try {
      if (submission) {
        const receipt = await writeDecisionReview(decisionId, submission, controller.signal);
        if (controller.signal.aborted) return;
        if (receipt.decision_id !== decisionId) throw new Error("Review receipt mismatch");

        setRetrySubmission(undefined);
        setReasonNote("");
        setRevisitAt("");
        setNotice({ title: labels.reviewSaved, tone: "success" });
      }
      await refresh(controller.signal);
    } catch (error) {
      if (controller.signal.aborted) return;
      const status = error instanceof ApiRequestError ? error.status : undefined;
      if (status === 409 || status === 404) {
        setRetrySubmission(undefined);
        setNotice({ title: labels.reviewConflict, tone: "warning" });
        await refresh(controller.signal);
      } else if (status !== undefined && status >= 400 && status < 500 && status !== 429) {
        setRetrySubmission(undefined);
        setNotice({ title: labels.reviewRejected, tone: "danger" });
      } else {
        setRetrySubmission(submission);
        setNotice({ title: labels.reviewUnconfirmed, tone: "warning" });
      }
    } finally {
      request.current = null;
      if (!controller.signal.aborted) setBusy(false);
    }
  }

  return (
    <section className="decision-review" aria-label={copy.reviewTitle}>
      <div className="risk-heading">
        <h2>{copy.reviewTitle}</h2>
        {context ? (
          <span className={`evidence-state ${context.local_state}`}>
            {copy.reviewStates[context.local_state]}
          </span>
        ) : null}
      </div>
      <p>{copy.reviewBoundary}</p>
      <ToastRegion
        label={labels.notifications}
        messages={
          notice
            ? [
                {
                  ...notice,
                  id: "decision-review",
                  action: (
                    <IconButton aria-label={labels.dismiss} onClick={() => setNotice(undefined)}>
                      <span aria-hidden="true">×</span>
                    </IconButton>
                  ),
                },
              ]
            : []
        }
      />
      {context && reviewable ? (
        <form className="decision-review-form" onSubmit={prepare}>
          <FormField id={`${id}-action`} label={copy.reviewAction}>
            <Select
              disabled={disabled}
              id={`${id}-action`}
              value={action}
              onValueChange={(value) => {
                if (value !== "accept" && value !== "defer" && value !== "reject") return;
                setAction(value);
                setReasonCode(reviewReasons[value][0]);
                setFormError("");
                if (value !== "defer") setRevisitAt("");
              }}
              options={Object.entries(copy.reviewActions).map(([value, label]) => ({
                value,
                label,
              }))}
            />
          </FormField>
          <FormField id={`${id}-mode`} label={copy.portfolioMode}>
            <Select
              disabled={disabled}
              id={`${id}-mode`}
              value={mode}
              onValueChange={(value) => {
                if (value === "paper" || value === "shadow") setMode(value);
              }}
              options={Object.entries(labels.modes).map(([value, label]) => ({ value, label }))}
            />
          </FormField>
          <FormField className="wide" id={`${id}-reason`} label={copy.ownerReason}>
            <Select
              disabled={disabled}
              id={`${id}-reason`}
              value={reasonCode}
              onValueChange={(value) => {
                setReasonCode(value);
                setFormError("");
              }}
              options={reviewReasons[action].map((value) => ({ value, label: reasonLabel(value) }))}
            />
          </FormField>
          <FormField className="wide" id={`${id}-note`} label={copy.reasonNote}>
            <Textarea
              disabled={disabled}
              id={`${id}-note`}
              maxLength={500}
              onChange={(event) => {
                setReasonNote(event.target.value);
                setFormError("");
              }}
              value={reasonNote}
            />
          </FormField>
          {action === "defer" ? (
            <FormField className="wide" id={`${id}-revisit`} label={copy.revisitAt}>
              <Input
                disabled={disabled}
                id={`${id}-revisit`}
                type="datetime-local"
                onChange={(event) => {
                  setRevisitAt(event.target.value);
                  setFormError("");
                }}
                value={revisitAt}
              />
            </FormField>
          ) : null}
          {formError ? <FieldError className="wide">{formError}</FieldError> : null}
          <Button className="wide" disabled={disabled} type="submit">
            {copy.reviewSubmit}
          </Button>
        </form>
      ) : (
        <Alert tone="warning">
          <p>{copy.reviewUnavailable}</p>
          {onReloadEvidence && context?.reviewable ? (
            <Button onClick={onReloadEvidence} variant="secondary">
              {copy.retry}
            </Button>
          ) : null}
        </Alert>
      )}
      {busy ? <p role="status">{copy.reviewSubmitting}</p> : null}
      {needsRefresh ? (
        <Alert tone="warning">
          <p>{labels.reviewRefreshFailed}</p>
          <Button disabled={busy} onClick={() => void run()} variant="secondary">
            {labels.refreshReviews}
          </Button>
        </Alert>
      ) : null}
      {retrySubmission ? (
        <Button
          disabled={busy}
          onClick={() => setConfirmation(retrySubmission)}
          variant="secondary"
        >
          {labels.retryReview}
        </Button>
      ) : null}
      <h3>{labels.reviewHistory}</h3>
      {context?.reviews.length ? (
        <ResponsiveRecordList as="ol" className="review-history" label={labels.reviewHistory}>
          {context.reviews.toReversed().map((review) => (
            <li key={review.review_id}>
              <strong>
                {copy.reviewActions[review.action]} · v
                {localizeDigits(String(review.review_version), locale)}
              </strong>
              <span>{reasonLabel(review.reason_code)}</span>
              {review.reason_note ? <bdi>{review.reason_note}</bdi> : null}
              <small>
                {labels.delivery[review.delivery_status]} ·{" "}
                <time dateTime={review.recorded_at}>
                  {formatTimestamp(review.recorded_at, locale)}
                </time>
              </small>
              {review.revisit_at ? (
                <small>
                  {copy.revisitAt} ·{" "}
                  <time dateTime={review.revisit_at}>
                    {formatTimestamp(review.revisit_at, locale)}
                  </time>
                </small>
              ) : null}
            </li>
          ))}
        </ResponsiveRecordList>
      ) : context ? (
        <p>{copy.noReviews}</p>
      ) : null}
      {confirmation ? (
        <ConfirmationDialog
          cancelLabel={labels.cancel}
          confirmLabel={copy.reviewSubmit}
          description={
            <>
              <bdi>{decisionId}</bdi>
              <br />
              {copy.reviewActions[confirmation.body.action]} ·{" "}
              {reasonLabel(confirmation.body.reason_code)}
              <br />
              {labels.modes[confirmation.body.portfolio_mode]}
              <br />
              {labels.reviewVersion}{" "}
              {localizeDigits(String(confirmation.body.expected_version), locale)}
              {confirmation.body.reason_note ? (
                <>
                  <br />
                  <bdi>{confirmation.body.reason_note}</bdi>
                </>
              ) : null}
              {confirmation.body.revisit_at ? (
                <>
                  <br />
                  {formatTimestamp(confirmation.body.revisit_at, locale)}
                </>
              ) : null}
            </>
          }
          onCancel={() => setConfirmation(undefined)}
          onConfirm={() => void run(confirmation)}
          open
          title={labels.confirmReview}
        />
      ) : null}
    </section>
  );
}
