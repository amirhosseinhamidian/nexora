"use client";

import Link from "next/link";
import { useState } from "react";

import { useWorkspace } from "@/components/authenticated-shell";
import {
  PortfolioDashboard,
  type PortfolioWorkspaceContext,
} from "@/components/portfolio-dashboard";
import { PortfolioOperations } from "@/components/portfolio-operations";
import {
  accountingHref,
  accountingViews,
  needsAccountingPortfolio,
  type AccountingQuery,
  type AccountingView,
  type CostBasisMethod,
} from "@/lib/portfolio-accounting";

export function TransactionsWorkspace({
  query,
  view,
}: {
  query: AccountingQuery;
  view: AccountingView;
}) {
  const { dictionary, locale, reauthenticate, refreshSession, session } = useWorkspace();
  const initialPortfolio = typeof query.portfolio === "string" ? query.portfolio : undefined;
  const [context, setContext] = useState<PortfolioWorkspaceContext>();
  const [basis, setBasis] = useState<CostBasisMethod>(
    query.basis === "weighted_average" ? "weighted_average" : "fifo",
  );
  const portfolio = context?.portfolioId ?? initialPortfolio;
  const copy = dictionary.portfolioOperations;

  function choosePortfolio(id: string) {
    window.history.replaceState(null, "", accountingHref(locale, view, id, basis));
  }

  function chooseBasis(method: CostBasisMethod) {
    setBasis(method);
    window.history.replaceState(null, "", accountingHref(locale, view, portfolio, method));
  }

  return (
    <>
      <nav aria-label={copy.tabs.label} className="accounting-navigation">
        {accountingViews.map((item) => (
          <Link
            aria-current={view === item ? "page" : undefined}
            href={accountingHref(locale, item, portfolio, basis)}
            key={item}
          >
            {copy.tabs[item]}
          </Link>
        ))}
      </nav>
      {needsAccountingPortfolio(view) ? (
        <PortfolioDashboard
          dictionary={dictionary}
          initialSelectionId={initialPortfolio}
          locale={locale}
          onPortfolioSelect={choosePortfolio}
          onWorkspaceChange={setContext}
          selectionOnly
        />
      ) : null}
      <PortfolioOperations
        basis={basis}
        context={context}
        dictionary={dictionary}
        key={JSON.stringify([view, context?.portfolioId, basis])}
        locale={locale}
        onBasisChange={chooseBasis}
        onReauthenticate={reauthenticate}
        onRefreshSession={refreshSession}
        recentlyReauthenticated={session.recently_reauthenticated}
        view={view}
      />
    </>
  );
}
