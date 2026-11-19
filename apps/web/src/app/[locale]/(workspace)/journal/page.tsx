import { WorkspaceView } from "@/components/workspace-view";
import { monitoringId } from "@/lib/monitoring";

export default async function JournalPage({
  searchParams,
}: {
  searchParams: Promise<{ decision?: string | string[] }>;
}) {
  const { decision } = await searchParams;
  return <WorkspaceView decisionId={monitoringId(decision)} section="journal" />;
}
