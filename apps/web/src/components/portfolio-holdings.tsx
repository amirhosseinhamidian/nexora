import { EmptyState, Table } from "@nexora/ui/primitives";

import type {
  PortfolioWorkspaceAccount,
  PortfolioWorkspaceAsset,
} from "@/components/portfolio-dashboard";
import { WorkspaceTime } from "@/components/workspace-time";
import type { Locale } from "@/i18n/config";
import type { Dictionary } from "@/i18n/dictionaries";
import {
  formatExactDecimal,
  formatExactQuantity,
  type PositionValuation,
} from "@/lib/portfolio-analytics";

export function PortfolioHoldings({
  accounts,
  assets,
  basePrecision,
  baseSymbol,
  dictionary,
  locale,
  positions,
}: {
  accounts: PortfolioWorkspaceAccount[];
  assets: Map<string, PortfolioWorkspaceAsset>;
  basePrecision?: number;
  baseSymbol?: string;
  dictionary: Dictionary;
  locale: Locale;
  positions: PositionValuation[];
}) {
  const dashboard = dictionary.portfolioDashboard;
  const copy = dashboard.holdings;
  const accountNames = new Map(accounts.map((account) => [account.account_id, account.name]));

  if (!positions.length) {
    return (
      <EmptyState className="portfolio-analysis-section" title={copy.title}>
        {copy.empty}
      </EmptyState>
    );
  }

  return (
    <section
      className="dashboard-card portfolio-analysis-section"
      aria-labelledby="portfolio-holdings-title"
    >
      <h3 id="portfolio-holdings-title">{copy.title}</h3>
      <p className="card-footnote">{copy.description}</p>
      <Table className="portfolio-analysis-table">
        <caption className="sr-only">{copy.title}</caption>
        <thead>
          <tr>
            <th scope="col">{dashboard.allocationAsset}</th>
            <th scope="col">{copy.account}</th>
            <th scope="col">{copy.quantity}</th>
            <th scope="col">{copy.value}</th>
            <th scope="col">{dashboard.valuationHealth}</th>
            <th scope="col">{copy.evidenceAt}</th>
            <th scope="col">{copy.costBasis}</th>
          </tr>
        </thead>
        <tbody>
          {positions.map((position) => {
            const asset = assets.get(position.asset_id);
            const account = accountNames.get(position.account_id);
            return (
              <tr key={`${position.account_id}:${position.asset_id}`}>
                <th scope="row">
                  <bdi>{asset?.name ?? position.asset_id}</bdi>{" "}
                  {asset?.symbol ? <bdi dir="ltr">{asset.symbol}</bdi> : null}
                </th>
                <td>
                  <bdi>{account ?? position.account_id}</bdi>
                </td>
                <td>
                  <bdi dir="ltr">{formatExactQuantity(position.quantity, locale)}</bdi>
                </td>
                <td>
                  {position.market_value === null ? (
                    dashboard.unavailable
                  ) : (
                    <bdi dir="ltr">
                      {formatExactDecimal(position.market_value, locale, basePrecision)}{" "}
                      {baseSymbol}
                    </bdi>
                  )}
                </td>
                <td>
                  <span className="valuation-label" data-state={position.state}>
                    {dashboard.valuationState[position.state]}
                  </span>
                </td>
                <td>
                  {position.evidence_at ? (
                    <WorkspaceTime dateTime={position.evidence_at} locale={locale} />
                  ) : (
                    dashboard.unavailable
                  )}
                </td>
                <td>{copy.basisStates[position.basis_status]}</td>
              </tr>
            );
          })}
        </tbody>
      </Table>
    </section>
  );
}
