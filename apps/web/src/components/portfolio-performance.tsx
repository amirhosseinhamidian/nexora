"use client";

import {
  Alert,
  Button,
  ChartContainer,
  ChartLegend,
  ComparisonBlock,
  Disclosure,
  EmptyState,
  ErrorState,
  FormField,
  Select,
  Spinner,
  Table,
} from "@nexora/ui/primitives";
import { useEffect, useId, useState } from "react";

import type { Locale } from "@/i18n/config";
import type { Dictionary } from "@/i18n/dictionaries";
import { apiRequest } from "@/lib/api-client";
import {
  formatExactDecimal,
  formatExactPercent,
  formatTimestamp,
  performancePath,
  performancePeriods,
  performancePlot,
  performanceViewBox,
  type PerformancePeriod,
  type PerformancePoint,
  type PerformanceSeries,
} from "@/lib/portfolio-analytics";

type DashboardCopy = Dictionary["portfolioDashboard"];
type PerformanceCopy = DashboardCopy["performance"];

function pointReason(point: PerformancePoint, copy: PerformanceCopy): string | undefined {
  switch (point.reason_code) {
    case "MISSING_NAV":
      return copy.reasons.missingValue;
    case "MISSING_EXTERNAL_FLOW_VALUATION":
      return copy.reasons.missingFlow;
    case "ZERO_START_NAV":
      return copy.reasons.zeroStart;
    default:
      return point.cumulative_return === null && point.period_return !== null
        ? copy.reasons.incompleteHistory
        : undefined;
  }
}

function PerformanceTable({
  basePrecision,
  baseSymbol,
  copy,
  locale,
  points,
}: {
  basePrecision?: number;
  baseSymbol?: string;
  copy: DashboardCopy;
  locale: Locale;
  points: PerformancePoint[];
}) {
  const performance = copy.performance;
  const money = (value: string | null) =>
    value === null ? (
      copy.unavailable
    ) : (
      <bdi dir="ltr">
        {formatExactDecimal(value, locale, basePrecision)} {baseSymbol}
      </bdi>
    );
  const rate = (value: string | null) =>
    value === null ? copy.unavailable : <bdi dir="ltr">{formatExactPercent(value, locale)}</bdi>;

  return (
    <Disclosure className="portfolio-chart-data" label={performance.showData}>
      <Table className="portfolio-analysis-table">
        <caption className="sr-only">{performance.dataTable}</caption>
        <thead>
          <tr>
            <th scope="col">{performance.date}</th>
            <th scope="col">{copy.nav}</th>
            <th scope="col">{performance.externalFlow}</th>
            <th scope="col">{performance.periodReturn}</th>
            <th scope="col">{performance.cumulativeReturn}</th>
            <th scope="col">{performance.state}</th>
          </tr>
        </thead>
        <tbody>
          {points.map((point, index) => {
            const reason = pointReason(point, performance);
            return (
              <tr key={point.as_of}>
                <th scope="row">
                  <time dateTime={point.as_of}>{formatTimestamp(point.as_of, locale)}</time>
                </th>
                <td>{money(point.nav)}</td>
                <td>{index === 0 ? "—" : money(point.external_flow)}</td>
                <td>{index === 0 ? "—" : rate(point.period_return)}</td>
                <td>{rate(point.cumulative_return)}</td>
                <td>
                  <span className="valuation-label" data-state={point.state}>
                    {performance.states[point.state]}
                  </span>
                  {reason ? <span className="performance-reason">{reason}</span> : null}
                </td>
              </tr>
            );
          })}
        </tbody>
      </Table>
    </Disclosure>
  );
}

function PerformanceChart({
  copy,
  locale,
  points,
  startAt,
  endAt,
}: {
  copy: PerformanceCopy;
  locale: Locale;
  points: PerformancePoint[];
  startAt: string;
  endAt: string;
}) {
  const plot = performancePlot(points, locale);
  if (!plot) return null;

  const date = new Intl.DateTimeFormat(locale === "fa" ? "fa-IR" : "en-GB", {
    dateStyle: "medium",
  });
  return (
    <>
      <div className="performance-chart-bounds" dir="ltr">
        <bdi>{plot.maximum}</bdi>
      </div>
      <svg
        className="performance-chart"
        data-performance-plot=""
        preserveAspectRatio="none"
        viewBox={`0 0 ${performanceViewBox.width} ${performanceViewBox.height}`}
      >
        <line
          className="performance-chart-zero"
          vectorEffect="non-scaling-stroke"
          x1={0}
          x2={performanceViewBox.width}
          y1={plot.zeroY}
          y2={plot.zeroY}
        />
        {plot.samples.map((sample, index) => {
          const previous = plot.samples[index - 1];
          if (!sample || !previous) return null;
          return (
            <line
              className="performance-chart-line"
              data-stale={sample.stale || previous.stale || undefined}
              key={points[index].as_of}
              vectorEffect="non-scaling-stroke"
              x1={previous.x}
              x2={sample.x}
              y1={previous.y}
              y2={sample.y}
            />
          );
        })}
        {plot.samples.map((sample, index) =>
          sample ? (
            <circle
              className="performance-chart-point"
              cx={sample.x}
              cy={sample.y}
              data-stale={sample.stale || undefined}
              key={points[index].as_of}
              r={4}
            />
          ) : null,
        )}
      </svg>
      <div className="performance-chart-bounds" dir="ltr">
        <bdi>{plot.minimum}</bdi>
      </div>
      <div className="performance-chart-bounds" dir="ltr">
        <time dateTime={startAt}>{date.format(new Date(startAt))}</time>
        <time dateTime={endAt}>{date.format(new Date(endAt))}</time>
      </div>
      <ChartLegend
        label={copy.state}
        items={[
          { id: "available", label: copy.states.available, color: "var(--nx-primary-strong)" },
          { id: "stale", label: copy.states.stale, color: "var(--nx-warning)" },
        ]}
      />
    </>
  );
}

export function PortfolioPerformance({
  asOf,
  basePrecision,
  baseSymbol,
  copy,
  locale,
  portfolioId,
}: {
  asOf: string;
  basePrecision?: number;
  baseSymbol?: string;
  copy: DashboardCopy;
  locale: Locale;
  portfolioId: string;
}) {
  const id = useId();
  const performance = copy.performance;
  const [period, setPeriod] = useState<PerformancePeriod>("month");
  const [revision, setRevision] = useState(0);
  const [result, setResult] = useState<{
    path: string;
    revision: number;
    series: PerformanceSeries | null;
  }>();
  const path = performancePath(portfolioId, asOf, period);
  const current = result?.path === path && result.revision === revision ? result : undefined;

  useEffect(() => {
    const controller = new AbortController();
    void apiRequest<PerformanceSeries>(path, { signal: controller.signal }).then(
      (series) => {
        if (!controller.signal.aborted) setResult({ path, revision, series });
      },
      () => {
        if (!controller.signal.aborted) setResult({ path, revision, series: null });
      },
    );
    return () => controller.abort();
  }, [path, revision]);

  const points = current?.series?.points ?? [];
  const first = points[0];
  const last = points.at(-1);
  const hasReturn = points
    .slice(1)
    .some((point) => point.cumulative_return !== null && point.state !== "unavailable");

  const snapshotValue = (point: PerformancePoint) => (
    <>
      {point.nav === null ? (
        copy.unavailable
      ) : (
        <bdi dir="ltr">
          {formatExactDecimal(point.nav, locale, basePrecision)} {baseSymbol}
        </bdi>
      )}
      <time dateTime={point.as_of}>{formatTimestamp(point.as_of, locale)}</time>
    </>
  );

  return (
    <section
      aria-labelledby={`${id}-performance`}
      className="portfolio-analysis-section portfolio-performance"
    >
      <header className="portfolio-performance-toolbar">
        <h3 id={`${id}-performance`}>{performance.title}</h3>
        <FormField id={`${id}-range`} label={performance.range}>
          <Select
            id={`${id}-range`}
            onValueChange={(value) => {
              if (value !== "week" && value !== "month" && value !== "quarter") return;
              setPeriod(value);
              setRevision((currentRevision) => currentRevision + 1);
            }}
            options={Object.keys(performancePeriods).map((key) => ({
              value: key,
              label: performance.periods[key as PerformancePeriod],
            }))}
            value={period}
          />
        </FormField>
      </header>
      {!current ? (
        <Spinner label={performance.loading} />
      ) : !current.series ? (
        <ErrorState
          title={performance.error}
          action={
            <Button onClick={() => setRevision((value) => value + 1)} variant="secondary">
              {copy.retry}
            </Button>
          }
        >
          {performance.retryHint}
        </ErrorState>
      ) : !first || !last ? (
        <EmptyState title={performance.emptyTitle}>{performance.emptyDescription}</EmptyState>
      ) : (
        <>
          <ComparisonBlock
            after={snapshotValue(last)}
            afterLabel={performance.endValue}
            before={snapshotValue(first)}
            beforeLabel={performance.startValue}
            title={performance.comparison}
          />
          {!hasReturn ? (
            <Alert tone="warning">{performance.unavailableReturn}</Alert>
          ) : last.cumulative_return === null ? (
            <Alert tone="warning">{performance.partialReturn}</Alert>
          ) : null}
          <ChartContainer
            className="portfolio-performance-chart"
            description={performance.description}
            table={
              <PerformanceTable
                basePrecision={basePrecision}
                baseSymbol={baseSymbol}
                copy={copy}
                locale={locale}
                points={points}
              />
            }
            title={performance.cumulativeReturn}
          >
            {hasReturn ? (
              <PerformanceChart
                copy={performance}
                endAt={current.series.end_at}
                locale={locale}
                points={points}
                startAt={current.series.start_at}
              />
            ) : null}
          </ChartContainer>
        </>
      )}
    </section>
  );
}
