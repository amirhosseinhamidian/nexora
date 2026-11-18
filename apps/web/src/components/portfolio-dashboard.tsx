"use client";

import {
  Alert,
  Button,
  ChartContainer,
  Disclosure,
  EmptyState,
  ErrorState,
  FormField,
  ResponsiveRecordList,
  Select,
  Spinner,
  StatCard,
  Table,
} from "@nexora/ui/primitives";
import {
  AlertTriangle,
  ArrowDownRight,
  ArrowUpRight,
  BriefcaseBusiness,
  CircleDollarSign,
  Landmark,
  Minus,
  PieChart,
  RefreshCw,
  Scale,
  ShieldAlert,
  WalletCards,
} from "lucide-react";
import Link from "next/link";
import { useId, type CSSProperties, useCallback, useEffect, useMemo, useState } from "react";

import { PortfolioHoldings } from "@/components/portfolio-holdings";
import { PortfolioPerformance } from "@/components/portfolio-performance";
import type { Locale } from "@/i18n/config";
import type { Dictionary } from "@/i18n/dictionaries";
import { apiRequest } from "@/lib/api-client";
import {
  addExact,
  align,
  compareExact,
  formatExactDecimal,
  formatTimestamp,
  localizeDigits,
  parseDecimal,
  type PositionValuation,
  type ValuationState,
} from "@/lib/portfolio-analytics";

type RegistryStatus = "active" | "archived" | "closed" | "inactive";
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
  precision?: number;
  status: RegistryStatus;
  symbol: string;
};

type PortfolioAnalytics = {
  as_of: string;
  nav: string | null;
  positions: PositionValuation[];
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

type DetailQuery = { portfolioId: string; revision: number };
type DetailResult = DetailQuery &
  (
    | { status: "ready"; analytics: PortfolioAnalytics; valuation?: ValuationResponse }
    | { status: "error" }
  );

function allocationRows(
  positions: PositionValuation[],
  assets: Map<string, PortfolioWorkspaceAsset>,
) {
  const grouped = new Map<string, ReturnType<typeof parseDecimal>>();
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

export function PortfolioDashboard({
  dictionary,
  locale,
  onWorkspaceChange,
  portfolioId,
  selectionOnly = false,
  showDetailsLink = false,
}: {
  dictionary: Dictionary;
  locale: Locale;
  onWorkspaceChange?: (context?: PortfolioWorkspaceContext) => void;
  portfolioId?: string;
  selectionOnly?: boolean;
  showDetailsLink?: boolean;
}) {
  const fieldId = useId();
  const copy = dictionary.portfolioDashboard;
  const [registryState, setRegistryState] = useState<"error" | "loading" | "ready">("loading");
  const [registry, setRegistry] = useState<RegistryData>({
    accounts: [],
    assets: [],
    portfolios: [],
  });
  const [detailResult, setDetailResult] = useState<DetailResult>();
  const [chosenPortfolioId, setChosenPortfolioId] = useState("");
  const selectedPortfolioId = portfolioId ?? chosenPortfolioId;
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
        setChosenPortfolioId((current) => {
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

  const selectedPortfolio = registry.portfolios.find(
    (item) => item.portfolio_id === selectedPortfolioId,
  );
  const analyticsPortfolioId = selectionOnly ? undefined : selectedPortfolio?.portfolio_id;
  const currentDetail =
    detailResult?.portfolioId === analyticsPortfolioId && detailResult?.revision === detailRevision
      ? detailResult
      : undefined;
  const details = currentDetail?.status === "ready" ? currentDetail : undefined;

  useEffect(() => {
    if (!analyticsPortfolioId || registryState !== "ready") {
      return;
    }
    const controller = new AbortController();
    async function loadDetails(id: string) {
      const asOf = new Date().toISOString();
      const encoded = encodeURIComponent(asOf);
      const [analytics, valuation] = await Promise.allSettled([
        apiRequest<PortfolioAnalytics>(
          `/api/v1/portfolios/${encodeURIComponent(id)}/analytics?as_of=${encoded}`,
          { signal: controller.signal },
        ),
        apiRequest<ValuationResponse>(
          `/api/v1/portfolios/${encodeURIComponent(id)}/valuation-status?as_of=${encoded}`,
          { signal: controller.signal },
        ),
      ]);
      if (controller.signal.aborted) return;
      const query = { portfolioId: id, revision: detailRevision };
      if (analytics.status === "rejected") {
        setDetailResult({ ...query, status: "error" });
        return;
      }
      setDetailResult({
        ...query,
        analytics: analytics.value,
        status: "ready",
        valuation: valuation.status === "fulfilled" ? valuation.value : undefined,
      });
    }
    void loadDetails(analyticsPortfolioId);
    return () => controller.abort();
  }, [analyticsPortfolioId, detailRevision, registryState]);

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
  const retryRegistry = useCallback(() => {
    setRegistryRevision((revision) => revision + 1);
    setDetailRevision((revision) => revision + 1);
  }, []);
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
        <Spinner label="" size="lg" />
        <div>
          <h2>{copy.loadingTitle}</h2>
          <p>{copy.loadingDescription}</p>
        </div>
      </section>
    );
  }

  if (registryState === "error") {
    return (
      <ErrorState
        className="dashboard-state error portfolio-dashboard"
        headingLevel={2}
        icon={<ShieldAlert aria-hidden="true" size={28} />}
        title={copy.errorTitle}
      >
        <p>{copy.errorDescription}</p>
        <Button
          variant="secondary"
          className="secondary-button"
          onClick={retryRegistry}
          type="button"
        >
          <RefreshCw aria-hidden="true" size={17} />
          {copy.retry}
        </Button>
      </ErrorState>
    );
  }

  if (portfolioId !== undefined && !selectedPortfolio) {
    return (
      <EmptyState
        className="dashboard-state error portfolio-dashboard"
        headingLevel={2}
        title={dictionary.workspacePages.portfolioUnavailableTitle}
      >
        <p>{dictionary.workspacePages.portfolioUnavailableDescription}</p>
        <Link className="secondary-button" href={`/${locale}/portfolios`}>
          {dictionary.workspacePages.backToPortfolios}
        </Link>
      </EmptyState>
    );
  }

  if (registry.portfolios.length === 0) {
    return (
      <EmptyState
        className="dashboard-state portfolio-dashboard"
        headingLevel={2}
        icon={<BriefcaseBusiness aria-hidden="true" size={30} />}
        title={copy.emptyTitle}
      >
        <p>{copy.emptyDescription}</p>
        <Link className="secondary-button" href={`/${locale}/onboarding`}>
          {dictionary.onboarding.start}
        </Link>
      </EmptyState>
    );
  }

  const selector = (
    <FormField
      className="portfolio-selector"
      id={`${fieldId}-select-portfolio`}
      label={copy.selectPortfolio}
    >
      <Select
        id={`${fieldId}-select-portfolio`}
        value={selectedPortfolioId}
        onValueChange={(value) => {
          setChosenPortfolioId(value);
          setDetailRevision((revision) => revision + 1);
        }}
        options={registry.portfolios.map((portfolio) => ({
          value: portfolio.portfolio_id,
          label: portfolio.name,
        }))}
      />
    </FormField>
  );

  if (selectionOnly) return <div className="workspace-portfolio-picker">{selector}</div>;

  const baseAsset = selectedPortfolio ? assets.get(selectedPortfolio.base_asset_id) : undefined;
  const valuationCounts = { fresh: 0, missing: 0, stale: 0 };
  for (const item of details?.valuation?.items ?? []) valuationCounts[item.state] += 1;
  const totalValuations = valuationCounts.fresh + valuationCounts.stale + valuationCounts.missing;
  const pnl = details?.analytics.unrealized_pnl ?? null;
  const pnlNegative = pnl?.startsWith("-") ?? false;
  const money = (value: string | null) =>
    value === null ? (
      copy.unavailable
    ) : (
      <bdi dir="ltr">
        {formatExactDecimal(value, locale, baseAsset?.precision)}{" "}
        <small>{baseAsset?.symbol ?? ""}</small>
      </bdi>
    );

  return (
    <section
      aria-labelledby="portfolio-dashboard-title"
      className="portfolio-dashboard"
      id="portfolio-overview"
    >
      <div className="dashboard-toolbar">
        <div>
          <p className="section-kicker">{copy.eyebrow}</p>
          <h2 id="portfolio-dashboard-title">
            {portfolioId ? selectedPortfolio?.name : copy.title}
          </h2>
        </div>
        {portfolioId === undefined ? selector : null}
      </div>

      {showDetailsLink && selectedPortfolio ? (
        <Link
          className="secondary-button"
          href={`/${locale}/portfolios/${encodeURIComponent(selectedPortfolio.portfolio_id)}`}
        >
          {dictionary.workspacePages.openPortfolioDetails}
        </Link>
      ) : null}

      <div className="portfolio-context">
        <span className={`status-badge ${selectedPortfolio?.status}`}>
          {copy.status[selectedPortfolio?.status ?? "inactive"]}
        </span>
        <span>{copy.kind[selectedPortfolio?.kind ?? "personal"]}</span>
        <code dir="ltr">{selectedPortfolio?.portfolio_key}</code>
      </div>

      {!currentDetail ? (
        <div aria-live="polite" className="dashboard-state compact">
          <Spinner label="" size="lg" />
          <p>{copy.loadingAnalytics}</p>
        </div>
      ) : !details ? (
        <Alert tone="danger" className="dashboard-state compact error" role="alert">
          <AlertTriangle aria-hidden="true" size={24} />
          <div>
            <p>{copy.analyticsError}</p>
            <Button
              variant="secondary"
              className="secondary-button"
              onClick={() => setDetailRevision((revision) => revision + 1)}
              type="button"
            >
              <RefreshCw aria-hidden="true" size={17} />
              {copy.retry}
            </Button>
          </div>
        </Alert>
      ) : (
        <>
          <div className="portfolio-metric-grid">
            <StatCard
              className="portfolio-metric-card"
              icon={<CircleDollarSign aria-hidden="true" size={20} />}
              label={copy.nav}
              value={money(details.analytics.nav)}
            >
              <p>
                {copy.asOf}{" "}
                <time dateTime={details.analytics.as_of}>
                  {formatTimestamp(details.analytics.as_of, locale)}
                </time>
              </p>
            </StatCard>
            <StatCard
              className="portfolio-metric-card"
              icon={
                pnl === null ? (
                  <Minus aria-hidden="true" size={20} />
                ) : pnlNegative ? (
                  <ArrowDownRight aria-hidden="true" className="negative" size={20} />
                ) : (
                  <ArrowUpRight aria-hidden="true" size={20} />
                )
              }
              label={copy.unrealizedPnl}
              value={money(pnl)}
              valueClassName={pnl === null ? undefined : pnlNegative ? "negative" : "positive"}
            />
            <StatCard
              className="portfolio-metric-card"
              icon={<Scale aria-hidden="true" size={20} />}
              label={copy.realizedPnl}
              value={money(details.analytics.realized_pnl)}
            />
            <StatCard
              className="portfolio-metric-card"
              icon={<WalletCards aria-hidden="true" size={20} />}
              label={copy.accounts}
              value={localizeDigits(String(selectedAccounts.length), locale)}
            >
              <p>
                {copy.activeAccounts}:{" "}
                {localizeDigits(
                  String(selectedAccounts.filter((item) => item.status === "active").length),
                  locale,
                )}
              </p>
            </StatCard>
          </div>

          {details.analytics.state !== "complete" && (
            <Alert
              tone="warning"
              className={`analytics-notice ${details.analytics.state}`}
              role="status"
            >
              <AlertTriangle aria-hidden="true" size={20} />
              <span>
                {details.analytics.nav === null
                  ? copy.navIncomplete
                  : copy.analyticsState[details.analytics.state]}
              </span>
              {details.analytics.nav === null ? (
                <span>
                  {copy.pricedValue} {money(details.analytics.priced_value)}
                </span>
              ) : null}
            </Alert>
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
              {details.valuation ? (
                <>
                  <p className="card-footnote">
                    {copy.freshEvidence}{" "}
                    <bdi>
                      {localizeDigits(`${valuationCounts.fresh}/${totalValuations}`, locale)}
                    </bdi>
                  </p>
                  <div className="valuation-summary">
                    {(["fresh", "stale", "missing"] as const).map((state) => (
                      <div className={`valuation-count ${state}`} key={state}>
                        <span>{copy.valuationState[state]}</span>
                        <strong>{localizeDigits(String(valuationCounts[state]), locale)}</strong>
                      </div>
                    ))}
                  </div>
                  <p className="card-footnote">{copy.valuationFootnote}</p>
                </>
              ) : (
                <Alert tone="warning">
                  <p>{copy.valuationUnavailable}</p>
                  <Button
                    onClick={() => setDetailRevision((revision) => revision + 1)}
                    variant="secondary"
                  >
                    {copy.retry}
                  </Button>
                </Alert>
              )}
            </article>

            <ChartContainer
              className="dashboard-card allocation-card"
              description={copy.pricedPositions}
              icon={<PieChart aria-hidden="true" size={22} />}
              table={
                allocation.length > 0 ? (
                  <Disclosure className="portfolio-chart-data" label={copy.showAllocationData}>
                    <Table>
                      <caption className="sr-only">{copy.allocation}</caption>
                      <thead>
                        <tr>
                          <th scope="col">{copy.allocationAsset}</th>
                          <th scope="col">{copy.allocationShare}</th>
                        </tr>
                      </thead>
                      <tbody>
                        {allocation.map((item) => (
                          <tr key={item.assetId}>
                            <th scope="row">
                              <bdi>{item.symbol}</bdi> {item.label}
                            </th>
                            <td>{percentage(item.basisPoints, locale)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </Table>
                  </Disclosure>
                ) : null
              }
              title={copy.allocation}
            >
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
                        <span
                          style={
                            {
                              "--nx-allocation-width": `${item.basisPoints / 100}%`,
                            } as CSSProperties
                          }
                        />
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </ChartContainer>
          </div>
          <PortfolioHoldings
            accounts={selectedAccounts}
            assets={assets}
            basePrecision={baseAsset?.precision}
            baseSymbol={baseAsset?.symbol}
            dictionary={dictionary}
            locale={locale}
            positions={details.analytics.positions}
          />
          <PortfolioPerformance
            asOf={details.analytics.as_of}
            basePrecision={baseAsset?.precision}
            baseSymbol={baseAsset?.symbol}
            copy={copy}
            key={details.portfolioId}
            locale={locale}
            portfolioId={details.portfolioId}
          />
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
          <ResponsiveRecordList className="account-grid" label={copy.accountRegistry}>
            {selectedAccounts.map((account) => (
              <li className="account-card" key={account.account_id}>
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
              </li>
            ))}
          </ResponsiveRecordList>
        )}
      </section>
    </section>
  );
}
