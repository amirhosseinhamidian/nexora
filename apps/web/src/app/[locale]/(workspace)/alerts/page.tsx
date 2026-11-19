import { WorkspaceView } from "@/components/workspace-view";
import { monitoringId } from "@/lib/monitoring";

export default async function AlertsPage({
  searchParams,
}: {
  searchParams: Promise<{
    alert?: string | string[];
    decision?: string | string[];
    watchlist?: string | string[];
  }>;
}) {
  const { alert, decision, watchlist } = await searchParams;
  return (
    <WorkspaceView
      alertId={monitoringId(alert)}
      decisionId={monitoringId(decision)}
      section="alerts"
      watchlistId={monitoringId(watchlist)}
    />
  );
}
