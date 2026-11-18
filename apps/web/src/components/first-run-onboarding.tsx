"use client";

import {
  Alert,
  Button,
  Checkbox,
  ConfirmationDialog,
  FormField,
  Input,
  Select,
  Spinner,
  ToastRegion,
} from "@nexora/ui/primitives";
import Link from "next/link";
import { type FormEvent, useEffect, useRef, useState } from "react";

import type { Locale } from "@/i18n/config";
import type { Dictionary } from "@/i18n/dictionaries";
import { ApiRequestError } from "@/lib/api-client";
import {
  accountKinds,
  assetClasses,
  canResumePortfolio,
  completeOnboarding,
  loadSetupRegistry,
  type OnboardingDraft,
  OnboardingError,
  portfolioKinds,
  readOnboardingDraft,
  type SetupAsset,
  type SetupPortfolio,
  validSetupStep,
  writeOnboardingDraft,
} from "@/lib/first-run-onboarding";

type Copy = Dictionary["onboarding"];
type Registry = Awaited<ReturnType<typeof loadSetupRegistry>>;
type Failure = keyof Copy["errors"];

function AssetFields({
  assets,
  copy,
  draft,
  update,
}: {
  assets: SetupAsset[];
  copy: Copy;
  draft: OnboardingDraft;
  update: (changes: Partial<OnboardingDraft>) => void;
}) {
  return (
    <fieldset
      className="onboarding-fields"
      disabled={Boolean(draft.savedAssetId || draft.savedPortfolioId)}
    >
      {assets.length ? (
        <FormField id="setup-asset-mode" label={copy.assetMode}>
          <Select
            id="setup-asset-mode"
            value={draft.assetMode}
            onValueChange={(value) =>
              update({ assetMode: value === "existing" ? "existing" : "new" })
            }
            options={[
              { value: "existing", label: copy.useExisting },
              { value: "new", label: copy.createAsset },
            ]}
          />
        </FormField>
      ) : null}
      {draft.assetMode === "existing" ? (
        <FormField id="setup-asset" label={copy.baseAsset}>
          <Select
            id="setup-asset"
            aria-required="true"
            value={draft.selectedAssetId}
            onValueChange={(value) => update({ selectedAssetId: value })}
            options={[
              { value: "", label: copy.chooseAsset },
              ...assets.map((asset) => ({
                value: asset.asset_id,
                label: `${asset.name} (${asset.symbol})`,
              })),
            ]}
          />
        </FormField>
      ) : (
        <>
          <FormField id="setup-asset-name" label={copy.assetName}>
            <Input
              id="setup-asset-name"
              maxLength={120}
              required
              value={draft.assetName}
              onChange={(event) => update({ assetName: event.target.value })}
            />
          </FormField>
          <FormField description={copy.symbolHelp} id="setup-symbol" label={copy.symbol}>
            <Input
              aria-describedby="setup-symbol-description"
              dir="ltr"
              id="setup-symbol"
              maxLength={24}
              required
              value={draft.assetSymbol}
              onChange={(event) => update({ assetSymbol: event.target.value.toUpperCase() })}
            />
          </FormField>
          <FormField id="setup-asset-class" label={copy.assetClass}>
            <Select
              id="setup-asset-class"
              value={draft.assetClass}
              onValueChange={(value) =>
                update({ assetClass: value as OnboardingDraft["assetClass"] })
              }
              options={assetClasses.map((item) => ({
                value: item,
                label: copy.assetClasses[item],
              }))}
            />
          </FormField>
          <FormField id="setup-precision" label={copy.precision}>
            <Input
              dir="ltr"
              id="setup-precision"
              min={0}
              max={30}
              required
              step={1}
              type="number"
              value={draft.assetPrecision}
              onChange={(event) => update({ assetPrecision: event.target.value })}
            />
          </FormField>
        </>
      )}
    </fieldset>
  );
}

function Review({
  assets,
  copy,
  draft,
}: {
  assets: SetupAsset[];
  copy: Copy;
  draft: OnboardingDraft;
}) {
  const existing = assets.find((asset) => asset.asset_id === draft.selectedAssetId);
  return (
    <dl className="onboarding-review">
      <div>
        <dt>{copy.baseAsset}</dt>
        <dd>
          {draft.assetMode === "existing" ? existing?.name : draft.assetName.trim()}{" "}
          <bdi>{draft.assetMode === "existing" ? existing?.symbol : draft.assetSymbol.trim()}</bdi>
          {draft.assetMode === "new" ? (
            <div>
              {copy.assetClasses[draft.assetClass]} · {copy.precision}{" "}
              <bdi>{draft.assetPrecision}</bdi>
            </div>
          ) : null}
        </dd>
      </div>
      <div>
        <dt>{copy.portfolioName}</dt>
        <dd>
          {draft.portfolioName.trim()} · {copy.portfolioKinds[draft.portfolioKind]}
        </dd>
      </div>
      <div>
        <dt>{copy.accountName}</dt>
        <dd>
          {draft.addAccount
            ? `${draft.accountName.trim()} · ${copy.accountKinds[draft.accountKind]}`
            : copy.noAccount}
        </dd>
      </div>
    </dl>
  );
}

export function FirstRunOnboarding({
  copy,
  locale,
  ownerId,
}: {
  copy: Copy;
  locale: Locale;
  ownerId: string;
}) {
  const [registry, setRegistry] = useState<Registry>();
  const [draft, setDraft] = useState<OnboardingDraft>();
  const [completed, setCompleted] = useState<SetupPortfolio>();
  const [attempt, setAttempt] = useState(0);
  const [loadFailed, setLoadFailed] = useState(false);
  const [storageFailed, setStorageFailed] = useState(false);
  const [failure, setFailure] = useState<Failure>();
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const request = useRef<AbortController | null>(null);
  const heading = useRef<HTMLHeadingElement>(null);
  const step = draft?.step;

  useEffect(() => {
    const controller = new AbortController();
    void loadSetupRegistry(controller.signal).then(
      (loaded) => {
        if (controller.signal.aborted) return;
        const saved = readOnboardingDraft(ownerId, loaded.assets);
        if (
          !saved.started &&
          saved.assetMode === "existing" &&
          !loaded.assets.some((item) => item.asset_id === saved.selectedAssetId)
        ) {
          saved.selectedAssetId = loaded.assets[0]?.asset_id ?? "";
          saved.assetMode = loaded.assets.length ? "existing" : "new";
          saved.step = 0;
        }
        setDraft(saved);
        setRegistry(loaded);
      },
      () => {
        if (!controller.signal.aborted) setLoadFailed(true);
      },
    );
    return () => {
      controller.abort();
      request.current?.abort();
    };
  }, [attempt, ownerId]);

  useEffect(() => {
    if (step !== undefined) heading.current?.focus();
  }, [step, completed]);

  function store(next: OnboardingDraft) {
    setStorageFailed(!writeOnboardingDraft(ownerId, next));
    setDraft(next);
  }

  if (loadFailed) {
    return (
      <Alert title={copy.loadError} tone="danger">
        <Button
          onClick={() => {
            setLoadFailed(false);
            setAttempt((current) => current + 1);
          }}
          variant="secondary"
        >
          {copy.retry}
        </Button>
      </Alert>
    );
  }
  if (!registry || !draft) return <Spinner label={copy.loading} />;

  const assets = registry.assets;
  const existing =
    registry.portfolios.find((item) => item.status === "active") ?? registry.portfolios[0];
  const resumable = registry.portfolios.some((item) => canResumePortfolio(draft, item));
  const portfolioHref = (id: string) => `/${locale}/portfolios/${encodeURIComponent(id)}`;

  if (completed) {
    return (
      <section className="onboarding-card" aria-labelledby="onboarding-done">
        <h2 id="onboarding-done" ref={heading} tabIndex={-1}>
          {copy.doneTitle}
        </h2>
        <p>{copy.doneDescription}</p>
        <Link className="primary-button" href={portfolioHref(completed.portfolio_id)}>
          {copy.openPortfolio}
        </Link>
        <ToastRegion
          label={copy.notifications}
          messages={[{ id: "setup-done", title: copy.doneTitle, tone: "success" }]}
        />
      </section>
    );
  }

  if ((existing && !resumable) || failure === "existingPortfolio") {
    return (
      <section className="onboarding-card" aria-labelledby="onboarding-existing">
        <h2 id="onboarding-existing" ref={heading} tabIndex={-1}>
          {copy.existingTitle}
        </h2>
        <p>{copy.errors.existingPortfolio}</p>
        <Link
          className="secondary-button"
          href={existing ? portfolioHref(existing.portfolio_id) : `/${locale}/portfolios`}
        >
          {copy.openPortfolios}
        </Link>
      </section>
    );
  }

  function update(changes: Partial<OnboardingDraft>) {
    if (!draft) return;
    setFailure(undefined);
    store({ ...draft, ...changes });
  }

  function next(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!draft || request.current) return;
    if (draft.step === 3) {
      setConfirming(true);
    } else if (validSetupStep(draft, assets, draft.step)) {
      update({ step: draft.step + 1 });
    } else {
      setFailure("invalid");
    }
  }

  async function submit() {
    if (!draft || request.current) return;
    const controller = new AbortController();
    request.current = controller;
    let checkpoint = { ...draft, started: true };
    setConfirming(false);
    setBusy(true);
    setFailure(undefined);
    store(checkpoint);
    try {
      const portfolio = await completeOnboarding(checkpoint, controller.signal, (saved) => {
        checkpoint = saved;
        store(saved);
      });
      writeOnboardingDraft(ownerId, undefined);
      setCompleted(portfolio);
    } catch (error) {
      if (controller.signal.aborted) return;
      const problem = error instanceof OnboardingError ? error.problem : undefined;
      const status = error instanceof ApiRequestError ? error.status : undefined;
      const editable =
        problem !== undefined ||
        status === 400 ||
        status === 404 ||
        status === 409 ||
        status === 422;
      if (editable) {
        if (problem === "assetUnavailable" && !checkpoint.savedPortfolioId) {
          checkpoint = { ...checkpoint, savedAssetId: "", id: crypto.randomUUID(), step: 0 };
          setRegistry(undefined);
          setAttempt((current) => current + 1);
        }
        store({ ...checkpoint, started: false });
      }
      setFailure(problem ?? (status === 409 ? "conflict" : editable ? "invalid" : "retry"));
    } finally {
      request.current = null;
      if (!controller.signal.aborted) setBusy(false);
    }
  }

  return (
    <section className="onboarding-card" aria-labelledby="onboarding-step">
      <p>{copy.intro}</p>
      <ol aria-label={copy.stepsLabel} className="onboarding-steps">
        {copy.steps.map((label, index) => (
          <li aria-current={index === draft.step ? "step" : undefined} key={label}>
            {label}
          </li>
        ))}
      </ol>
      <h2 id="onboarding-step" ref={heading} tabIndex={-1}>
        {copy.steps[draft.step]}
      </h2>
      {failure ? <Alert tone="danger">{copy.errors[failure]}</Alert> : null}
      {storageFailed ? <Alert tone="warning">{copy.storageWarning}</Alert> : null}
      {draft.started && !busy && !failure ? <Alert tone="info">{copy.resume}</Alert> : null}
      <form className="onboarding-form" onSubmit={next}>
        {draft.step === 0 ? (
          <AssetFields assets={assets} copy={copy} draft={draft} update={update} />
        ) : null}
        {draft.step === 1 ? (
          <fieldset className="onboarding-fields" disabled={Boolean(draft.savedPortfolioId)}>
            <FormField id="setup-portfolio-name" label={copy.portfolioName}>
              <Input
                id="setup-portfolio-name"
                required
                maxLength={120}
                value={draft.portfolioName}
                onChange={(event) => update({ portfolioName: event.target.value })}
              />
            </FormField>
            <FormField id="setup-portfolio-kind" label={copy.portfolioKind}>
              <Select
                id="setup-portfolio-kind"
                value={draft.portfolioKind}
                onValueChange={(value) =>
                  update({ portfolioKind: value as OnboardingDraft["portfolioKind"] })
                }
                options={portfolioKinds.map((item) => ({
                  value: item,
                  label: copy.portfolioKinds[item],
                }))}
              />
            </FormField>
          </fieldset>
        ) : null}
        {draft.step === 2 ? (
          <fieldset className="onboarding-fields">
            <Checkbox
              checked={draft.addAccount}
              onChange={(event) => update({ addAccount: event.target.checked })}
            >
              {copy.addAccount}
            </Checkbox>
            {draft.addAccount ? (
              <>
                <FormField id="setup-account-name" label={copy.accountName}>
                  <Input
                    id="setup-account-name"
                    required
                    maxLength={120}
                    value={draft.accountName}
                    onChange={(event) => update({ accountName: event.target.value })}
                  />
                </FormField>
                <FormField id="setup-account-kind" label={copy.accountKind}>
                  <Select
                    id="setup-account-kind"
                    value={draft.accountKind}
                    onValueChange={(value) =>
                      update({ accountKind: value as OnboardingDraft["accountKind"] })
                    }
                    options={accountKinds.map((item) => ({
                      value: item,
                      label: copy.accountKinds[item],
                    }))}
                  />
                </FormField>
                <p>{copy.accountHelp}</p>
              </>
            ) : null}
          </fieldset>
        ) : null}
        {draft.step === 3 ? <Review assets={assets} copy={copy} draft={draft} /> : null}
        <div className="onboarding-actions">
          {draft.step > 0 && !draft.started ? (
            <Button onClick={() => update({ step: draft.step - 1 })} variant="secondary">
              {copy.back}
            </Button>
          ) : null}
          <Button loading={busy} type="submit">
            {draft.step < 3 ? copy.next : draft.started ? copy.retry : copy.save}
          </Button>
        </div>
      </form>
      <ConfirmationDialog
        cancelLabel={copy.cancel}
        confirmLabel={copy.confirm}
        description={copy.confirmDescription}
        onCancel={() => setConfirming(false)}
        onConfirm={() => void submit()}
        open={confirming}
        title={copy.confirmTitle}
      />
    </section>
  );
}
