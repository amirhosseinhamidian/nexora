import { Button, Disclosure, EmptyState, ResponsiveRecordList } from "@nexora/ui/primitives";

import { WorkspaceTime } from "@/components/workspace-time";
import type { Locale } from "@/i18n/config";
import type { Dictionary } from "@/i18n/dictionaries";
import type { ExportReceipt } from "@/lib/portfolio-exports";

export type ExportStatus = "ready" | "verified" | "unavailable" | "integrityFailed" | "checkFailed";

export function ExportHistory({
  busy,
  copy,
  history,
  locale,
  onCheck,
  statuses,
}: {
  busy: boolean;
  copy: Dictionary["exports"];
  history: ExportReceipt[];
  locale: Locale;
  onCheck: (receipt: ExportReceipt, save: boolean) => void;
  statuses: Record<string, ExportStatus>;
}) {
  const numbers = new Intl.NumberFormat(locale === "fa" ? "fa-IR" : "en-GB");
  return (
    <section className="settings-card export-history" aria-label={copy.history}>
      <h2>{copy.history}</h2>
      <p>{copy.historyScope}</p>
      {history.length ? (
        <ResponsiveRecordList className="export-records" label={copy.history}>
          {history.map((item) => {
            const status = statuses[item.id] ?? "ready";
            return (
              <li className="export-record" key={item.id}>
                <div className="export-record-heading">
                  <div>
                    <h3>{copy.profiles[item.profile]}</h3>
                    <WorkspaceTime dateTime={item.generatedAt} locale={locale} />
                  </div>
                  <span className={`evidence-state export-status-${status}`}>
                    {copy.statuses[status]}
                  </span>
                </div>
                <dl className="export-record-info">
                  <div>
                    <dt>{copy.formatsTitle}</dt>
                    <dd>{item.formats.map((format) => copy.formats[format]).join(" · ")}</dd>
                  </div>
                  <div>
                    <dt>{copy.bundleSize}</dt>
                    <dd>
                      {numbers.format(item.sizeBytes)} {copy.bytes}
                    </dd>
                  </div>
                  <div>
                    <dt>{copy.records}</dt>
                    <dd>{numbers.format(item.recordCount)}</dd>
                  </div>
                  <div>
                    <dt>{copy.retention}</dt>
                    <dd>{item.pinned ? copy.pinned : copy.standardRetention}</dd>
                  </div>
                </dl>
                <Disclosure className="accounting-disclosure" label={copy.receiptDetails}>
                  <dl className="accounting-evidence">
                    <div>
                      <dt>{copy.exportId}</dt>
                      <dd>
                        <code dir="ltr">{item.id}</code>
                      </dd>
                    </div>
                    <div>
                      <dt>{copy.version}</dt>
                      <dd>
                        <code dir="ltr">{item.version}</code>
                      </dd>
                    </div>
                    <div>
                      <dt>{copy.bundleChecksum}</dt>
                      <dd>
                        <code dir="ltr">{item.sha256}</code>
                      </dd>
                    </div>
                    <div>
                      <dt>{copy.snapshotChecksum}</dt>
                      <dd>
                        <code dir="ltr">{item.snapshotSha256}</code>
                      </dd>
                    </div>
                  </dl>
                </Disclosure>
                <div className="monitoring-links">
                  <Button disabled={busy} onClick={() => onCheck(item, false)} variant="secondary">
                    {copy.verify}
                  </Button>
                  <Button disabled={busy} onClick={() => onCheck(item, true)}>
                    {copy.download}
                  </Button>
                </div>
              </li>
            );
          })}
        </ResponsiveRecordList>
      ) : (
        <EmptyState title={copy.empty} />
      )}
    </section>
  );
}
