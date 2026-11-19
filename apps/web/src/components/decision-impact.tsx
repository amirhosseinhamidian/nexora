import { Alert, ChartContainer, ComparisonBlock, EmptyState, Table } from "@nexora/ui/primitives";
import type { CSSProperties } from "react";

import { DecisionPolicyChecks } from "@/components/decision-policy-checks";
import type { Locale } from "@/i18n/config";
import type { Dictionary } from "@/i18n/dictionaries";
import type { PortfolioImpact } from "@/lib/decision-intelligence";
import { exactDecimal } from "@/lib/portfolio-accounting";
import { formatTimestamp } from "@/lib/portfolio-analytics";

export function PortfolioImpactPanel({
  dictionary,
  impact,
  locale,
}: {
  dictionary: Dictionary;
  impact: PortfolioImpact | null;
  locale: Locale;
}) {
  const copy = dictionary.decisionFeed;
  const labels = dictionary.decisionPages;
  if (!impact) return <EmptyState title={copy.portfolioImpactUnavailable} />;
  const analysis = impact.analysis;
  const amount = (value: string | null) => <bdi dir="ltr">{exactDecimal(value, locale)}</bdi>;

  return (
    <section className="risk-explanation portfolio-impact" aria-label={copy.portfolioImpactTitle}>
      <div className="risk-heading">
        <h2>{copy.portfolioImpactTitle}</h2>
        <span className={`risk-decision ${impact.recommendation}`}>
          {copy.portfolioRecommendations[impact.recommendation]}
        </span>
      </div>
      <p className="advisory-boundary">{copy.portfolioImpactBoundary}</p>
      {analysis ? (
        <>
          <dl className="portfolio-impact-summary">
            <div>
              <dt>{copy.snapshotMode}</dt>
              <dd>{labels.modes[analysis.snapshot.mode]}</dd>
            </div>
            <div>
              <dt>{copy.snapshotSource}</dt>
              <dd>{labels.snapshotSources[analysis.snapshot.source]}</dd>
            </div>
            <div>
              <dt>{labels.snapshotAt}</dt>
              <dd>
                <time dateTime={analysis.snapshot.as_of}>
                  {formatTimestamp(analysis.snapshot.as_of, locale)}
                </time>
              </dd>
            </div>
            <div>
              <dt>{copy.projectedConcentration}</dt>
              <dd>{amount(analysis.exposure.projected_asset_concentration_fraction)}</dd>
            </div>
            <div>
              <dt>{copy.correlation}</dt>
              <dd>
                {labels.correlationStates[analysis.correlation.status]} ·{" "}
                {amount(analysis.correlation.maximum_absolute_correlation)}
                <small>{analysis.correlation.evidence}</small>
              </dd>
            </div>
          </dl>
          <ComparisonBlock
            title={labels.exposure}
            beforeLabel={labels.current}
            before={amount(analysis.exposure.current_exposure_fraction)}
            afterLabel={labels.projected}
            after={amount(analysis.exposure.projected_exposure_fraction)}
          />
          <ComparisonBlock
            title={labels.notional}
            beforeLabel={labels.current}
            before={amount(analysis.exposure.current_gross_notional)}
            afterLabel={labels.projected}
            after={amount(analysis.exposure.projected_gross_notional)}
          />
          <DecisionPolicyChecks
            checks={analysis.checks}
            dictionary={dictionary}
            locale={locale}
            title={copy.portfolioChecks}
          />
        </>
      ) : (
        <p>{copy.portfolioAnalysisUnavailable}</p>
      )}
      <dl className="risk-policy-grid">
        <div>
          <dt>{copy.policyVersion}</dt>
          <dd dir="ltr">{impact.policy.version}</dd>
        </div>
        <div>
          <dt>{copy.evaluatedAt}</dt>
          <dd>
            <time dateTime={impact.analyzed_at}>{formatTimestamp(impact.analyzed_at, locale)}</time>
          </dd>
        </div>
        <div className="wide">
          <dt>{copy.policyChecksum}</dt>
          <dd className="checksum" dir="ltr">
            {impact.policy.checksum}
          </dd>
        </div>
      </dl>
      {impact.provider_reason_codes.length ? (
        <>
          <h3>{copy.providerReasons}</h3>
          <ul className="risk-reasons">
            {impact.provider_reason_codes.map((reason) => (
              <li key={reason.code}>
                <code dir="ltr">{reason.code}</code>
              </li>
            ))}
          </ul>
        </>
      ) : null}
      <Alert tone="warning" className="risk-uncertainty" role="status">
        <strong>{copy.uncertainty}</strong>
        <p>{copy.uncertaintyNotSupplied}</p>
        <code dir="ltr">{impact.uncertainty.reason_code}</code>
      </Alert>
    </section>
  );
}

export function DecisionScenarios({
  copy,
  impact,
  locale,
}: {
  copy: Dictionary["decisionPages"];
  impact: PortfolioImpact | null;
  locale: Locale;
}) {
  const analysis = impact?.analysis;
  if (!analysis?.scenarios.length) return <EmptyState title={copy.scenariosUnavailable} />;

  const losses = analysis.scenarios.map((scenario) => Number(scenario.loss_fraction));
  const maxLoss = losses.reduce(
    (max, loss) => (Number.isFinite(loss) ? Math.max(max, loss) : max),
    0,
  );
  const amount = (value: string) => <bdi dir="ltr">{exactDecimal(value, locale)}</bdi>;
  const table = (
    <Table aria-label={copy.panels.scenarios}>
      <thead>
        <tr>
          {[
            copy.shock,
            copy.existingPnl,
            copy.candidatePnl,
            copy.projectedEquity,
            copy.lossFraction,
          ].map((label) => (
            <th key={label} scope="col">
              {label}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {analysis.scenarios.map((scenario) => (
          <tr key={scenario.shock_fraction}>
            <th scope="row">{amount(scenario.shock_fraction)}</th>
            <td>{amount(scenario.existing_pnl)}</td>
            <td>{amount(scenario.candidate_pnl)}</td>
            <td>{amount(scenario.projected_equity)}</td>
            <td>{amount(scenario.loss_fraction)}</td>
          </tr>
        ))}
      </tbody>
    </Table>
  );
  const canChart = maxLoss > 0 && losses.every((value) => Number.isFinite(value) && value >= 0);
  return (
    <section className="decision-scenarios">
      <p>{copy.scenarioDescription}</p>
      {canChart ? (
        <ChartContainer
          description={copy.lossChartDescription}
          table={table}
          title={copy.lossChartTitle}
        >
          <ul className="decision-scenario-bars">
            {analysis.scenarios.map((scenario, index) => (
              <li key={scenario.shock_fraction}>
                <span>{amount(scenario.shock_fraction)}</span>
                <div className="decision-scenario-track">
                  <div
                    className="decision-scenario-bar"
                    style={
                      { "--scenario-width": `${(losses[index] / maxLoss) * 100}%` } as CSSProperties
                    }
                  />
                </div>
                <span>{amount(scenario.loss_fraction)}</span>
              </li>
            ))}
          </ul>
        </ChartContainer>
      ) : (
        table
      )}
    </section>
  );
}
