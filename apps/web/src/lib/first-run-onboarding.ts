import { ApiRequestError, apiRequest } from "@/lib/api-client";

export const assetClasses = ["fiat", "crypto", "equity", "fund", "commodity", "other"] as const;
export const portfolioKinds = ["personal", "paper", "shadow"] as const;
export const accountKinds = [
  "cash",
  "brokerage_manual",
  "wallet_watch_only",
  "exchange",
  "paper",
  "shadow",
  "other_manual",
] as const;

type AssetClass = (typeof assetClasses)[number];
type PortfolioKind = (typeof portfolioKinds)[number];
type AccountKind = (typeof accountKinds)[number];

type AssetInput = {
  asset_key: string;
  asset_class: AssetClass;
  name: string;
  precision: number;
  symbol: string;
};
type PortfolioInput = {
  portfolio_key: string;
  name: string;
  kind: PortfolioKind;
  base_asset_id: string;
};
type AccountInput = {
  account_key: string;
  name: string;
  kind: AccountKind;
  portfolio_id: string;
};
export type SetupAsset = AssetInput & { asset_id: string; status: string };
export type SetupPortfolio = PortfolioInput & { portfolio_id: string; status: string };
type SetupAccount = AccountInput & { account_id: string; status: string };

export type OnboardingDraft = {
  id: string;
  step: number;
  started: boolean;
  assetMode: "existing" | "new";
  selectedAssetId: string;
  savedAssetId: string;
  assetName: string;
  assetSymbol: string;
  assetClass: AssetClass;
  assetPrecision: string;
  portfolioName: string;
  portfolioKind: PortfolioKind;
  savedPortfolioId: string;
  addAccount: boolean;
  accountName: string;
  accountKind: AccountKind;
};

export type SetupProblem = "assetUnavailable" | "existingPortfolio" | "conflict" | "invalid";

export class OnboardingError extends Error {
  constructor(readonly problem: SetupProblem) {
    super(problem);
  }
}

const firstPortfolioKey = "first-portfolio";
const firstAccountKey = "first-portfolio-account";
const setupApi = {
  assets: "/api/v1/assets",
  portfolios: "/api/v1/portfolios",
  accounts: "/api/v1/accounts",
} as const;

function draftKey(ownerId: string) {
  return `nexora:onboarding:v1:${ownerId}`;
}

export function hasOnboardingDraft(ownerId: string): boolean {
  try {
    return window.sessionStorage.getItem(draftKey(ownerId)) !== null;
  } catch {
    return false;
  }
}

export function readOnboardingDraft(ownerId: string, assets: SetupAsset[]): OnboardingDraft {
  const initial: OnboardingDraft = {
    id: crypto.randomUUID(),
    step: 0,
    started: false,
    assetMode: assets.length ? "existing" : "new",
    selectedAssetId: assets[0]?.asset_id ?? "",
    savedAssetId: "",
    assetName: "",
    assetSymbol: "",
    assetClass: "fiat",
    assetPrecision: "2",
    portfolioName: "",
    portfolioKind: "personal",
    savedPortfolioId: "",
    addAccount: false,
    accountName: "",
    accountKind: "cash",
  };
  try {
    const value: unknown = JSON.parse(window.sessionStorage.getItem(draftKey(ownerId)) ?? "null");
    if (!value || typeof value !== "object") return initial;
    const saved = value as OnboardingDraft;
    if (
      Object.keys(initial).some(
        (key) =>
          typeof saved[key as keyof OnboardingDraft] !==
          typeof initial[key as keyof OnboardingDraft],
      )
    ) {
      return initial;
    }
    if (
      !/^[0-9a-f-]{36}$/.test(saved.id) ||
      ![0, 1, 2, 3].includes(saved.step) ||
      !["existing", "new"].includes(saved.assetMode) ||
      !assetClasses.includes(saved.assetClass) ||
      !portfolioKinds.includes(saved.portfolioKind) ||
      !accountKinds.includes(saved.accountKind)
    )
      return initial;
    return saved;
  } catch {
    return initial;
  }
}

export function writeOnboardingDraft(ownerId: string, draft: OnboardingDraft | undefined): boolean {
  try {
    if (draft) window.sessionStorage.setItem(draftKey(ownerId), JSON.stringify(draft));
    else window.sessionStorage.removeItem(draftKey(ownerId));
    return true;
  } catch {
    return false;
  }
}

async function list<T>(path: string, signal: AbortSignal): Promise<T[]> {
  const response = await apiRequest<{ items: T[] }>(path, { signal });
  return response.items;
}

export async function loadSetupRegistry(signal: AbortSignal) {
  const [assets, portfolios] = await Promise.all([
    list<SetupAsset>(setupApi.assets, signal),
    list<SetupPortfolio>(setupApi.portfolios, signal),
  ]);
  return { assets: assets.filter((asset) => asset.status === "active"), portfolios };
}

function name(value: string) {
  return value.trim().replace(/\s+/g, " ");
}

export function canResumePortfolio(draft: OnboardingDraft, portfolio: SetupPortfolio) {
  return (
    portfolio.portfolio_key === firstPortfolioKey &&
    portfolio.status === "active" &&
    (draft.savedPortfolioId === portfolio.portfolio_id ||
      (draft.started &&
        portfolio.name === name(draft.portfolioName) &&
        portfolio.kind === draft.portfolioKind))
  );
}

export function validSetupStep(
  draft: OnboardingDraft,
  assets: SetupAsset[],
  step: number,
): boolean {
  const hasName = (value: string) => name(value).length > 0 && name(value).length <= 120;
  if (step === 0) {
    if (draft.assetMode === "existing") {
      return assets.some((asset) => asset.asset_id === draft.selectedAssetId);
    }
    return (
      hasName(draft.assetName) &&
      /^[A-Z0-9][A-Z0-9._-]{0,23}$/.test(draft.assetSymbol.trim().toUpperCase()) &&
      /^(?:[0-9]|[12][0-9]|30)$/.test(draft.assetPrecision)
    );
  }
  if (step === 1) return hasName(draft.portfolioName);
  return !draft.addAccount || hasName(draft.accountName);
}

function matches<T extends object>(record: T, input: Partial<T>) {
  return (Object.keys(input) as (keyof T)[]).every((key) => record[key] === input[key]);
}

async function createOrRecover<T>(
  path: string,
  input: object,
  lookup: () => Promise<T | undefined>,
  signal: AbortSignal,
): Promise<T> {
  const existing = await lookup();
  if (existing) return existing;
  signal.throwIfAborted();
  try {
    return await apiRequest<T>(path, { method: "POST", body: input, signal });
  } catch (error) {
    signal.throwIfAborted();
    // A conflicting key or a lost response can mean this exact write already committed.
    if (error instanceof ApiRequestError && error.status < 500 && error.status !== 409) throw error;
    const recovered = await lookup();
    if (recovered) return recovered;
    throw error;
  }
}

export async function completeOnboarding(
  draft: OnboardingDraft,
  signal: AbortSignal,
  checkpoint: (draft: OnboardingDraft) => void,
) {
  const registry = await loadSetupRegistry(signal);
  const expectedAsset = draft.assetMode === "new" ? draft.savedAssetId : draft.selectedAssetId;
  const resumed = registry.portfolios.find(
    (item) => canResumePortfolio(draft, item) && item.base_asset_id === expectedAsset,
  );
  if (registry.portfolios.length && !resumed) {
    throw new OnboardingError("existingPortfolio");
  }
  if (![1, 2].every((step) => validSetupStep(draft, registry.assets, step))) {
    throw new OnboardingError("invalid");
  }
  if (!resumed && !validSetupStep(draft, registry.assets, 0)) {
    throw new OnboardingError(draft.assetMode === "existing" ? "assetUnavailable" : "invalid");
  }

  let assetId = draft.selectedAssetId;
  if (!resumed && draft.assetMode === "new") {
    const input: AssetInput = {
      asset_key: `setup-${draft.id}`,
      asset_class: draft.assetClass,
      name: name(draft.assetName),
      symbol: draft.assetSymbol.trim().toUpperCase(),
      precision: Number(draft.assetPrecision),
    };
    const asset = await createOrRecover<SetupAsset>(
      setupApi.assets,
      input,
      async () => {
        const existing = (await list<SetupAsset>(setupApi.assets, signal)).find(
          (item) => item.asset_key === input.asset_key,
        );
        if (existing && existing.status !== "active") throw new OnboardingError("assetUnavailable");
        if (existing && !matches(existing, input)) throw new OnboardingError("conflict");
        return existing;
      },
      signal,
    );
    assetId = asset.asset_id;
    draft = { ...draft, savedAssetId: assetId };
    signal.throwIfAborted();
    checkpoint(draft);
  }

  const portfolioInput: PortfolioInput = {
    portfolio_key: firstPortfolioKey,
    name: name(draft.portfolioName),
    kind: draft.portfolioKind,
    base_asset_id: assetId,
  };
  const portfolio =
    resumed ??
    (await createOrRecover<SetupPortfolio>(
      setupApi.portfolios,
      portfolioInput,
      async () => {
        const portfolios = await list<SetupPortfolio>(setupApi.portfolios, signal);
        const existing = portfolios.find(
          (item) => item.status === "active" && matches(item, portfolioInput),
        );
        if (!existing && portfolios.length) throw new OnboardingError("existingPortfolio");
        return existing;
      },
      signal,
    ).catch((error: unknown) => {
      if (error instanceof ApiRequestError && error.status === 404) {
        throw new OnboardingError("assetUnavailable");
      }
      throw error;
    }));
  draft = { ...draft, savedPortfolioId: portfolio.portfolio_id };
  signal.throwIfAborted();
  checkpoint(draft);

  if (draft.addAccount) {
    const input: AccountInput = {
      account_key: firstAccountKey,
      name: name(draft.accountName),
      kind: draft.accountKind,
      portfolio_id: portfolio.portfolio_id,
    };
    await createOrRecover<SetupAccount>(
      setupApi.accounts,
      input,
      async () => {
        const existing = (await list<SetupAccount>(setupApi.accounts, signal)).find(
          (item) => item.account_key === input.account_key,
        );
        if (existing && (existing.status !== "active" || !matches(existing, input))) {
          throw new OnboardingError("conflict");
        }
        return existing;
      },
      signal,
    );
  }
  signal.throwIfAborted();
  return portfolio;
}
