"use client";

import {
  Button,
  Checkbox,
  FieldError,
  FormField,
  Input,
  Select,
  type SelectOption,
} from "@nexora/ui/primitives";
import { type FormEvent, useId, useState } from "react";

import type { Dictionary } from "@/i18n/dictionaries";
import {
  accountKinds,
  assetClasses,
  identifierSchemes,
  normalizeRegistryName,
  portfolioKinds,
  type AssetIdentifierInput,
  type RegistryCreation,
  type RegistrySection,
  type RegistrySnapshot,
} from "@/lib/portfolio-registry";

export function registryOptions<Value extends string>(
  values: readonly Value[],
  labels: Record<Value, string>,
): SelectOption[] {
  return values.map((value) => ({ value, label: labels[value] }));
}

export function RegistrySelectField({
  id,
  label,
  onValueChange,
  options,
  required,
  value,
}: {
  id: string;
  label: string;
  onValueChange: (value: string) => void;
  options: SelectOption[];
  required?: boolean;
  value: string;
}) {
  return (
    <FormField id={id} label={label}>
      <Select
        aria-required={required}
        id={id}
        onValueChange={onValueChange}
        options={options}
        value={value}
      />
    </FormField>
  );
}

export function RegistryCreateForm({
  busy,
  dictionary,
  onCreate,
  section,
  snapshot,
}: {
  busy: boolean;
  dictionary: Dictionary;
  onCreate: (creation: RegistryCreation) => void;
  section: RegistrySection;
  snapshot: RegistrySnapshot;
}) {
  const id = useId();
  const copy = dictionary.registry;
  const onboarding = dictionary.onboarding;
  const classification = {
    assets: registryOptions(assetClasses, onboarding.assetClasses),
    portfolios: registryOptions(portfolioKinds, onboarding.portfolioKinds),
    accounts: registryOptions(accountKinds, onboarding.accountKinds),
  }[section];
  const activeAssets = snapshot.assets.filter((asset) => asset.status === "active");
  const activePortfolios = snapshot.portfolios.filter((portfolio) => portfolio.status === "active");
  const [kind, setKind] = useState(classification[0].value);
  const [parent, setParent] = useState("");
  const [error, setError] = useState("");

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy) return;
    const data = new FormData(event.currentTarget);
    const name = normalizeRegistryName(String(data.get("name") ?? ""));
    if (!name || name.length > 120) {
      setError(copy.invalidName);
      return;
    }
    if (section === "assets") {
      const asset_class = assetClasses.find((item) => item === kind);
      const symbol = String(data.get("symbol") ?? "")
        .trim()
        .toUpperCase();
      const rawPrecision = String(data.get("precision") ?? "");
      const precision = Number(rawPrecision);
      if (!/^[A-Z0-9][A-Z0-9._-]{0,23}$/.test(symbol)) {
        setError(copy.invalidSymbol);
        return;
      }
      if (
        !/^\d+$/.test(rawPrecision) ||
        !Number.isInteger(precision) ||
        precision < 0 ||
        precision > 30
      ) {
        setError(copy.invalidPrecision);
        return;
      }
      if (!asset_class) return;
      setError("");
      onCreate({ section, fields: { name, symbol, precision, asset_class } });
    } else if (section === "portfolios") {
      const portfolioKind = portfolioKinds.find((item) => item === kind);
      if (!portfolioKind || !activeAssets.some((asset) => asset.asset_id === parent)) {
        setError(copy.chooseAsset);
        return;
      }
      setError("");
      onCreate({ section, fields: { name, kind: portfolioKind, base_asset_id: parent } });
    } else {
      const accountKind = accountKinds.find((item) => item === kind);
      if (
        !accountKind ||
        !activePortfolios.some((portfolio) => portfolio.portfolio_id === parent)
      ) {
        setError(copy.choosePortfolio);
        return;
      }
      const institution = normalizeRegistryName(String(data.get("institution") ?? ""));
      setError("");
      onCreate({
        section,
        fields: {
          name,
          kind: accountKind,
          portfolio_id: parent,
          institution_name: institution || null,
        },
      });
    }
  }

  return (
    <form noValidate onSubmit={submit}>
      <fieldset className="grid gap-4" disabled={busy}>
        <FormField id={`${id}-name`} label={copy.name}>
          <Input id={`${id}-name`} maxLength={120} name="name" required />
        </FormField>
        <RegistrySelectField
          id={`${id}-kind`}
          label={section === "assets" ? onboarding.assetClass : copy.kind}
          onValueChange={setKind}
          options={classification}
          value={kind}
        />
        {section === "assets" ? (
          <>
            <FormField id={`${id}-symbol`} label={onboarding.symbol}>
              <Input dir="ltr" id={`${id}-symbol`} maxLength={24} name="symbol" required />
            </FormField>
            <FormField id={`${id}-precision`} label={onboarding.precision}>
              <Input
                defaultValue={2}
                dir="ltr"
                id={`${id}-precision`}
                inputMode="numeric"
                max={30}
                min={0}
                name="precision"
                required
                type="number"
              />
            </FormField>
          </>
        ) : null}
        {section === "portfolios" ? (
          <RegistrySelectField
            id={`${id}-base-asset`}
            label={onboarding.baseAsset}
            onValueChange={setParent}
            options={[
              { value: "", label: copy.chooseAsset, disabled: true },
              ...activeAssets.map(({ asset_id, name, symbol }) => ({
                value: asset_id,
                label: `${name} (${symbol})`,
              })),
            ]}
            required
            value={parent}
          />
        ) : null}
        {section === "accounts" ? (
          <>
            <RegistrySelectField
              id={`${id}-portfolio`}
              label={copy.portfolio}
              onValueChange={setParent}
              options={[
                { value: "", label: copy.choosePortfolio, disabled: true },
                ...activePortfolios.map(({ portfolio_id, name }) => ({
                  value: portfolio_id,
                  label: name,
                })),
              ]}
              required
              value={parent}
            />
            <FormField
              id={`${id}-institution`}
              label={copy.institution}
              optionalLabel={copy.optional}
            >
              <Input id={`${id}-institution`} maxLength={120} name="institution" />
            </FormField>
          </>
        ) : null}
        {error ? <FieldError>{error}</FieldError> : null}
        <Button className="justify-self-start" loading={busy} type="submit">
          {busy ? copy.saving : copy[section].create}
        </Button>
      </fieldset>
    </form>
  );
}

export function AssetIdentifierForm({
  busy,
  copy,
  onSave,
}: {
  busy: boolean;
  copy: Dictionary["registry"];
  onSave: (input: AssetIdentifierInput) => void;
}) {
  const id = useId();
  const [scheme, setScheme] = useState<string>("ticker");
  const [invalid, setInvalid] = useState(false);

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy) return;
    const data = new FormData(event.currentTarget);
    const value = String(data.get("identifier") ?? "").trim();
    const selectedScheme = identifierSchemes.find((item) => item === scheme);
    if (!selectedScheme || !/^[A-Za-z0-9][A-Za-z0-9._:/-]{0,159}$/.test(value)) {
      setInvalid(true);
      return;
    }
    setInvalid(false);
    onSave({ scheme: selectedScheme, value, is_primary: data.has("primary") });
  }

  return (
    <form noValidate onSubmit={submit}>
      <fieldset className="grid gap-4" disabled={busy}>
        <RegistrySelectField
          id={`${id}-scheme`}
          label={copy.identifierScheme}
          onValueChange={setScheme}
          options={registryOptions(identifierSchemes, copy.identifierSchemes)}
          value={scheme}
        />
        <FormField
          id={`${id}-value`}
          label={copy.identifierValue}
          error={invalid ? copy.invalidIdentifier : undefined}
        >
          <Input
            aria-describedby={invalid ? `${id}-value-error` : undefined}
            aria-invalid={invalid || undefined}
            dir="ltr"
            id={`${id}-value`}
            maxLength={160}
            name="identifier"
            required
          />
        </FormField>
        <Checkbox name="primary">{copy.identifierPrimary}</Checkbox>
        <Button className="justify-self-start" loading={busy} type="submit">
          {busy ? copy.saving : copy.addIdentifier}
        </Button>
      </fieldset>
    </form>
  );
}
