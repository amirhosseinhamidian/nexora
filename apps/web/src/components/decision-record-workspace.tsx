"use client";

import { Alert, Button, EmptyState, ErrorState, Spinner } from "@nexora/ui/primitives";
import Link from "next/link";
import { useEffect, useState } from "react";

import { useWorkspace } from "@/components/authenticated-shell";
import { EvidencePanel } from "@/components/decision-evidence";
import { DecisionScenarios, PortfolioImpactPanel } from "@/components/decision-impact";
import { DecisionReviewPanel } from "@/components/decision-review";
import { RiskGatePanel } from "@/components/decision-risk";
import {
  decisionHref,
  decisionPanels,
  loadDecisionRecord,
  type DecisionRecord,
  type DecisionRoute,
} from "@/lib/decision-intelligence";

export function DecisionRecordWorkspace({ route }: { route: DecisionRoute }) {
  const { dictionary, locale } = useWorkspace();
  const copy = dictionary.decisionPages;
  const feed = dictionary.decisionFeed;
  const [revision, setRevision] = useState(0);
  const [result, setResult] = useState<{ revision: number; record?: DecisionRecord }>();
  const record = result?.revision === revision ? result?.record : undefined;

  useEffect(() => {
    const controller = new AbortController();
    void loadDecisionRecord(route, controller.signal).then(
      (value) => {
        if (!controller.signal.aborted) setResult({ revision, record: value });
      },
      () => {
        if (!controller.signal.aborted) setResult({ revision });
      },
    );
    return () => controller.abort();
  }, [revision, route]);

  return (
    <section className="decision-record-page">
      <Link className="secondary-button decision-open-record" href={`/${locale}/decisions`}>
        {copy.backToFeed}
      </Link>
      <nav aria-label={copy.navigation} className="accounting-navigation">
        {decisionPanels.map((panel) => (
          <Link
            aria-current={panel === route.panel ? "page" : undefined}
            href={decisionHref(locale, { ...route, panel })}
            key={panel}
          >
            {copy.panels[panel]}
          </Link>
        ))}
      </nav>
      {result?.revision !== revision ? (
        <Alert className="inline-state" role="status">
          <Spinner label="" /> {feed.loadingDetail}
        </Alert>
      ) : null}
      {result?.revision === revision && !record ? (
        <ErrorState
          title={feed.error}
          action={
            <Button onClick={() => setRevision((value) => value + 1)} variant="secondary">
              {feed.retry}
            </Button>
          }
        />
      ) : null}
      {record?.provider && record.provider.state !== "ready" ? (
        <Alert tone="warning" className="provider-state">
          {feed.providerStates[record.provider.state]}
        </Alert>
      ) : null}
      {record ? (
        <div className="decision-record-content">
          {!record.item ? <EmptyState title={copy.evidenceUnavailable} /> : null}
          {record.item && route.panel !== "evidence" ? (
            <p className="decision-context">
              {feed.resourceTypes[record.item.resource_type]}{" "}
              <code dir="ltr">{record.item.resource_id}</code>
            </p>
          ) : null}
          {record.item && route.panel === "evidence" ? (
            <>
              <EvidencePanel copy={feed} item={record.item} locale={locale} />
              {route.kind === "candidates" && record.decisionId ? (
                <Link
                  className="secondary-button decision-open-record"
                  href={decisionHref(locale, {
                    kind: "records",
                    panel: "evidence",
                    resourceId: record.decisionId,
                  })}
                >
                  {copy.openLinkedDecision}
                </Link>
              ) : null}
            </>
          ) : null}
          {record.item && route.panel === "risk" ? (
            <RiskGatePanel
              dictionary={dictionary}
              locale={locale}
              riskGate={record.riskGate ?? null}
            />
          ) : null}
          {record.item && route.panel === "impact" ? (
            <PortfolioImpactPanel
              dictionary={dictionary}
              impact={record.portfolioImpact ?? null}
              locale={locale}
            />
          ) : null}
          {record.item && route.panel === "scenarios" ? (
            <DecisionScenarios
              impact={record.portfolioImpact ?? null}
              copy={copy}
              locale={locale}
            />
          ) : null}
          {route.panel === "reviews" ? (
            <DecisionReviewPanel
              context={record.reviewContext ?? null}
              decisionId={record.decisionId}
              dictionary={dictionary}
              generation={record.item ? (record.provider?.generation ?? undefined) : undefined}
              locale={locale}
              onReloadEvidence={() => setRevision((value) => value + 1)}
              sourceChecksum={
                record.item?.resource_type === "decision_evaluation"
                  ? record.item.source.checksum
                  : undefined
              }
            />
          ) : null}
        </div>
      ) : null}
    </section>
  );
}
