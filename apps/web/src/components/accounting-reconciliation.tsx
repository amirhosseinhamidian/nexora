import {
  Button,
  Disclosure,
  EmptyState,
  FormField,
  Input,
  ResponsiveRecordList,
  Select,
} from "@nexora/ui/primitives";
import { useId, useState } from "react";

import type { Locale } from "@/i18n/config";
import type { Dictionary } from "@/i18n/dictionaries";
import type { ReconciliationCase, ReconciliationDecision } from "@/lib/portfolio-accounting";
import { formatTimestamp, localizeDigits } from "@/lib/portfolio-analytics";

type AccountingCopy = Dictionary["portfolioOperations"];
const decisions = ["matched", "accepted_difference", "resolved", "ignored_with_reason"] as const;

function ReconciliationCard({
  busy,
  copy,
  item,
  locale,
  onDecide,
  recentlyReauthenticated,
}: {
  busy: boolean;
  copy: AccountingCopy;
  item: ReconciliationCase;
  locale: Locale;
  onDecide: (item: ReconciliationCase, state: ReconciliationDecision, reason: string) => void;
  recentlyReauthenticated: boolean;
}) {
  const id = useId();
  const [decision, setDecision] = useState<ReconciliationDecision>("matched");
  const [reason, setReason] = useState("");
  const [invalidReason, setInvalidReason] = useState(false);

  function submit() {
    if (!recentlyReauthenticated || busy) return;
    const entered = reason.trim();
    if (entered.length < 8 || entered.length > 500) {
      setInvalidReason(true);
      return;
    }
    onDecide(item, decision, entered);
  }

  return (
    <li className="operation-card">
      <div className="operation-card-heading">
        <span className={`status-badge ${item.state}`}>{copy.reconciliationState[item.state]}</span>
        <time dateTime={item.updated_at}>{formatTimestamp(item.updated_at, locale)}</time>
      </div>
      {item.reason ? <p>{item.reason}</p> : null}
      <Disclosure className="accounting-disclosure" label={copy.reconciliation.evidence}>
        <dl className="accounting-evidence">
          <div>
            <dt>{copy.reconciliation.caseId}</dt>
            <dd>
              <code dir="ltr">{item.reconciliation_case_id}</code>
            </dd>
          </div>
          <div>
            <dt>{copy.reconciliation.difference}</dt>
            <dd>
              {copy.importReasons[item.difference_code as keyof AccountingCopy["importReasons"]] ??
                copy.importReasons.unknown}{" "}
              <code dir="ltr">{item.difference_code}</code>
            </dd>
          </div>
          <div>
            <dt>{copy.imports.batchId}</dt>
            <dd>
              <code dir="ltr">{item.import_batch_id}</code>
            </dd>
          </div>
          <div>
            <dt>{copy.reconciliation.rowId}</dt>
            <dd>
              <code dir="ltr">{item.import_row_id}</code>
            </dd>
          </div>
          <div>
            <dt>{copy.reconciliation.version}</dt>
            <dd>{localizeDigits(String(item.row_version), locale)}</dd>
          </div>
          {item.transaction_id ? (
            <div>
              <dt>{copy.journal.recordId}</dt>
              <dd>
                <code dir="ltr">{item.transaction_id}</code>
              </dd>
            </div>
          ) : null}
        </dl>
      </Disclosure>
      {item.state === "open" ? (
        <div className="decision-form">
          <FormField id={`${id}-choice`} label={copy.reconciliation.decision}>
            <Select
              id={`${id}-choice`}
              disabled={busy}
              value={decision}
              onValueChange={(value) => {
                const next = decisions.find((item) => item === value);
                if (next) setDecision(next);
              }}
              options={decisions.map((value) => ({
                value,
                label: copy.reconciliationState[value],
              }))}
            />
          </FormField>
          <FormField
            id={`${id}-reason`}
            label={copy.reason}
            error={invalidReason ? copy.reasonRequired : undefined}
          >
            <Input
              aria-describedby={invalidReason ? `${id}-reason-error` : undefined}
              aria-invalid={invalidReason || undefined}
              disabled={busy}
              id={`${id}-reason`}
              maxLength={500}
              onChange={(event) => {
                setReason(event.target.value);
                setInvalidReason(false);
              }}
              value={reason}
            />
          </FormField>
          <Button disabled={busy || !recentlyReauthenticated} onClick={submit} variant="secondary">
            {copy.reconciliation.apply}
          </Button>
        </div>
      ) : null}
    </li>
  );
}

export function AccountingReconciliation({
  busy,
  cases,
  copy,
  locale,
  onDecide,
  recentlyReauthenticated,
}: {
  busy: boolean;
  cases: ReconciliationCase[];
  copy: AccountingCopy;
  locale: Locale;
  onDecide: (item: ReconciliationCase, state: ReconciliationDecision, reason: string) => void;
  recentlyReauthenticated: boolean;
}) {
  if (!cases.length) return <EmptyState title={copy.reconciliation.empty} />;
  return (
    <>
      <h3>{copy.reconciliation.title}</h3>
      <p>{copy.reconciliation.description}</p>
      <ResponsiveRecordList className="operations-card-list" label={copy.reconciliation.title}>
        {cases.map((item) => (
          <ReconciliationCard
            busy={busy}
            copy={copy}
            item={item}
            key={item.reconciliation_case_id}
            locale={locale}
            onDecide={onDecide}
            recentlyReauthenticated={recentlyReauthenticated}
          />
        ))}
      </ResponsiveRecordList>
    </>
  );
}
