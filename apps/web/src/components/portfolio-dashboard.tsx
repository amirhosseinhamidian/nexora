"use client";

import {
  AlertTriangle,
  ArrowDownRight,
  ArrowUpRight,
  BriefcaseBusiness,
  CircleDollarSign,
  Landmark,
  LoaderCircle,
  PieChart,
  RefreshCw,
  ShieldAlert,
  WalletCards,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import type { Locale } from "@/i18n/config";
import type { Dictionary } from "@/i18n/dictionaries";
import { apiRequest } from "@/lib/api-client";

type RegistryStatus = "active" | "archived" | "closed" | "inactive";
type ValuationState = "fresh" | "missing" | "stale";
type AnalyticsState = "complete" | "missing" | "stale";

type Portfolio = {
  base_asset_id: string;
  kind: "paper" | "personal" | "shadow";
  name: string;
  portfolio_id: string;
  portfolio_key: string;
  status: RegistryStatus;
};

export type PortfolioWorkspaceAccount = {
  account_id: string;
  account_key: string;
  institution_name: string | null;
  kind:
    | "brokerage_manual"
    | "cash"
    | "exchange"
    | "other_manual"
    | "paper"
    | "shadow"
    | "wallet_watch_only";
  name: string;
  portfolio_id: string;
  status: RegistryStatus;
};

export type PortfolioWorkspaceAsset = {
  asset_id: string;
  name: string;
  status: RegistryStatus;
  symbol: string;
};

type Position = {
  asset_id: string;
  market_value: string | null;
  state: ValuationState;
};

type PortfolioAnalytics = {
  as_of: string;
  nav: string | null;
  positions: Position[];
  priced_value: string;
  realized_pnl: string | null;
  state: AnalyticsState;
  unrealized_pnl: string | null;
};

type ValuationStatus = {
  asset_id: string;
  state: ValuationState;
};

type ListResponse<T> = { items: T[] };
type ValuationResponse = { as_of: string; items: ValuationStatus[] };

type RegistryData = {
  accounts: PortfolioWorkspaceAccount[];
  assets: PortfolioWorkspaceAsset[];
  portfolios: Portfolio[];
};

export type PortfolioWorkspaceContext = {
  accounts: PortfolioWorkspaceAccount[];
  assets: PortfolioWorkspaceAsset[];
  portfolioId: string;
  portfolioName: string;
};

type DetailData = {
  analytics: PortfolioAnalytics;
  valuation: ValuationResponse;
};

type ExactDecimal = { scale: number; units: bigint };

const decimalPattern = /^(-?)(0|[1-9][0-9]*)(?:\.([0-9]+))?$/;

function parseDecimal(value: string): ExactDecimal {
  const match = decimalPattern.exec(value);
  if (!match) throw new Error("invalid canonical decimal");
  const fraction = match[3] ?? "";
  const units = BigInt(`${match[2]}${fraction}`) * (match[1] === "-" ? -1n : 1n);
  return { scale: fraction.length, units };
}

function powerOfTen(exponent: number): bigint {
  return 10n ** BigInt(exponent);
}

function align(value: ExactDecimal, scale: number): bigint {
  return value.units * powerOfTen(scale - value.scale);
}

function addExact(left: ExactDecimal, right: ExactDecimal): ExactDecimal {
  const scale = Math.max(left.scale, right.scale);
  return { scale, units: align(left, scale) + align(right, scale) };
}

function compareExact(left: ExactDecimal, right: ExactDecimal): number {
  const scale = Math.max(left.scale, right.scale);
  const difference = align(left, scale) - align(right, scale);
  return difference < 0n ? -1 : difference > 0n ? 1 : 0;
}

function localizeDigits(value: string, locale: Locale): string {
  if (locale === "en") return value;
  return value.replace(/[0-9]/g, (digit) => "۰۱۲۳۴۵۶۷۸۹"[Number(digit)]);
}

export function formatExactDecimal(
  value: string | null,
  locale: Locale,
  fractionDigits = 2,
): string {
  if (value === null) return "—";
  const parsed = parseDecimal(value);
  const negative = parsed.units < 0n;
  let absolute = negative ? -parsed.units : parsed.units;
  if (parsed.scale > fractionDigits) {
    const divisor = powerOfTen(parsed.scale - fractionDigits);
    const remainder = absolute % divisor;
    absolute /= divisor;
    if (remainder * 2n >= divisor) absolute += 1n;
  } else {
    absolute *= powerOfTen(fractionDigits - parsed.scale);
  }
  const scaleDivisor = powerOfTen(fractionDigits);
  const integer = absolute / scaleDivisor;
  const fraction =
    fractionDigits === 0 ? "" : (absolute % scaleDivisor).toString().padStart(fractionDigits, "0");
  const grouped = integer.toString().replace(/\B(?=(\d{3})+(?!\d))/g, locale === "fa" ? "٬" : ",");
  const decimal = fraction ? `${locale === "fa" ? "٫" : "."}${fraction}` : "";
  return localizeDigits(`${negative ? "−" : ""}${grouped}${decimal}`, locale);
}

function allocationRows(positions: Position[], assets: Map<string, PortfolioWorkspaceAsset>) {
  const grouped = new Map<string, ExactDecimal>();
  for (const position of positions) {
    if (position.market_value === null) continue;
    const value = parseDecimal(position.market_value);
    if (value.units <= 0n) continue;
    grouped.set(
      position.asset_id,
      addExact(grouped.get(position.asset_id) ?? { scale: 0, units: 0n }, value),
    );
  }
  const rows = [...grouped].map(([assetId, value]) => ({ assetId, value }));
  if (rows.length === 0) return [];
  rows.sort((left, right) => compareExact(right.value, left.value));
  const scale = Math.max(...rows.map((row) => row.value.scale));
  const total = rows.reduce((sum, row) => sum + align(row.value, scale), 0n);
  return rows.map((row) => {
    const normalized = align(row.value, scale);
    const basisPoints = Number((normalized * 10_000n + total / 2n) / total);
    const asset = assets.get(row.assetId);
    return {
      assetId: row.assetId,
      basisPoints,
      label: asset?.name ?? row.assetId.slice(0, 8),
      symbol: asset?.symbol ?? "—",
    };
  });
}

function percentage(basisPoints: number, locale: Locale): string {
  const integer = Math.floor(basisPoints / 100);
  const fraction = Math.floor((basisPoints % 100) / 10);
  return localizeDigits(`${integer}${locale === "fa" ? "٫" : "."}${fraction}%`, locale);
}

function formatTimestamp(value: string, locale: Locale): string {
  return new Intl.DateTimeFormat(locale === "fa" ? "fa-IR" : "en-GB", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

export function PortfolioDashboard({
  dictionary,
  locale,
  onWorkspaceChange,
}: {
  dictionary: Dictionary;
  locale: Locale;
  onWorkspaceChange?: (context?: PortfolioWorkspaceContext) => void;
}) {
  const copy = dictionary.portfolioDashboard;
  const [registryState, setRegistryState] = useState<"error" | "loading" | "ready">("loading");
  const [detailState, setDetailState] = useState<"error" | "loading" | "ready">("loading");
  const [registry, setRegistry] = useState<RegistryData>({
    accounts: [],
    assets: [],
    portfolios: [],
  });
  const [details, setDetails] = useState<DetailData>();
  const [selectedPortfolioId, setSelectedPortfolioId] = useState("");
  const [registryRevision, setRegistryRevision] = useState(0);
  const [detailRevision, setDetailRevision] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    async function loadRegistry() {
      setRegistryState("loading");
      try {
        const [portfolioResponse, accountResponse, assetResponse] = await Promise.all([
          apiRequest<ListResponse<Portfolio>>("/api/v1/portfolios", { signal: controller.signal }),
          apiRequest<ListResponse<PortfolioWorkspaceAccount>>("/api/v1/accounts", {
            signal: controller.signal,
          }),
          apiRequest<ListResponse<PortfolioWorkspaceAsset>>("/api/v1/assets", {
            signal: controller.signal,
          }),
        ]);
        if (controller.signal.aborted) return;
        const next = {
          accounts: accountResponse.items,
          assets: assetResponse.items,
          portfolios: portfolioResponse.items,
        };
        setRegistry(next);
        setSelectedPortfolioId((current) => {
          if (next.portfolios.some((item) => item.portfolio_id === current)) return current;
          return (
            next.portfolios.find((item) => item.status === "active")?.portfolio_id ??
            next.portfolios[0]?.portfolio_id ??
            ""
          );
        });
        setRegistryState("ready");
      } catch {
        if (!controller.signal.aborted) setRegistryState("error");
      }
    }
    void loadRegistry();
    return () => controller.abort();
  }, [registryRevision]);

  useEffect(() => {
    if (!selectedPortfolioId || registryState !== "ready") {
      return;
    }
    const controller = new AbortController();
    async function loadDetails() {
      setDetailState("loading");
      const asOf = new Date().toISOString();
      const encoded = encodeURIComponent(asOf);
      try {
        const [analytics, valuation] = await Promise.all([
          apiRequest<PortfolioAnalytics>(
            `/api/v1/portfolios/${encodeURIComponent(selectedPortfolioId)}/analytics?as_of=${encoded}`,
            {
              signal: controller.signal,
            },
          ),
          apiRequest<ValuationResponse>(
            `/api/v1/portfolios/${encodeURIComponent(selectedPortfolioId)}/valuation-status?as_of=${encoded}`,
            {
              signal: controller.signal,
            },
          ),
        ]);
        if (controller.signal.aborted) return;
        setDetails({ analytics, valuation });
        setDetailState("ready");
      } catch {
        if (!controller.signal.aborted) setDetailState("error");
      }
    }
    void loadDetails();
    return () => controller.abort();
  }, [detailRevision, registryState, selectedPortfolioId]);

  const selectedPortfolio = registry.portfolios.find(
    (item) => item.portfolio_id === selectedPortfolioId,
  );
  const selectedAccounts = useMemo(
    () => registry.accounts.filter((item) => item.portfolio_id === selectedPortfolioId),
    [registry.accounts, selectedPortfolioId],
  );
  const assets = useMemo(
    () => new Map(registry.assets.map((asset) => [asset.asset_id, asset])),
    [registry.assets],
  );
  const allocation = useMemo(
    () => allocationRows(details?.analytics.positions ?? [], assets),
    [assets, details?.analytics.positions],
  );
  const retryRegistry = useCallback(() => setRegistryRevision((revision) => revision + 1), []);
  const workspaceContext = useMemo<PortfolioWorkspaceContext | undefined>(
    () =>
      selectedPortfolio
        ? {
            accounts: selectedAccounts,
            assets: registry.assets,
            portfolioId: selectedPortfolio.portfolio_id,
            portfolioName: selectedPortfolio.name,
          }
        : undefined,
    [registry.assets, selectedAccounts, selectedPortfolio],
  );

  useEffect(() => {
    onWorkspaceChange?.(workspaceContext);
  }, [onWorkspaceChange, workspaceContext]);

  if (registryState === "loading") {
    return (
      <section aria-live="polite" className="dashboard-state portfolio-dashboard">
        <LoaderCircle aria-hidden="true" className="spin" size={28} />
        <div>
          <h2>{copy.loadingTitle}</h2>
          <p>{copy.loadingDescription}</p>
        </div>
      </section>
    );
  }

  if (registryState === "error") {
    return (
      <section className="dashboard-state error portfolio-dashboard" role="alert">
        <ShieldAlert aria-hidden="true" size={28} />
        <div>
          <h2>{copy.errorTitle}</h2>
          <p>{copy.errorDescription}</p>
          <button className="secondary-button" onClick={retryRegistry} type="button">
            <RefreshCw aria-hidden="true" size={17} />
            {copy.retry}
          </button>
        </div>
      </section>
    );
  }

  if (registry.portfolios.length === 0) {
    return (
      <section className="dashboard-state portfolio-dashboard">
        <BriefcaseBusiness aria-hidden="true" size={30} />
        <div>
          <h2>{copy.emptyTitle}</h2>
          <p>{copy.emptyDescription}</p>
        </div>
      </section>
    );
  }

  const baseAsset = selectedPortfolio ? assets.get(selectedPortfolio.base_asset_id) : undefined;
  const valuationCounts = { fresh: 0, missing: 0, stale: 0 };
  for (const item of details?.valuation.items ?? []) valuationCounts[item.state] += 1;
  const totalValuations = valuationCounts.fresh + valuationCounts.stale + valuationCounts.missing;
  const pnl = details?.analytics.unrealized_pnl ?? null;
  const pnlNegative = pnl?.startsWith("-") ?? false;

  return (
    <section
      aria-labelledby="portfolio-dashboard-title"
      className="portfolio-dashboard"
      id="portfolio-overview"
    >
      <div className="dashboard-toolbar">
        <div>
          <p className="section-kicker">{copy.eyebrow}</p>
          <h2 id="portfolio-dashboard-title">{copy.title}</h2>
        </div>
        <label className="portfolio-selector">
          <span>{copy.selectPortfolio}</span>
          <select
            value={selectedPortfolioId}
            onChange={(event) => setSelectedPortfolioId(event.target.value)}
          >
            {registry.portfolios.map((portfolio) => (
              <option key={portfolio.portfolio_id} value={portfolio.portfolio_id}>
                {portfolio.name}
              </option>
            ))}
          </select>
        </label>
      </div>

      <div className="portfolio-context">
        <span className={`status-badge ${selectedPortfolio?.status}`}>
          {copy.status[selectedPortfolio?.status ?? "inactive"]}
        </span>
        <span>{copy.kind[selectedPortfolio?.kind ?? "personal"]}</span>
        <code dir="ltr">{selectedPortfolio?.portfolio_key}</code>
      </div>

      {detailState === "loading" ? (
        <div aria-live="polite" className="dashboard-state compact">
          <LoaderCircle aria-hidden="true" className="spin" size={24} />
          <p>{copy.loadingAnalytics}</p>
        </div>
      ) : detailState === "error" || !details ? (
        <div className="dashboard-state compact error" role="alert">
          <AlertTriangle aria-hidden="true" size={24} />
          <div>
            <p>{copy.analyticsError}</p>
            <button
              className="secondary-button"
              onClick={() => setDetailRevision((revision) => revision + 1)}
              type="button"
            >
              <RefreshCw aria-hidden="true" size={17} />
              {copy.retry}
            </button>
          </div>
        </div>
      ) : (
        <>
          <div className="portfolio-metric-grid">
            <article className="portfolio-metric-card">
              <div>
                <span>{copy.nav}</span>
                <CircleDollarSign aria-hidden="true" size={20} />
              </div>
              <strong dir="ltr">
                {formatExactDecimal(details.analytics.nav, locale)}{" "}
                <small>{baseAsset?.symbol ?? ""}</small>
              </strong>
              <p>
                {copy.asOf} {formatTimestamp(details.analytics.as_of, locale)}
              </p>
            </article>
            <article className="portfolio-metric-card">
              <div>
                <span>{copy.unrealizedPnl}</span>
                {pnlNegative ? (
                  <ArrowDownRight aria-hidden="true" className="negative" size={20} />
                ) : (
                  <ArrowUpRight aria-hidden="true" size={20} />
                )}
              </div>
              <strong className={pnlNegative ? "negative" : "positive"} dir="ltr">
                {formatExactDecimal(pnl, locale)} <small>{baseAsset?.symbol ?? ""}</small>
              </strong>
              <p>
                {copy.realizedPnl}:{" "}
                <b dir="ltr">{formatExactDecimal(details.analytics.realized_pnl, locale)}</b>
              </p>
            </article>
            <article className="portfolio-metric-card">
              <div>
                <span>{copy.accounts}</span>
                <WalletCards aria-hidden="true" size={20} />
              </div>
              <strong>{localizeDigits(String(selectedAccounts.length), locale)}</strong>
              <p>
                {copy.activeAccounts}:{" "}
                {localizeDigits(
                  String(selectedAccounts.filter((item) => item.status === "active").length),
                  locale,
                )}
              </p>
            </article>
            <article className="portfolio-metric-card">
              <div>
                <span>{copy.valuationHealth}</span>
                <Landmark aria-hidden="true" size={20} />
              </div>
              <strong>
                {localizeDigits(`${valuationCounts.fresh}/${totalValuations}`, locale)}
              </strong>
              <p>{copy.freshEvidence}</p>
            </article>
          </div>

          {details.analytics.state !== "complete" && (
            <div className={`analytics-notice ${details.analytics.state}`} role="status">
              <AlertTriangle aria-hidden="true" size={20} />
              <span>{copy.analyticsState[details.analytics.state]}</span>
            </div>
          )}

          <div className="portfolio-detail-grid">
            <article className="dashboard-card valuation-card">
              <div className="card-heading">
                <div>
                  <p className="section-kicker">{copy.evidence}</p>
                  <h3>{copy.valuationHealth}</h3>
                </div>
                <Landmark aria-hidden="true" size={22} />
              </div>
              <div className="valuation-summary">
                {(["fresh", "stale", "missing"] as const).map((state) => (
                  <div className={`valuation-count ${state}`} key={state}>
                    <span>{copy.valuationState[state]}</span>
                    <strong>{localizeDigits(String(valuationCounts[state]), locale)}</strong>
                  </div>
                ))}
              </div>
              <p className="card-footnote">{copy.valuationFootnote}</p>
            </article>

            <article className="dashboard-card allocation-card">
              <div className="card-heading">
                <div>
                  <p className="section-kicker">{copy.pricedPositions}</p>
                  <h3>{copy.allocation}</h3>
                </div>
                <PieChart aria-hidden="true" size={22} />
              </div>
              {allocation.length === 0 ? (
                <p className="inline-empty">{copy.noAllocation}</p>
              ) : (
                <ul className="allocation-list">
                  {allocation.map((item) => (
                    <li key={item.assetId}>
                      <div>
                        <span>
                          <b dir="ltr">{item.symbol}</b> {item.label}
                        </span>
                        <strong>{percentage(item.basisPoints, locale)}</strong>
                      </div>
                      <span aria-hidden="true" className="allocation-track">
                        <span style={{ width: `${item.basisPoints / 100}%` }} />
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </article>
          </div>
        </>
      )}

      <section aria-labelledby="accounts-title" className="accounts-section" id="accounts">
        <div className="card-heading accounts-heading">
          <div>
            <p className="section-kicker">{copy.registry}</p>
            <h3 id="accounts-title">{copy.accountRegistry}</h3>
          </div>
          <span className="count-badge">
            {localizeDigits(String(selectedAccounts.length), locale)}
          </span>
        </div>
        {selectedAccounts.length === 0 ? (
          <p className="inline-empty">{copy.noAccounts}</p>
        ) : (
          <div className="account-grid">
            {selectedAccounts.map((account) => (
              <article className="account-card" key={account.account_id}>
                <div className="account-icon">
                  <WalletCards aria-hidden="true" size={20} />
                </div>
                <div className="account-copy">
                  <div>
                    <h4>{account.name}</h4>
                    <span className={`status-badge ${account.status}`}>
                      {copy.status[account.status]}
                    </span>
                  </div>
                  <p>{copy.accountKind[account.kind]}</p>
                  <dl>
                    <div>
                      <dt>{copy.institution}</dt>
                      <dd>{account.institution_name ?? copy.manualAccount}</dd>
                    </div>
                    <div>
                      <dt>{copy.accountKey}</dt>
                      <dd>
                        <code dir="ltr">{account.account_key}</code>
                      </dd>
                    </div>
                  </dl>
                </div>
              </article>
            ))}
          </div>
        )}
      </section>
    </section>
  );
}
