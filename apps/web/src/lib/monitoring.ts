import type { Locale } from "@/i18n/config";
import { ApiRequestError } from "@/lib/api-client";
import type { ProviderStatus } from "@/lib/decision-intelligence";

export type AlertSeverity = "info" | "warning" | "critical";
export type MonitoringPreferences = {
  presentation_order: "newest_first" | "oldest_first" | "severity_desc";
  minimum_severity: AlertSeverity;
  include_resolved: boolean;
};

const severityRank: Record<AlertSeverity, number> = { info: 1, warning: 2, critical: 3 };

export function monitoringId(value?: unknown): string | undefined {
  if (typeof value !== "string") return undefined;
  const id = value.trim();
  return id && id.length <= 160 && !/[\u0000-\u001f\u007f]/.test(id) ? id : undefined;
}

export function alertDecisionId(evidence: Record<string, unknown>) {
  const evaluation = monitoringId(evidence.evaluation_id);
  const decision = monitoringId(evidence.decision_id);
  if (evaluation && decision && evaluation !== decision) return undefined;
  return evaluation ?? decision;
}

export function alertSeverity(value: unknown): AlertSeverity | undefined {
  return value === "info" || value === "warning" || value === "critical" ? value : undefined;
}

export function visibleAlerts<
  T extends {
    local_state: string;
    evidence: Record<string, unknown>;
    source: { observed_at: string };
  },
>(items: T[], preferences: MonitoringPreferences): T[] {
  const rank = (item: T) => {
    const severity = alertSeverity(item.evidence.severity);
    return severity ? severityRank[severity] : 0;
  };
  return items
    .filter(
      (item) =>
        (preferences.include_resolved || item.local_state !== "resolved") &&
        rank(item) >= severityRank[preferences.minimum_severity],
    )
    .sort((a, b) => {
      const newest = Date.parse(b.source.observed_at) - Date.parse(a.source.observed_at);
      if (preferences.presentation_order === "oldest_first") return -newest;
      if (preferences.presentation_order === "severity_desc") return rank(b) - rank(a) || newest;
      return newest;
    });
}

export function alertsHref(
  locale: Locale,
  filters: { alert?: string; decision?: string; watchlist?: string } = {},
) {
  const query = new URLSearchParams();
  if (filters.watchlist) query.set("watchlist", filters.watchlist);
  if (filters.alert) query.set("alert", filters.alert);
  if (filters.decision) query.set("decision", filters.decision);
  return `/${locale}/alerts${query.size ? `?${query}` : ""}`;
}

export function watchlistsHref(locale: Locale, watchlist?: string) {
  return `/${locale}/alerts/watchlists${watchlist ? `?${new URLSearchParams({ watchlist })}` : ""}`;
}

export function journalHref(locale: Locale, decision?: string) {
  return `/${locale}/journal${decision ? `?${new URLSearchParams({ decision })}` : ""}`;
}

export function monitoringFailure(error: unknown): "conflict" | "rejected" | "unconfirmed" {
  if (!(error instanceof ApiRequestError)) return "unconfirmed";
  if (error.status === 409 || error.status === 404) return "conflict";
  if (error.status >= 400 && error.status < 500 && error.status !== 429) return "rejected";
  return "unconfirmed";
}

type AlertState = "acknowledged" | "expired" | "open" | "resolved" | "snoozed";

type AlertSource = {
  aggregate_id: string | null;
  aggregate_type: string | null;
  aggregate_version: number | null;
  checksum: string;
  event_id: string | null;
  observed_at: string;
  resource_id: string;
  resource_schema_version: string;
  resource_type: "alert";
  schema_version: "nexora-source-reference-v1";
  source_product: "trd_bot";
  source_version: string;
};

export type AlertHistory = {
  alert_history_id: string;
  evidence_generation: number;
  occurred_at: string;
  reason_code: string;
  recorded_at: string;
  snooze_until: string | null;
  source_evidence_checksum: string;
  state: AlertState;
  state_version: number;
};

export type AlertItem = {
  alert_id: string;
  current_version: number;
  evidence: Record<string, unknown>;
  evidence_sha256: string;
  history: AlertHistory[];
  local_state: AlertState;
  snooze_until: string | null;
  source: AlertSource;
};

export type AlertInboxResponse = {
  items: AlertItem[];
  notification_delivery_enabled: false;
  provider: ProviderStatus;
  schema_version: "nexora-alert-inbox-v1";
};

export type AlertAction = "acknowledge" | "snooze";
