"use client";

import { CheckCircle2, ShieldCheck } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { type ReactNode, useSyncExternalStore } from "react";

import { AlertInbox } from "@/components/alert-inbox";
import { useWorkspace } from "@/components/authenticated-shell";
import { DecisionExperience } from "@/components/decision-experience";
import { DecisionRecordWorkspace } from "@/components/decision-record-workspace";
import { FirstRunOnboarding } from "@/components/first-run-onboarding";
import { MonitoringNavigation } from "@/components/monitoring-navigation";
import { OutcomeJournalPanel } from "@/components/outcome-journal-panel";
import { PortfolioDashboard } from "@/components/portfolio-dashboard";
import { RegistryManagement } from "@/components/registry-management";
import { TransactionsWorkspace } from "@/components/transactions-workspace";
import { WatchlistPanel } from "@/components/watchlist-panel";
import { hasOnboardingDraft } from "@/lib/first-run-onboarding";
import { journalHref } from "@/lib/monitoring";
import type { DecisionRoute } from "@/lib/decision-intelligence";
import type { AccountingQuery, AccountingView } from "@/lib/portfolio-accounting";

type WorkspaceViewProps =
  | { section: "portfolioDetail"; portfolioId: string }
  | { section: "transactions"; query: AccountingQuery; view: AccountingView }
  | { section: "decisionRecord"; route: DecisionRoute }
  | { section: "alerts"; alertId?: string; decisionId?: string; watchlistId?: string }
  | { section: "watchlists"; watchlistId?: string }
  | { section: "journal"; decisionId?: string }
  | {
      section:
        | "overview"
        | "onboarding"
        | "portfolios"
        | "assets"
        | "accounts"
        | "decisions"
        | "exports"
        | "settings";
    };

function WorkspaceHeading({ title }: { title: string }) {
  const { dictionary } = useWorkspace();
  return (
    <header className="page-heading">
      <h1>{title}</h1>
      <div className="ready-badge">
        <CheckCircle2 aria-hidden="true" size={18} />
        {dictionary.shell.authenticated}
      </div>
    </header>
  );
}

function SecurityBoundary() {
  const { dictionary } = useWorkspace();
  return (
    <section className="boundary-card">
      <div className="boundary-heading">
        <h2>{dictionary.shell.securityTitle}</h2>
        <ShieldCheck aria-hidden="true" size={28} />
      </div>
      <ul className="boundary-list">
        {Object.values(dictionary.shell.securityItems).map((item) => (
          <li key={item}>
            <CheckCircle2 aria-hidden="true" size={18} />
            <span>{item}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}

function ResumeOnboarding() {
  const { dictionary, locale, session } = useWorkspace();
  const hasDraft = useSyncExternalStore(
    () => () => undefined,
    () => hasOnboardingDraft(session.owner_id),
    () => false,
  );
  if (!hasDraft) return null;
  return (
    <div className="onboarding-resume">
      <Link className="secondary-button" href={`/${locale}/onboarding`}>
        {dictionary.onboarding.resumeLink}
      </Link>
    </div>
  );
}

export function WorkspaceView(props: WorkspaceViewProps) {
  const { dictionary, locale, session } = useWorkspace();
  const router = useRouter();
  const copy = dictionary.workspacePages;
  const navigation = dictionary.navigation;
  let title: string;
  let content: ReactNode;

  switch (props.section) {
    case "onboarding":
      title = dictionary.onboarding.title;
      content = (
        <FirstRunOnboarding
          copy={dictionary.onboarding}
          key={session.owner_id}
          locale={locale}
          ownerId={session.owner_id}
        />
      );
      break;
    case "overview":
      title = navigation.overview;
      content = (
        <>
          <ResumeOnboarding />
          <PortfolioDashboard dictionary={dictionary} locale={locale} showDetailsLink />
          <SecurityBoundary />
        </>
      );
      break;
    case "portfolios":
      title = navigation.portfolio;
      content = (
        <>
          <ResumeOnboarding />
          <RegistryManagement
            dictionary={dictionary}
            key={session.owner_id}
            locale={locale}
            section="portfolios"
          />
        </>
      );
      break;
    case "assets":
    case "accounts":
      title = navigation[props.section];
      content = (
        <RegistryManagement
          dictionary={dictionary}
          key={`${session.owner_id}-${props.section}`}
          locale={locale}
          section={props.section}
        />
      );
      break;
    case "portfolioDetail":
      title = copy.portfolioDetails;
      content = (
        <PortfolioDashboard
          dictionary={dictionary}
          locale={locale}
          portfolioId={props.portfolioId}
        />
      );
      break;
    case "transactions":
      title =
        props.view === "journal"
          ? navigation.transactions
          : dictionary.portfolioOperations.tabs[props.view];
      content = (
        <TransactionsWorkspace
          key={JSON.stringify([
            session.owner_id,
            props.view,
            props.query.portfolio,
            props.query.basis,
          ])}
          query={props.query}
          view={props.view}
        />
      );
      break;
    case "decisions":
      title = navigation.decisions;
      content = <DecisionExperience dictionary={dictionary} locale={locale} />;
      break;
    case "decisionRecord":
      title = dictionary.decisionPages.panels[props.route.panel];
      content = (
        <DecisionRecordWorkspace
          key={JSON.stringify([session.owner_id, props.route])}
          route={props.route}
        />
      );
      break;
    case "alerts":
      title = navigation.alerts;
      content = (
        <>
          <MonitoringNavigation
            copy={dictionary.monitoring}
            locale={locale}
            view="alerts"
            watchlist={props.watchlistId}
          />
          <AlertInbox
            alertId={props.alertId}
            decisionId={props.decisionId}
            dictionary={dictionary}
            key={JSON.stringify([
              session.owner_id,
              props.alertId,
              props.decisionId,
              props.watchlistId,
            ])}
            locale={locale}
            watchlistId={props.watchlistId}
          />
        </>
      );
      break;
    case "watchlists":
      title = dictionary.monitoring.watchlists;
      content = (
        <>
          <MonitoringNavigation
            copy={dictionary.monitoring}
            locale={locale}
            view="watchlists"
            watchlist={props.watchlistId}
          />
          <WatchlistPanel
            dictionary={dictionary}
            key={JSON.stringify([session.owner_id, props.watchlistId])}
            locale={locale}
            initialWatchlistId={props.watchlistId}
          />
        </>
      );
      break;
    case "journal":
      title = navigation.journal;
      content = (
        <OutcomeJournalPanel
          decisionId={props.decisionId}
          dictionary={dictionary}
          key={JSON.stringify([session.owner_id, props.decisionId])}
          locale={locale}
          onDecisionSearch={(id) => router.push(journalHref(locale, id))}
        />
      );
      break;
    case "exports":
      title = navigation.exports;
      content = <p className="workspace-page-note">{copy.exportsDescription}</p>;
      break;
    case "settings":
      title = navigation.settings;
      content = <p className="workspace-page-note">{copy.settingsDescription}</p>;
      break;
  }
  return (
    <>
      <WorkspaceHeading title={title} />
      {content}
    </>
  );
}
