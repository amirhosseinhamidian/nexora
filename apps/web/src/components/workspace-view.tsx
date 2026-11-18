"use client";

import { CheckCircle2, ShieldCheck } from "lucide-react";
import Link from "next/link";
import { type ReactNode, useState, useSyncExternalStore } from "react";

import { AlertInbox } from "@/components/alert-inbox";
import { useWorkspace } from "@/components/authenticated-shell";
import { DecisionExperience } from "@/components/decision-experience";
import { FirstRunOnboarding } from "@/components/first-run-onboarding";
import { OutcomeJournalPanel } from "@/components/outcome-journal-panel";
import {
  PortfolioDashboard,
  type PortfolioWorkspaceContext,
} from "@/components/portfolio-dashboard";
import { PortfolioOperations } from "@/components/portfolio-operations";
import { WatchlistPanel } from "@/components/watchlist-panel";
import { hasOnboardingDraft } from "@/lib/first-run-onboarding";

type WorkspaceViewProps =
  | { section: "portfolioDetail"; portfolioId: string }
  | {
      section:
        | "overview"
        | "onboarding"
        | "portfolios"
        | "transactions"
        | "decisions"
        | "alerts"
        | "journal"
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

function TransactionsWorkspace() {
  const { dictionary, locale, session } = useWorkspace();
  const [portfolioContext, setPortfolioContext] = useState<PortfolioWorkspaceContext>();
  return (
    <>
      <PortfolioDashboard
        dictionary={dictionary}
        locale={locale}
        onWorkspaceChange={setPortfolioContext}
        selectionOnly
      />
      <PortfolioOperations
        context={portfolioContext}
        dictionary={dictionary}
        locale={locale}
        recentlyReauthenticated={session.recently_reauthenticated}
      />
    </>
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
          <PortfolioDashboard dictionary={dictionary} locale={locale} showDetailsLink />
        </>
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
      title = navigation.transactions;
      content = <TransactionsWorkspace />;
      break;
    case "decisions":
      title = navigation.decisions;
      content = <DecisionExperience dictionary={dictionary} locale={locale} />;
      break;
    case "alerts":
      title = navigation.alerts;
      content = (
        <>
          <AlertInbox dictionary={dictionary} locale={locale} />
          <WatchlistPanel dictionary={dictionary} locale={locale} />
        </>
      );
      break;
    case "journal":
      title = navigation.journal;
      content = <OutcomeJournalPanel dictionary={dictionary} locale={locale} />;
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
