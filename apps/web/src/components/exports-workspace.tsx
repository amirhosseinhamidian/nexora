"use client";

import {
  Alert,
  Button,
  Checkbox,
  ConfirmationDialog,
  FieldError,
  FormField,
  IconButton,
  Select,
  ToastRegion,
} from "@nexora/ui/primitives";
import { useEffect, useId, useRef, useState } from "react";

import { useWorkspace } from "@/components/authenticated-shell";
import { ExportHistory, type ExportStatus } from "@/components/export-history";
import { ApiRequestError, downloadExport } from "@/lib/api-client";
import {
  createPortfolioExport,
  exportFormats,
  exportProfiles,
  readExportHistory,
  rememberExport,
  type ExportFormat,
  type ExportProfile,
  type ExportReceipt,
  type ExportRequest,
} from "@/lib/portfolio-exports";

export function ExportsWorkspace() {
  const { dictionary, locale, session } = useWorkspace();
  const ownerId = session.owner_id;
  const copy = dictionary.exports;
  const id = useId();
  const request = useRef<AbortController | null>(null);
  const [history, setHistory] = useState(() => readExportHistory(ownerId));
  const [profile, setProfile] = useState<ExportProfile>("ai_safe");
  const [formats, setFormats] = useState<ExportFormat[]>(["json"]);
  const [pinned, setPinned] = useState(false);
  const [confirmation, setConfirmation] = useState<ExportRequest>();
  const [operation, setOperation] = useState<"creating" | "verifying" | "downloading">();
  const [notice, setNotice] = useState<{ title: string; tone: "success" | "warning" | "danger" }>();
  const [statuses, setStatuses] = useState<Record<string, ExportStatus>>({});
  const [formatError, setFormatError] = useState(false);

  useEffect(() => () => request.current?.abort(), []);

  async function create(options: ExportRequest) {
    if (request.current) return;
    const controller = new AbortController();
    request.current = controller;
    setConfirmation(undefined);
    setOperation("creating");
    setNotice(undefined);
    try {
      const receipt = await createPortfolioExport(options, controller.signal);
      if (controller.signal.aborted) return;
      const saved = rememberExport(ownerId, receipt, history);
      setHistory(saved.history);
      setNotice(
        saved.persisted
          ? { title: copy.created, tone: "success" }
          : { title: copy.historyUnavailable, tone: "warning" },
      );
    } catch (error) {
      if (controller.signal.aborted) return;
      const capacity =
        error instanceof ApiRequestError &&
        (error.code === "PORTFOLIO_EXPORT_CAPACITY_EXCEEDED" ||
          error.code === "ARTIFACT_STORAGE_CAPACITY_EXCEEDED");
      setNotice({ title: capacity ? copy.capacity : copy.createFailed, tone: "danger" });
    } finally {
      request.current = null;
      if (!controller.signal.aborted) setOperation(undefined);
    }
  }

  async function check(receipt: ExportReceipt, save: boolean) {
    if (request.current) return;
    const controller = new AbortController();
    request.current = controller;
    setOperation(save ? "downloading" : "verifying");
    setNotice(undefined);
    try {
      await downloadExport("portfolio-export", receipt.id, receipt.version, {
        expected: { sha256: receipt.sha256, sizeBytes: receipt.sizeBytes },
        save,
        signal: controller.signal,
      });
      if (controller.signal.aborted) return;
      setStatuses((current) => ({ ...current, [receipt.id]: "verified" }));
      setNotice({ title: save ? copy.downloadStarted : copy.verified, tone: "success" });
    } catch (error) {
      if (controller.signal.aborted) return;
      const status = error instanceof ApiRequestError ? error.status : undefined;
      const failed =
        status === 404 ? "unavailable" : status === 409 ? "integrityFailed" : "checkFailed";
      setStatuses((current) => ({ ...current, [receipt.id]: failed }));
      setNotice({ title: copy.statuses[failed], tone: "danger" });
    } finally {
      request.current = null;
      if (!controller.signal.aborted) setOperation(undefined);
    }
  }

  return (
    <div className="settings-workspace">
      <ToastRegion
        label={copy.notifications}
        messages={
          notice
            ? [
                {
                  ...notice,
                  id: "export-operation",
                  action: (
                    <IconButton aria-label={copy.dismiss} onClick={() => setNotice(undefined)}>
                      <span aria-hidden="true">×</span>
                    </IconButton>
                  ),
                },
              ]
            : []
        }
      />
      {operation ? <Alert role="status">{copy.operations[operation]}</Alert> : null}
      <section className="settings-card" aria-labelledby={`${id}-title`}>
        <h2 id={`${id}-title`}>{copy.createTitle}</h2>
        <p>{copy.createDescription}</p>
        <form
          className="export-form"
          onSubmit={(event) => {
            event.preventDefault();
            if (operation || request.current) return;
            if (!formats.length) {
              setFormatError(true);
              return;
            }
            setConfirmation({
              profile,
              formats: exportFormats.filter((format) => formats.includes(format)),
              pinned,
            });
          }}
        >
          <FormField
            id={`${id}-profile`}
            label={copy.profile}
            description={copy.profileDescriptions[profile]}
          >
            <Select
              aria-describedby={`${id}-profile-description`}
              disabled={!!operation}
              id={`${id}-profile`}
              options={exportProfiles.map((value) => ({ value, label: copy.profiles[value] }))}
              value={profile}
              onValueChange={(value) => {
                if (value === "ai_safe" || value === "private_complete") setProfile(value);
              }}
            />
          </FormField>
          <fieldset
            className="export-format-options"
            disabled={!!operation}
            aria-describedby={formatError ? `${id}-formats-error` : undefined}
          >
            <legend>{copy.formatsTitle}</legend>
            {exportFormats.map((format) => (
              <Checkbox
                checked={formats.includes(format)}
                key={format}
                onChange={(event) => {
                  const checked = event.target.checked;
                  setFormatError(false);
                  setFormats((current) =>
                    checked ? [...current, format] : current.filter((item) => item !== format),
                  );
                }}
              >
                {copy.formats[format]}
              </Checkbox>
            ))}
            {formatError ? (
              <FieldError id={`${id}-formats-error`}>{copy.formatRequired}</FieldError>
            ) : null}
          </fieldset>
          <div>
            <Checkbox
              checked={pinned}
              disabled={!!operation}
              aria-describedby={`${id}-retention`}
              onChange={(event) => setPinned(event.target.checked)}
            >
              {copy.pin}
            </Checkbox>
            <p id={`${id}-retention`}>{copy.retentionHint}</p>
          </div>
          <Button disabled={!!operation} type="submit">
            {copy.create}
          </Button>
        </form>
      </section>
      <ExportHistory
        busy={!!operation}
        copy={copy}
        history={history}
        locale={locale}
        onCheck={(receipt, save) => void check(receipt, save)}
        statuses={statuses}
      />
      {confirmation ? (
        <ConfirmationDialog
          cancelLabel={copy.cancel}
          confirmLabel={copy.create}
          description={
            <>
              {copy.profiles[confirmation.profile]} ·{" "}
              {confirmation.formats.map((format) => copy.formats[format]).join(" · ")}
              <br />
              {copy.profileDescriptions[confirmation.profile]}
              <br />
              {confirmation.pinned ? copy.pinned : copy.standardRetention}
            </>
          }
          onCancel={() => setConfirmation(undefined)}
          onConfirm={() => void create(confirmation)}
          open
          title={copy.confirmCreate}
        />
      ) : null}
    </div>
  );
}
