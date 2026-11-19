import {
  Alert,
  Button,
  Disclosure,
  EmptyState,
  FieldError,
  FormField,
  Input,
  Pagination,
  ResponsiveRecordList,
  Select,
  Textarea,
} from "@nexora/ui/primitives";
import { useId, useState, type FormEvent } from "react";

import { WorkspaceTime } from "@/components/workspace-time";
import type { Locale } from "@/i18n/config";
import type { Dictionary } from "@/i18n/dictionaries";
import {
  accountingImportBody,
  maxImportBytes,
  type ImportBatch,
  type ImportFormat,
} from "@/lib/portfolio-accounting";
import { localizeDigits } from "@/lib/portfolio-analytics";

type AccountingCopy = Dictionary["portfolioOperations"];
const formats = { csv: "CSV", nexora_json: "Nexora JSON" };

function ImportRows({
  batch,
  copy,
  locale,
}: {
  batch: ImportBatch;
  copy: AccountingCopy;
  locale: Locale;
}) {
  const [page, setPage] = useState(1);
  const pageSize = 20;
  const pageCount = Math.ceil(batch.rows.length / pageSize);
  const currentPage = Math.min(page, pageCount);
  if (pageCount === 0) return null;
  return (
    <Disclosure className="import-preview accounting-disclosure" label={copy.imports.showRows}>
      {batch.rows.slice((currentPage - 1) * pageSize, currentPage * pageSize).map((row) => (
        <div className="import-row" key={row.import_row_id}>
          <div>
            <b>{localizeDigits(String(row.row_number), locale)}</b>
            <span className={`status-badge ${row.status}`}>{copy.importRowStatus[row.status]}</span>
            {row.reason_code ? (
              <span>
                {copy.importReasons[row.reason_code as keyof AccountingCopy["importReasons"]] ??
                  copy.importReasons.unknown}{" "}
                <code dir="ltr">{row.reason_code}</code>
              </span>
            ) : null}
          </div>
          {row.normalized_payload ? (
            <pre dir="ltr">{JSON.stringify(row.normalized_payload, null, 2)}</pre>
          ) : null}
        </div>
      ))}
      {pageCount > 1 ? (
        <Pagination
          currentPage={currentPage}
          label={copy.imports.rows}
          locale={locale}
          nextLabel={copy.imports.nextRows}
          onPageChange={setPage}
          previousLabel={copy.imports.previousRows}
          totalPages={pageCount}
        />
      ) : null}
    </Disclosure>
  );
}

function ImportBatchCard({
  batch,
  busy,
  copy,
  locale,
  onPublish,
  onReview,
  recentlyReauthenticated,
}: {
  batch: ImportBatch;
  busy: boolean;
  copy: AccountingCopy;
  locale: Locale;
  onPublish: (batch: ImportBatch) => void;
  onReview: (batch: ImportBatch, reason: string) => void;
  recentlyReauthenticated: boolean;
}) {
  const id = useId();
  const [reason, setReason] = useState("");
  const [invalidReason, setInvalidReason] = useState(false);
  const count = (value: number) => localizeDigits(String(value), locale);
  const blocked = batch.quarantined_count > 0;

  function review() {
    const entered = reason.trim();
    if (entered.length < 8 || entered.length > 500) {
      setInvalidReason(true);
      return;
    }
    onReview(batch, entered);
  }

  return (
    <li className="operation-card">
      <div className="operation-card-heading">
        <div>
          <span className={`status-badge ${batch.status}`}>{copy.importStatus[batch.status]}</span>
          <b>{formats[batch.source_format]}</b>
        </div>
        <WorkspaceTime dateTime={batch.created_at} locale={locale} />
      </div>
      <dl className="import-counts">
        <div>
          <dt>{copy.imports.rows}</dt>
          <dd>{count(batch.row_count)}</dd>
        </div>
        <div>
          <dt>{copy.imports.ready}</dt>
          <dd>{count(batch.ready_count)}</dd>
        </div>
        <div>
          <dt>{copy.imports.duplicates}</dt>
          <dd>{count(batch.duplicate_count)}</dd>
        </div>
        <div>
          <dt>{copy.imports.quarantined}</dt>
          <dd>{count(batch.quarantined_count)}</dd>
        </div>
      </dl>
      {blocked ? <Alert tone="warning">{copy.imports.quarantineHelp}</Alert> : null}
      <ImportRows batch={batch} copy={copy} locale={locale} />
      <Disclosure className="accounting-disclosure" label={copy.imports.evidence}>
        <dl className="accounting-evidence">
          <div>
            <dt>{copy.imports.batchId}</dt>
            <dd>
              <code dir="ltr">{batch.import_batch_id}</code>
            </dd>
          </div>
          <div>
            <dt>{copy.imports.checksum}</dt>
            <dd>
              <code dir="ltr">{batch.content_sha256}</code>
            </dd>
          </div>
          {batch.review_reason ? (
            <div>
              <dt>{copy.reason}</dt>
              <dd>{batch.review_reason}</dd>
            </div>
          ) : null}
          {batch.published_at ? (
            <div>
              <dt>{copy.imports.publishedAt}</dt>
              <dd>
                <WorkspaceTime dateTime={batch.published_at} locale={locale} />
              </dd>
            </div>
          ) : null}
        </dl>
      </Disclosure>
      {batch.status === "dry_run" && !blocked ? (
        <div className="bounded-action-form">
          <FormField
            id={id}
            label={copy.reason}
            error={invalidReason ? copy.reasonRequired : undefined}
          >
            <Input
              aria-describedby={invalidReason ? `${id}-error` : undefined}
              aria-invalid={invalidReason || undefined}
              disabled={busy}
              id={id}
              maxLength={500}
              onChange={(event) => {
                setReason(event.target.value);
                setInvalidReason(false);
              }}
              value={reason}
            />
          </FormField>
          <Button disabled={busy} onClick={review} variant="secondary">
            {copy.imports.review}
          </Button>
        </div>
      ) : null}
      {batch.status === "reviewed" && !blocked ? (
        <Button
          className="accounting-card-action"
          disabled={busy || !recentlyReauthenticated}
          onClick={() => onPublish(batch)}
          variant="secondary"
        >
          {copy.imports.publish}
        </Button>
      ) : null}
    </li>
  );
}

export function AccountingImports({
  busy,
  copy,
  imports,
  locale,
  onDryRun,
  onPublish,
  onReview,
  recentlyReauthenticated,
}: {
  busy: boolean;
  copy: AccountingCopy;
  imports: ImportBatch[];
  locale: Locale;
  onDryRun: (format: ImportFormat, content: string) => Promise<boolean>;
  onPublish: (batch: ImportBatch) => void;
  onReview: (batch: ImportBatch, reason: string) => void;
  recentlyReauthenticated: boolean;
}) {
  const id = useId();
  const [format, setFormat] = useState<ImportFormat>("csv");
  const [content, setContent] = useState("");
  const [fileName, setFileName] = useState("");
  const [reading, setReading] = useState(false);
  const [inputError, setInputError] = useState("");

  async function readFile(file: File) {
    const extension = file.name.toLowerCase().split(".").at(-1);
    setInputError("");
    if (extension !== "csv" && extension !== "json") {
      setInputError(copy.imports.fileTypeError);
      return;
    }
    if (file.size > maxImportBytes) {
      setInputError(copy.imports.sizeError);
      return;
    }
    setReading(true);
    try {
      const text = new TextDecoder("utf-8", { fatal: true }).decode(await file.arrayBuffer());
      setContent(text);
      setFileName(file.name);
      setFormat(extension === "csv" ? "csv" : "nexora_json");
    } catch {
      setInputError(copy.imports.fileReadError);
    } finally {
      setReading(false);
    }
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const source = content.replace(/^\uFEFF/, "");
    if (busy || reading || inputError || !source.trim()) return;
    const payload = JSON.stringify(accountingImportBody(format, source));
    if (new TextEncoder().encode(payload).byteLength > maxImportBytes) {
      setInputError(copy.imports.sizeError);
      return;
    }
    setInputError("");
    if (await onDryRun(format, source)) {
      setContent("");
      setFileName("");
    }
  }

  return (
    <>
      <h3>{copy.imports.title}</h3>
      <p>{copy.imports.description}</p>
      <Disclosure className="accounting-disclosure" label={copy.imports.formatHelp}>
        <dl className="accounting-evidence">
          <div>
            <dt>{copy.imports.csvHeader}</dt>
            <dd>
              <code dir="ltr">row_id,portfolio_id,transaction_kind,occurred_at,memo,legs</code>
            </dd>
          </div>
          <div>
            <dt>{copy.imports.jsonVersion}</dt>
            <dd>
              <code dir="ltr">nexora-transaction-import-v1</code>
            </dd>
          </div>
          <div>
            <dt>{copy.imports.legHelp}</dt>
            <dd>{copy.imports.legDescription}</dd>
          </div>
        </dl>
      </Disclosure>
      <form className="import-form" onSubmit={(event) => void submit(event)}>
        <FormField
          id={`${id}-file`}
          label={copy.imports.file}
          description={copy.imports.fileHelp}
          optionalLabel={copy.optional}
        >
          <Input
            accept=".csv,.json"
            aria-describedby={`${id}-file-description`}
            disabled={busy || reading}
            id={`${id}-file`}
            onChange={(event) => {
              const file = event.currentTarget.files?.[0];
              event.currentTarget.value = "";
              if (file) void readFile(file);
            }}
            type="file"
          />
        </FormField>
        {fileName ? (
          <p className="accounting-filename">
            <bdi>{fileName}</bdi>
          </p>
        ) : null}
        <FormField id={`${id}-format`} label={copy.imports.format}>
          <Select
            disabled={busy || reading}
            id={`${id}-format`}
            onValueChange={(value) => {
              if (value === "csv" || value === "nexora_json") {
                setFormat(value);
                setInputError("");
              }
            }}
            options={Object.entries(formats).map(([value, label]) => ({ value, label }))}
            value={format}
          />
        </FormField>
        <FormField id={`${id}-content`} label={copy.imports.content}>
          <Textarea
            disabled={busy || reading}
            id={`${id}-content`}
            maxLength={maxImportBytes}
            onChange={(event) => {
              setContent(event.target.value);
              setFileName("");
              setInputError("");
            }}
            placeholder={copy.imports.placeholder}
            required
            rows={8}
            value={content}
          />
        </FormField>
        <p>{copy.imports.dryRunNotice}</p>
        {inputError ? <FieldError>{inputError}</FieldError> : null}
        <Button disabled={busy || reading || !!inputError || !content.trim()} type="submit">
          {copy.imports.preview}
        </Button>
      </form>
      {imports.length ? (
        <ResponsiveRecordList className="operations-card-list" label={copy.imports.title}>
          {imports.map((batch) => (
            <ImportBatchCard
              batch={batch}
              busy={busy}
              copy={copy}
              key={batch.import_batch_id}
              locale={locale}
              onPublish={onPublish}
              onReview={onReview}
              recentlyReauthenticated={recentlyReauthenticated}
            />
          ))}
        </ResponsiveRecordList>
      ) : (
        <EmptyState className="operations-card-list" title={copy.imports.empty} />
      )}
    </>
  );
}
