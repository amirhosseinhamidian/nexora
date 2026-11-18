"use client";

import {
  Alert,
  ResponsiveRecordList,
  EmptyState,
  Button,
  FieldError,
  FormField,
  Input,
  SearchInput,
  Select,
  Spinner,
  Textarea,
} from "@nexora/ui/primitives";
import { BookOpen, Plus, RefreshCw, Search, ShieldCheck } from "lucide-react";
import type { FormEvent } from "react";
import { useId, useCallback, useEffect, useRef, useState } from "react";

import type { Locale } from "@/i18n/config";
import type { Dictionary } from "@/i18n/dictionaries";
import { apiRequest } from "@/lib/api-client";

type EntryKind =
  | "correction"
  | "expectation_comparison"
  | "lesson"
  | "observed_outcome"
  | "owner_note"
  | "review_rationale";
type UncertaintyLevel = "high" | "low" | "medium" | "unknown";
type SourceKind =
  "external_record" | "manual_observation" | "portfolio_snapshot" | "provider_evidence";

type SourceLineage = {
  schema_version: "nexora-outcome-source-lineage-v1";
  source_kind: SourceKind;
  source_id: string;
  source_version: string | null;
  observed_at: string;
  checksum: string;
};

type JournalEntry = {
  entry_id: string;
  decision_id: string;
  entry_kind: EntryKind;
  content: string;
  uncertainty_level: UncertaintyLevel;
  uncertainty_note: string | null;
  review_id: string | null;
  portfolio_id: string | null;
  simulated_position_reference: string | null;
  decision_evidence_generation: number;
  decision_evidence_checksum: string;
  source_lineage: SourceLineage | null;
  occurred_at: string;
  recorded_at: string;
  supersedes_entry_id: string | null;
  author_kind: "owner";
  append_only: true;
  ai_generated: false;
  provider_rewritable: false;
};

type JournalList = {
  schema_version: "nexora-outcome-journal-v1";
  decision_id: string;
  items: JournalEntry[];
};

type PendingEntry = {
  body: Record<string, unknown>;
  decisionId: string;
  key: string;
};

function isJournalEntry(value: unknown): value is JournalEntry {
  if (!value || typeof value !== "object") return false;
  const candidate = value as Partial<JournalEntry>;
  return (
    typeof candidate.entry_id === "string" &&
    typeof candidate.decision_id === "string" &&
    typeof candidate.entry_kind === "string" &&
    typeof candidate.content === "string" &&
    typeof candidate.occurred_at === "string" &&
    typeof candidate.recorded_at === "string"
  );
}

export function OutcomeJournalPanel({
  decisionId,
  dictionary,
  locale,
}: {
  decisionId?: string;
  dictionary: Dictionary;
  locale: Locale;
}) {
  const fieldId = useId();
  const copy = dictionary.outcomeJournal;
  const [decisionInput, setDecisionInput] = useState("");
  const [activeDecision, setActiveDecision] = useState<string>();
  const [entries, setEntries] = useState<JournalEntry[]>([]);
  const [state, setState] = useState<"error" | "initial" | "loading" | "ready">("initial");
  const [entryKind, setEntryKind] = useState<EntryKind>("owner_note");
  const [content, setContent] = useState("");
  const [uncertaintyLevel, setUncertaintyLevel] = useState<UncertaintyLevel>("unknown");
  const [uncertaintyNote, setUncertaintyNote] = useState("");
  const [reviewId, setReviewId] = useState("");
  const [portfolioId, setPortfolioId] = useState("");
  const [simulatedPositionReference, setSimulatedPositionReference] = useState("");
  const [occurredAt, setOccurredAt] = useState("");
  const [supersedesEntryId, setSupersedesEntryId] = useState("");
  const [sourceKind, setSourceKind] = useState<SourceKind>("manual_observation");
  const [sourceId, setSourceId] = useState("");
  const [sourceVersion, setSourceVersion] = useState("");
  const [sourceObservedAt, setSourceObservedAt] = useState("");
  const [sourceChecksum, setSourceChecksum] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [operationError, setOperationError] = useState(false);
  const [pending, setPending] = useState<PendingEntry>();
  const loadSequence = useRef(0);
  const integratedDecisionId = useRef<string | undefined>(undefined);

  function changed() {
    setPending(undefined);
    setOperationError(false);
  }

  const load = useCallback(async (nextDecisionId: string) => {
    const sequence = ++loadSequence.current;
    setState("loading");
    setOperationError(false);
    try {
      const response = await apiRequest<JournalList>(
        `/api/v1/decisions/${encodeURIComponent(nextDecisionId)}/journal?limit=50`,
      );
      const nextEntries = Array.isArray(response?.items)
        ? response.items.filter(isJournalEntry)
        : [];
      if (sequence !== loadSequence.current) return;
      setEntries(nextEntries);
      setActiveDecision(nextDecisionId);
      setState("ready");
    } catch {
      if (sequence === loadSequence.current) setState("error");
    }
  }, []);

  useEffect(() => {
    if (!decisionId || decisionId === integratedDecisionId.current) return;
    const synchronize = window.setTimeout(() => {
      integratedDecisionId.current = decisionId;
      setDecisionInput(decisionId);
      void load(decisionId);
    }, 0);
    return () => window.clearTimeout(synchronize);
  }, [decisionId, load]);

  function loadDecision(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const decisionId = decisionInput.trim();
    if (decisionId) void load(decisionId);
  }

  async function createEntry(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (
      !activeDecision ||
      !content.trim() ||
      !occurredAt ||
      !observedOutcomeReady ||
      !correctionReady
    )
      return;
    const sourceLineage =
      entryKind === "observed_outcome"
        ? {
            checksum: sourceChecksum.trim(),
            observed_at: new Date(sourceObservedAt).toISOString(),
            schema_version: "nexora-outcome-source-lineage-v1",
            source_id: sourceId.trim(),
            source_kind: sourceKind,
            source_version: sourceVersion.trim() || null,
          }
        : null;
    const operation =
      pending?.decisionId === activeDecision
        ? pending
        : {
            body: {
              content: content.trim(),
              entry_kind: entryKind,
              occurred_at: new Date(occurredAt).toISOString(),
              portfolio_id: portfolioId.trim() || null,
              review_id: reviewId.trim() || null,
              simulated_position_reference: simulatedPositionReference.trim() || null,
              source_lineage: sourceLineage,
              supersedes_entry_id:
                entryKind === "correction" ? supersedesEntryId.trim() || null : null,
              uncertainty_level: uncertaintyLevel,
              uncertainty_note: uncertaintyNote.trim() || null,
            },
            decisionId: activeDecision,
            key: `nexora-outcome-journal-${crypto.randomUUID()}`,
          };
    setPending(operation);
    setSubmitting(true);
    setOperationError(false);
    try {
      const created = await apiRequest<JournalEntry>(
        `/api/v1/decisions/${encodeURIComponent(operation.decisionId)}/journal`,
        {
          body: operation.body,
          headers: { "Idempotency-Key": operation.key },
          method: "POST",
        },
      );
      if (!isJournalEntry(created)) throw new Error("Invalid journal response");
      setEntries((current) => [
        created,
        ...current.filter((item) => item.entry_id !== created.entry_id),
      ]);
      setContent("");
      setPending(undefined);
    } catch {
      setOperationError(true);
    } finally {
      setSubmitting(false);
    }
  }

  const observedOutcomeReady =
    entryKind !== "observed_outcome" ||
    Boolean(
      sourceId.trim() && sourceObservedAt && /^sha256:[0-9a-f]{64}$/.test(sourceChecksum.trim()),
    );
  const correctionReady = entryKind !== "correction" || Boolean(supersedesEntryId.trim());

  return (
    <section className="outcome-journal-panel" id="decision-journal">
      <div className="section-heading">
        <div>
          <p className="eyebrow">{copy.eyebrow}</p>
          <h2>{copy.title}</h2>
          <p>{copy.description}</p>
        </div>
        <BookOpen aria-hidden="true" size={28} />
      </div>

      <form className="journal-search" onSubmit={loadDecision}>
        <FormField id={`${fieldId}-decision-id`} label={copy.decisionId}>
          <SearchInput
            id={`${fieldId}-decision-id`}
            maxLength={160}
            onChange={(event) => setDecisionInput(event.target.value)}
            placeholder={copy.decisionPlaceholder}
            required
            value={decisionInput}
          />
        </FormField>
        <Button
          variant="secondary"
          className="secondary-button"
          disabled={!decisionInput.trim() || state === "loading"}
          type="submit"
        >
          <Search aria-hidden="true" size={16} />
          {copy.load}
        </Button>
      </form>

      {state === "initial" ? (
        <div className="journal-state">
          <BookOpen aria-hidden="true" size={22} />
          <span>{copy.initial}</span>
        </div>
      ) : state === "loading" ? (
        <Alert className="journal-state" role="status">
          <Spinner label="" />
          <span>{copy.loading}</span>
        </Alert>
      ) : state === "error" ? (
        <Alert tone="danger" className="journal-state error" role="alert">
          <span>{copy.error}</span>
          {decisionInput.trim() ? (
            <Button
              variant="secondary"
              className="secondary-button"
              onClick={() => void load(decisionInput.trim())}
              type="button"
            >
              <RefreshCw aria-hidden="true" size={16} />
              {copy.retry}
            </Button>
          ) : null}
        </Alert>
      ) : activeDecision ? (
        <div className="journal-workspace">
          <div className="journal-active-decision">
            <span>{copy.activeDecision}</span>
            <code dir="ltr">{activeDecision}</code>
          </div>

          {entries.length ? (
            <ResponsiveRecordList as="ol" className="journal-entry-list" label={copy.title}>
              {entries.map((entry) => (
                <li key={entry.entry_id}>
                  <div className="journal-entry-heading">
                    <span className="evidence-state">{copy.entryKinds[entry.entry_kind]}</span>
                    <time dateTime={entry.occurred_at}>
                      {new Intl.DateTimeFormat(locale, {
                        dateStyle: "medium",
                        timeStyle: "short",
                      }).format(new Date(entry.occurred_at))}
                    </time>
                  </div>
                  <p>{entry.content}</p>
                  <dl>
                    <div>
                      <dt>{copy.uncertainty}</dt>
                      <dd>{copy.uncertaintyLevels[entry.uncertainty_level]}</dd>
                    </div>
                    <div>
                      <dt>{copy.generation}</dt>
                      <dd>{entry.decision_evidence_generation}</dd>
                    </div>
                    <div className="wide">
                      <dt>{copy.decisionChecksum}</dt>
                      <dd>
                        <code dir="ltr">{entry.decision_evidence_checksum}</code>
                      </dd>
                    </div>
                    {entry.source_lineage ? (
                      <div className="wide">
                        <dt>{copy.sourceLineage}</dt>
                        <dd>
                          {copy.sourceKinds[entry.source_lineage.source_kind]} ·{" "}
                          {entry.source_lineage.source_id}
                          <br />
                          <code dir="ltr">{entry.source_lineage.checksum}</code>
                        </dd>
                      </div>
                    ) : null}
                    {entry.supersedes_entry_id ? (
                      <div className="wide">
                        <dt>{copy.supersedes}</dt>
                        <dd>
                          <code dir="ltr">{entry.supersedes_entry_id}</code>
                        </dd>
                      </div>
                    ) : null}
                  </dl>
                </li>
              ))}
            </ResponsiveRecordList>
          ) : (
            <EmptyState
              className="empty-state-card"
              headingLevel={2}
              icon={<BookOpen aria-hidden="true" size={28} />}
              title={copy.emptyTitle}
            >
              <p>{copy.emptyDescription}</p>
            </EmptyState>
          )}

          <form className="journal-form" onSubmit={(event) => void createEntry(event)}>
            <h3>{copy.createTitle}</h3>
            <div className="journal-form-grid">
              <FormField id={`${fieldId}-entry-kind`} label={copy.entryKind}>
                <Select
                  id={`${fieldId}-entry-kind`}
                  onValueChange={(value) => {
                    setEntryKind(value as EntryKind);
                    changed();
                  }}
                  value={entryKind}
                  options={Object.entries(copy.entryKinds).map(([value, label]) => ({
                    value: value,
                    label: label,
                  }))}
                />
              </FormField>
              <FormField id={`${fieldId}-occurred-at`} label={copy.occurredAt}>
                <Input
                  id={`${fieldId}-occurred-at`}
                  onChange={(event) => {
                    setOccurredAt(event.target.value);
                    changed();
                  }}
                  required
                  type="datetime-local"
                  value={occurredAt}
                />
              </FormField>
              <FormField id={`${fieldId}-uncertainty`} label={copy.uncertainty}>
                <Select
                  id={`${fieldId}-uncertainty`}
                  onValueChange={(value) => {
                    setUncertaintyLevel(value as UncertaintyLevel);
                    changed();
                  }}
                  value={uncertaintyLevel}
                  options={Object.entries(copy.uncertaintyLevels).map(([value, label]) => ({
                    value: value,
                    label: label,
                  }))}
                />
              </FormField>
              <FormField id={`${fieldId}-uncertainty-note`} label={copy.uncertaintyNote}>
                <Input
                  id={`${fieldId}-uncertainty-note`}
                  maxLength={500}
                  onChange={(event) => {
                    setUncertaintyNote(event.target.value);
                    changed();
                  }}
                  value={uncertaintyNote}
                />
              </FormField>
              <FormField className="wide" id={`${fieldId}-content`} label={copy.content}>
                <Textarea
                  id={`${fieldId}-content`}
                  maxLength={4000}
                  onChange={(event) => {
                    setContent(event.target.value);
                    changed();
                  }}
                  required
                  value={content}
                />
              </FormField>
              <FormField id={`${fieldId}-review-id`} label={copy.reviewId}>
                <Input
                  id={`${fieldId}-review-id`}
                  onChange={(event) => {
                    setReviewId(event.target.value);
                    changed();
                  }}
                  value={reviewId}
                />
              </FormField>
              <FormField id={`${fieldId}-portfolio-id`} label={copy.portfolioId}>
                <Input
                  id={`${fieldId}-portfolio-id`}
                  onChange={(event) => {
                    setPortfolioId(event.target.value);
                    changed();
                  }}
                  value={portfolioId}
                />
              </FormField>
              <FormField
                className="wide"
                id={`${fieldId}-simulated-position`}
                label={copy.simulatedPosition}
              >
                <Input
                  id={`${fieldId}-simulated-position`}
                  maxLength={160}
                  onChange={(event) => {
                    setSimulatedPositionReference(event.target.value);
                    changed();
                  }}
                  value={simulatedPositionReference}
                />
              </FormField>

              {entryKind === "correction" ? (
                <FormField
                  className="wide"
                  id={`${fieldId}-superseded-entry`}
                  label={copy.supersededEntry}
                >
                  <Input
                    id={`${fieldId}-superseded-entry`}
                    onChange={(event) => {
                      setSupersedesEntryId(event.target.value);
                      changed();
                    }}
                    required
                    value={supersedesEntryId}
                  />
                </FormField>
              ) : null}

              {entryKind === "observed_outcome" ? (
                <fieldset className="journal-lineage wide">
                  <legend>{copy.sourceLineage}</legend>
                  <FormField id={`${fieldId}-source-kind`} label={copy.sourceKind}>
                    <Select
                      id={`${fieldId}-source-kind`}
                      onValueChange={(value) => {
                        setSourceKind(value as SourceKind);
                        changed();
                      }}
                      value={sourceKind}
                      options={Object.entries(copy.sourceKinds).map(([value, label]) => ({
                        value: value,
                        label: label,
                      }))}
                    />
                  </FormField>
                  <FormField id={`${fieldId}-source-id`} label={copy.sourceId}>
                    <Input
                      id={`${fieldId}-source-id`}
                      maxLength={160}
                      onChange={(event) => {
                        setSourceId(event.target.value);
                        changed();
                      }}
                      required
                      value={sourceId}
                    />
                  </FormField>
                  <FormField id={`${fieldId}-source-version`} label={copy.sourceVersion}>
                    <Input
                      id={`${fieldId}-source-version`}
                      maxLength={80}
                      onChange={(event) => {
                        setSourceVersion(event.target.value);
                        changed();
                      }}
                      value={sourceVersion}
                    />
                  </FormField>
                  <FormField id={`${fieldId}-source-observed-at`} label={copy.sourceObservedAt}>
                    <Input
                      id={`${fieldId}-source-observed-at`}
                      onChange={(event) => {
                        setSourceObservedAt(event.target.value);
                        changed();
                      }}
                      required
                      type="datetime-local"
                      value={sourceObservedAt}
                    />
                  </FormField>
                  <FormField
                    className="wide"
                    id={`${fieldId}-source-checksum`}
                    label={copy.sourceChecksum}
                  >
                    <Input
                      id={`${fieldId}-source-checksum`}
                      dir="ltr"
                      onChange={(event) => {
                        setSourceChecksum(event.target.value);
                        changed();
                      }}
                      pattern="sha256:[0-9a-f]{64}"
                      required
                      value={sourceChecksum}
                    />
                  </FormField>
                </fieldset>
              ) : null}
            </div>
            <Button
              className="primary-button"
              disabled={
                submitting ||
                !content.trim() ||
                !occurredAt ||
                !observedOutcomeReady ||
                !correctionReady
              }
              type="submit"
            >
              <Plus aria-hidden="true" size={16} />
              {submitting ? copy.saving : copy.create}
            </Button>
          </form>

          {operationError ? (
            <FieldError className="form-error">{copy.operationError}</FieldError>
          ) : null}
        </div>
      ) : null}

      <p className="journal-boundary">
        <ShieldCheck aria-hidden="true" size={18} />
        {copy.boundary}
      </p>
    </section>
  );
}
