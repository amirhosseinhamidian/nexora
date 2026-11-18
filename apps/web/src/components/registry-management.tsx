"use client";

import {
  Alert,
  Button,
  ConfirmationDialog,
  EmptyState,
  ErrorState,
  FilterBar,
  FormField,
  IconButton,
  Modal,
  SearchInput,
  Spinner,
  ToastRegion,
} from "@nexora/ui/primitives";
import Link from "next/link";
import { useEffect, useId, useRef, useState } from "react";

import {
  AssetIdentifierForm,
  RegistryCreateForm,
  RegistrySelectField,
  registryOptions,
} from "@/components/registry-forms";
import { RegistryRecordList } from "@/components/registry-record-list";
import type { Locale } from "@/i18n/config";
import type { Dictionary } from "@/i18n/dictionaries";
import { ApiRequestError } from "@/lib/api-client";
import {
  addAssetIdentifier,
  changeRegistryLifecycle,
  createRegistryRecord,
  loadRegistry,
  type AssetIdentifierInput,
  type RegistryAsset,
  type RegistryCreation,
  type RegistryRecord,
  type RegistrySection,
  type RegistrySnapshot,
} from "@/lib/portfolio-registry";

type RegistryDialog =
  | { kind: "create" }
  | { kind: "lifecycle"; target: RegistryRecord }
  | { kind: "identifier"; target: RegistryAsset };
const terminalStatus = { assets: "inactive", portfolios: "archived", accounts: "closed" } as const;

function creationPrerequisite(
  section: RegistrySection,
  snapshot: RegistrySnapshot,
  dictionary: Dictionary,
  locale: Locale,
): { href: string; label: string; description?: string } | undefined {
  const copy = dictionary.registry;
  if (section === "portfolios") {
    if (snapshot.portfolios.length === 0) {
      return { href: `/${locale}/onboarding`, label: dictionary.onboarding.start };
    }
    if (!snapshot.assets.some((asset) => asset.status === "active")) {
      return { href: `/${locale}/assets`, label: copy.goToAssets, description: copy.needsAsset };
    }
  }
  if (
    section === "accounts" &&
    !snapshot.portfolios.some((portfolio) => portfolio.status === "active")
  ) {
    return {
      href: `/${locale}/portfolios`,
      label: copy.goToPortfolios,
      description: copy.needsPortfolio,
    };
  }
}

export function RegistryManagement({
  dictionary,
  locale,
  section,
}: {
  dictionary: Dictionary;
  locale: Locale;
  section: RegistrySection;
}) {
  const id = useId();
  const copy = dictionary.registry;
  const sectionCopy = copy[section];
  const request = useRef<AbortController | null>(null);
  const creation = useRef<{ input: string; key: string } | null>(null);
  const [snapshot, setSnapshot] = useState<RegistrySnapshot>();
  const [revision, setRevision] = useState(0);
  const [loadFailed, setLoadFailed] = useState(false);
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("");
  const [portfolio, setPortfolio] = useState("");
  const [dialog, setDialog] = useState<RegistryDialog>();
  const [busy, setBusy] = useState(false);
  const [issue, setIssue] = useState("");
  const [notice, setNotice] = useState<{ title: string; tone: "success" | "danger" | "warning" }>();

  useEffect(() => {
    const controller = new AbortController();
    void loadRegistry(section, controller.signal).then(
      (loaded) => {
        if (!controller.signal.aborted) setSnapshot(loaded);
      },
      () => {
        if (!controller.signal.aborted) setLoadFailed(true);
      },
    );
    return () => controller.abort();
  }, [section, revision]);

  useEffect(() => () => request.current?.abort(), []);

  useEffect(() => {
    if (notice?.tone !== "success") return;
    const timer = window.setTimeout(() => setNotice(undefined), 6000);
    return () => window.clearTimeout(timer);
  }, [notice]);

  function refresh() {
    setSnapshot(undefined);
    setLoadFailed(false);
    setRevision((current) => current + 1);
  }

  function openDialog(next: RegistryDialog) {
    setIssue("");
    setNotice(undefined);
    setDialog(next);
  }

  function dismissDialog() {
    if (request.current) return;
    setIssue("");
    setDialog(undefined);
  }

  async function save(
    kind: RegistryDialog["kind"],
    perform: (signal: AbortSignal) => Promise<unknown>,
  ) {
    if (request.current) return;
    const controller = new AbortController();
    request.current = controller;
    setBusy(true);
    setIssue("");
    setNotice(undefined);
    if (kind === "lifecycle") setDialog(undefined);
    try {
      await perform(controller.signal);
      if (controller.signal.aborted) return;
      setDialog(undefined);
      if (kind === "create") {
        creation.current = null;
        setStatus("");
        setQuery("");
        setPortfolio("");
        setNotice({ title: sectionCopy.created, tone: "success" });
      } else {
        setNotice({
          title: kind === "identifier" ? copy.identifierSaved : sectionCopy.changed,
          tone: "success",
        });
      }
      if (kind !== "identifier") refresh();
    } catch (error) {
      if (controller.signal.aborted) return;
      const statusCode = error instanceof ApiRequestError ? error.status : undefined;
      if (kind === "lifecycle") {
        const stale = statusCode === 409 || statusCode === 404;
        setNotice({
          title: stale ? copy.stale : copy.actionUnconfirmed,
          tone: stale ? "warning" : "danger",
        });
        refresh();
      } else if (statusCode === 409) {
        setIssue(kind === "identifier" ? copy.identifierConflict : copy.createConflict);
      } else {
        setIssue(statusCode === 404 ? copy.parentUnavailable : copy.saveFailed);
      }
    } finally {
      request.current = null;
      if (!controller.signal.aborted) setBusy(false);
    }
  }

  function create(input: RegistryCreation) {
    if (request.current) return;
    const signature = JSON.stringify(input);
    if (creation.current?.input !== signature) {
      creation.current = { input: signature, key: `web-${crypto.randomUUID()}` };
    }
    const { key } = creation.current;
    void save("create", (signal) => createRegistryRecord(input, key, signal));
  }

  function registerIdentifier(asset: RegistryAsset, input: AssetIdentifierInput) {
    void save("identifier", (signal) => addAssetIdentifier(asset.asset_id, input, signal));
  }

  const records = snapshot?.[section] ?? [];
  const text = query.trim().toLocaleLowerCase(locale);
  const visible = records.filter((record) => {
    const nameMatches = record.name.toLocaleLowerCase(locale).includes(text);
    const symbolMatches =
      "symbol" in record && record.symbol.toLocaleLowerCase(locale).includes(text);
    return (
      (nameMatches || symbolMatches) &&
      (!status || record.status === status) &&
      (!portfolio || ("account_id" in record && record.portfolio_id === portfolio))
    );
  });
  const prerequisites = snapshot
    ? creationPrerequisite(section, snapshot, dictionary, locale)
    : undefined;
  const prerequisiteLink = prerequisites ? (
    <Link className="nx-button nx-button--secondary nx-control--md" href={prerequisites.href}>
      {prerequisites.label}
    </Link>
  ) : undefined;

  return (
    <section aria-label={sectionCopy.listLabel} className="registry-management">
      <header className="registry-toolbar">
        <p>{sectionCopy.description}</p>
        {snapshot && !prerequisites ? (
          <Button disabled={busy} onClick={() => openDialog({ kind: "create" })}>
            {sectionCopy.create}
          </Button>
        ) : null}
      </header>
      <ToastRegion
        label={copy.notifications}
        messages={
          notice
            ? [
                {
                  ...notice,
                  id: "registry-notice",
                  action: (
                    <IconButton
                      aria-label={copy.dismissNotification}
                      onClick={() => setNotice(undefined)}
                      size="sm"
                    >
                      <span aria-hidden="true">×</span>
                    </IconButton>
                  ),
                },
              ]
            : []
        }
      />
      {busy && !dialog ? <Spinner label={copy.saving} /> : null}
      {loadFailed ? (
        <ErrorState
          action={
            <Button onClick={refresh} variant="secondary">
              {copy.retry}
            </Button>
          }
          title={copy.loadErrorTitle}
        >
          {copy.loadErrorDescription}
        </ErrorState>
      ) : !snapshot ? (
        <Spinner label={copy.loading} />
      ) : (
        <>
          {prerequisites?.description && records.length > 0 ? (
            <Alert tone="info">
              <p>{prerequisites.description}</p>
              {prerequisiteLink}
            </Alert>
          ) : null}
          {records.length === 0 ? (
            <EmptyState action={prerequisiteLink} title={sectionCopy.emptyTitle}>
              {prerequisites?.description ?? sectionCopy.emptyDescription}
            </EmptyState>
          ) : (
            <>
              <FilterBar label={copy.filters}>
                <FormField id={`${id}-query`} label={copy.search}>
                  <SearchInput
                    id={`${id}-query`}
                    onChange={(event) => setQuery(event.target.value)}
                    value={query}
                  />
                </FormField>
                <RegistrySelectField
                  id={`${id}-status`}
                  label={copy.status}
                  onValueChange={setStatus}
                  options={[
                    { value: "", label: copy.allStatuses },
                    ...registryOptions(["active", terminalStatus[section]], copy.statuses),
                  ]}
                  value={status}
                />
                {section === "accounts" ? (
                  <RegistrySelectField
                    id={`${id}-portfolio`}
                    label={copy.portfolio}
                    onValueChange={setPortfolio}
                    options={[
                      { value: "", label: copy.allPortfolios },
                      ...snapshot.portfolios.map(({ portfolio_id, name }) => ({
                        value: portfolio_id,
                        label: name,
                      })),
                    ]}
                    value={portfolio}
                  />
                ) : null}
              </FilterBar>
              {visible.length ? (
                <RegistryRecordList
                  busy={busy}
                  dictionary={dictionary}
                  locale={locale}
                  onAddIdentifier={(target) => openDialog({ kind: "identifier", target })}
                  onLifecycle={(target) => openDialog({ kind: "lifecycle", target })}
                  records={visible}
                  section={section}
                  snapshot={snapshot}
                />
              ) : (
                <EmptyState title={copy.noMatches}>{copy.noMatchesDescription}</EmptyState>
              )}
            </>
          )}
        </>
      )}
      {dialog?.kind === "create" && snapshot ? (
        <Modal closeLabel={copy.cancel} onClose={dismissDialog} open title={sectionCopy.create}>
          {issue ? <Alert tone="danger">{issue}</Alert> : null}
          <RegistryCreateForm
            busy={busy}
            dictionary={dictionary}
            onCreate={create}
            section={section}
            snapshot={snapshot}
          />
        </Modal>
      ) : null}
      {dialog?.kind === "identifier" ? (
        <Modal
          closeLabel={copy.cancel}
          description={<bdi>{dialog.target.name}</bdi>}
          onClose={dismissDialog}
          open
          title={copy.addIdentifier}
        >
          {issue ? <Alert tone="danger">{issue}</Alert> : null}
          <AssetIdentifierForm
            busy={busy}
            copy={copy}
            onSave={(input) => registerIdentifier(dialog.target, input)}
          />
        </Modal>
      ) : null}
      {dialog?.kind === "lifecycle" ? (
        <ConfirmationDialog
          cancelLabel={copy.cancel}
          confirmLabel={sectionCopy.action}
          description={
            <>
              <bdi>{dialog.target.name}</bdi>
              <br />
              {sectionCopy.confirmDescription}
            </>
          }
          destructive
          onCancel={dismissDialog}
          onConfirm={() =>
            void save("lifecycle", (signal) => changeRegistryLifecycle(dialog.target, signal))
          }
          open
          title={sectionCopy.confirmTitle}
        />
      ) : null}
    </section>
  );
}
