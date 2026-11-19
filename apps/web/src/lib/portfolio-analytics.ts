import type { Locale } from "@/i18n/config";

export type ValuationState = "fresh" | "missing" | "stale";
export type PositionValuation = {
  account_id: string;
  asset_id: string;
  quantity: string;
  market_value: string | null;
  basis_status: "known" | "mixed" | "unknown";
  evidence_at: string | null;
  state: ValuationState;
};

export type PerformancePoint = {
  as_of: string;
  nav: string | null;
  external_flow: string | null;
  period_return: string | null;
  cumulative_return: string | null;
  state: "available" | "stale" | "unavailable";
  reason_code: string | null;
};

export type PerformanceSeries = {
  start_at: string;
  end_at: string;
  points: PerformancePoint[];
};

export const performancePeriods = {
  week: { days: 7, sampleCount: 8 },
  month: { days: 30, sampleCount: 11 },
  quarter: { days: 90, sampleCount: 13 },
} as const;
export type PerformancePeriod = keyof typeof performancePeriods;

export function performancePath(
  portfolioId: string,
  asOf: string,
  period: PerformancePeriod,
): string {
  const { days, sampleCount } = performancePeriods[period];
  const start = new Date(Date.parse(asOf) - days * 86_400_000);
  const query = new URLSearchParams({
    start_at: start.toISOString(),
    end_at: asOf,
    point_count: String(sampleCount),
  });
  return `/api/v1/portfolios/${encodeURIComponent(portfolioId)}/performance?${query}`;
}

type ExactDecimal = { scale: number; units: bigint };

export function parseDecimal(value: string): ExactDecimal {
  const match = /^(-?)(0|[1-9][0-9]*)(?:\.([0-9]+))?$/.exec(value);
  if (!match) throw new Error("invalid canonical decimal");
  const fraction = match[3] ?? "";
  const units = BigInt(`${match[2]}${fraction}`) * (match[1] === "-" ? -1n : 1n);
  return { scale: fraction.length, units };
}

function powerOfTen(exponent: number): bigint {
  return 10n ** BigInt(exponent);
}

export function align(value: ExactDecimal, scale: number): bigint {
  return value.units * powerOfTen(scale - value.scale);
}

export function addExact(left: ExactDecimal, right: ExactDecimal): ExactDecimal {
  const scale = Math.max(left.scale, right.scale);
  return { scale, units: align(left, scale) + align(right, scale) };
}

export function compareExact(left: ExactDecimal, right: ExactDecimal): number {
  const scale = Math.max(left.scale, right.scale);
  const difference = align(left, scale) - align(right, scale);
  return difference < 0n ? -1 : difference > 0n ? 1 : 0;
}

export function localizeDigits(value: string, locale: Locale): string {
  if (locale === "en") return value;
  return value.replace(/[0-9]/g, (digit) => "۰۱۲۳۴۵۶۷۸۹"[Number(digit)]);
}

function formatDecimal(value: ExactDecimal, locale: Locale, fractionDigits: number): string {
  const negative = value.units < 0n;
  let absolute = negative ? -value.units : value.units;
  if (value.scale > fractionDigits) {
    const divisor = powerOfTen(value.scale - fractionDigits);
    const remainder = absolute % divisor;
    absolute /= divisor;
    if (remainder * 2n >= divisor) absolute += 1n;
  } else {
    absolute *= powerOfTen(fractionDigits - value.scale);
  }
  const scaleDivisor = powerOfTen(fractionDigits);
  const integer = absolute / scaleDivisor;
  const fraction =
    fractionDigits === 0 ? "" : (absolute % scaleDivisor).toString().padStart(fractionDigits, "0");
  const grouped = integer.toString().replace(/\B(?=(\d{3})+(?!\d))/g, locale === "fa" ? "٬" : ",");
  const decimal = fraction ? `${locale === "fa" ? "٫" : "."}${fraction}` : "";
  return localizeDigits(`${negative ? "−" : ""}${grouped}${decimal}`, locale);
}

export function formatExactDecimal(
  value: string | null,
  locale: Locale,
  fractionDigits = 2,
): string {
  return value === null ? "—" : formatDecimal(parseDecimal(value), locale, fractionDigits);
}

export function formatExactQuantity(value: string, locale: Locale): string {
  const decimal = parseDecimal(value);
  return formatDecimal(decimal, locale, decimal.scale);
}

export function formatExactPercent(value: string | null, locale: Locale): string {
  return value === null ? "—" : formatPercent(parseDecimal(value), locale);
}

function formatPercent(value: ExactDecimal, locale: Locale): string {
  const scaled = { units: value.units * 100n, scale: value.scale };
  return `${formatDecimal(scaled, locale, 2)}${locale === "fa" ? "٪" : "%"}`;
}

export function formatTimestamp(value: string, locale: Locale, timeZone?: string): string {
  return new Intl.DateTimeFormat(locale === "fa" ? "fa-IR" : "en-GB", {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone,
  }).format(new Date(value));
}

export const performanceViewBox = { width: 600, height: 200 } as const;

export function performancePlot(points: PerformancePoint[], locale: Locale) {
  const samples = points.map((point) =>
    point.cumulative_return === null || point.state === "unavailable"
      ? undefined
      : parseDecimal(point.cumulative_return),
  );
  if (!samples.some(Boolean)) return undefined;
  const scale = samples.reduce((largest, value) => Math.max(largest, value?.scale ?? 0), 0);
  const normalized = samples.map((value) => (value ? align(value, scale) : undefined));
  const { min, max } = normalized.reduce(
    (range, value) => {
      if (value === undefined) return range;
      return {
        min: value < range.min ? value : range.min,
        max: value > range.max ? value : range.max,
      };
    },
    { min: 0n, max: 0n },
  );
  const inset = 12;
  const width = performanceViewBox.width - inset * 2;
  const height = performanceViewBox.height - inset * 2;
  const span = max - min;
  // Limit the conversion to bounded pixel coordinates. Keep measurement and labels exact.
  const toY = (value: bigint) =>
    span === 0n
      ? inset + height / 2
      : inset + (Number(((max - value) * 1000n) / span) * height) / 1000;
  return {
    samples: normalized.map((value, index) =>
      value === undefined
        ? undefined
        : {
            x: inset + (index * width) / Math.max(1, points.length - 1),
            y: toY(value),
            stale: points[index].state === "stale",
          },
    ),
    zeroY: toY(0n),
    maximum: formatPercent({ units: max, scale }, locale),
    minimum: formatPercent({ units: min, scale }, locale),
  };
}
