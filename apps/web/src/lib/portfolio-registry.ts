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
export const identifierSchemes = [
  "iso_4217",
  "ticker",
  "coingecko",
  "isin",
  "cusip",
  "figi",
  "manual",
] as const;

export type AssetInput = {
  asset_key: string;
  asset_class: (typeof assetClasses)[number];
  name: string;
  precision: number;
  symbol: string;
};
export type PortfolioInput = {
  portfolio_key: string;
  name: string;
  kind: (typeof portfolioKinds)[number];
  base_asset_id: string;
};
export type AccountInput = {
  account_key: string;
  name: string;
  kind: (typeof accountKinds)[number];
  portfolio_id: string;
};

type RegistryVersion = { row_version: number };
export type RegistryAsset = AssetInput &
  RegistryVersion & { asset_id: string; status: "active" | "inactive" };
export type RegistryPortfolio = PortfolioInput &
  RegistryVersion & { portfolio_id: string; status: "active" | "archived" };
export type RegistryAccount = AccountInput &
  RegistryVersion & {
    account_id: string;
    institution_name: string | null;
    status: "active" | "closed";
  };
export type RegistrySnapshot = {
  assets: RegistryAsset[];
  portfolios: RegistryPortfolio[];
  accounts: RegistryAccount[];
};
export type RegistrySection = keyof RegistrySnapshot;
export type RegistryRecord = RegistryAsset | RegistryPortfolio | RegistryAccount;
export type RegistryCreation =
  | { section: "assets"; fields: Omit<AssetInput, "asset_key"> }
  | { section: "portfolios"; fields: Omit<PortfolioInput, "portfolio_key"> }
  | {
      section: "accounts";
      fields: Omit<AccountInput, "account_key"> & Pick<RegistryAccount, "institution_name">;
    };
export type AssetIdentifierInput = {
  scheme: (typeof identifierSchemes)[number];
  value: string;
  is_primary: boolean;
};

const paths = {
  assets: "/api/v1/assets",
  portfolios: "/api/v1/portfolios",
  accounts: "/api/v1/accounts",
} as const;
const lifecycle = { assets: "deactivate", portfolios: "archive", accounts: "close" } as const;
const keyFields = {
  assets: "asset_key",
  portfolios: "portfolio_key",
  accounts: "account_key",
} as const;

export function normalizeRegistryName(value: string): string {
  return value.trim().replace(/\s+/g, " ");
}

export async function listRegistryItems<T>(path: string, signal: AbortSignal): Promise<T[]> {
  return (await apiRequest<{ items: T[] }>(path, { signal })).items;
}

export async function loadRegistry(
  section: RegistrySection,
  signal: AbortSignal,
): Promise<RegistrySnapshot> {
  const [assets, portfolios, accounts] = await Promise.all([
    section !== "accounts" ? listRegistryItems<RegistryAsset>(paths.assets, signal) : [],
    section !== "assets" ? listRegistryItems<RegistryPortfolio>(paths.portfolios, signal) : [],
    section === "accounts" ? listRegistryItems<RegistryAccount>(paths.accounts, signal) : [],
  ]);
  return { assets, portfolios, accounts };
}

export function registryRecordId(record: RegistryRecord): string {
  if ("asset_id" in record) return record.asset_id;
  if ("account_id" in record) return record.account_id;
  return record.portfolio_id;
}

export async function createRegistryRecord(
  { section, fields }: RegistryCreation,
  key: string,
  signal: AbortSignal,
): Promise<void> {
  const body = { ...fields, [keyFields[section]]: key };
  try {
    await apiRequest<RegistryRecord>(paths[section], { method: "POST", body, signal });
  } catch (error) {
    signal.throwIfAborted();
    if (error instanceof ApiRequestError && error.status < 500 && error.status !== 409) throw error;

    // Registry keys are unique. Recover only when the server stored this exact submission.
    const records = await listRegistryItems<Record<string, unknown>>(paths[section], signal);
    const saved = records.some(
      (item) =>
        item.status === "active" &&
        Object.entries(body).every(([name, value]) => item[name] === value),
    );
    if (!saved) throw error;
  }
}

export async function changeRegistryLifecycle(record: RegistryRecord, signal: AbortSignal) {
  const section =
    "asset_id" in record ? "assets" : "account_id" in record ? "accounts" : "portfolios";
  const id = encodeURIComponent(registryRecordId(record));
  return apiRequest<RegistryRecord>(`${paths[section]}/${id}/${lifecycle[section]}`, {
    method: "POST",
    body: { expected_row_version: record.row_version },
    signal,
  });
}

export async function addAssetIdentifier(
  assetId: string,
  body: AssetIdentifierInput,
  signal: AbortSignal,
) {
  return apiRequest(`${paths.assets}/${encodeURIComponent(assetId)}/identifiers`, {
    method: "POST",
    body,
    signal,
  });
}
