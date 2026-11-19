import { WorkspaceView } from "@/components/workspace-view";
import { monitoringId } from "@/lib/monitoring";

export default async function WatchlistsPage({
  searchParams,
}: {
  searchParams: Promise<{ watchlist?: string | string[] }>;
}) {
  const { watchlist } = await searchParams;
  return <WorkspaceView section="watchlists" watchlistId={monitoringId(watchlist)} />;
}
