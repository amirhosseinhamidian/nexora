import { notFound } from "next/navigation";

import { WorkspaceView } from "@/components/workspace-view";
import { decisionPanels } from "@/lib/decision-intelligence";

export default async function DecisionPage({
  params,
}: {
  params: Promise<{ kind: string; resourceId: string; panel?: string[] }>;
}) {
  const { kind, resourceId, panel } = await params;
  if ((kind !== "records" && kind !== "candidates") || !resourceId || resourceId.length > 160) {
    notFound();
  }
  const section = !panel
    ? "evidence"
    : decisionPanels.find((item) => item !== "evidence" && panel.length === 1 && item === panel[0]);
  if (!section) notFound();
  return <WorkspaceView section="decisionRecord" route={{ kind, resourceId, panel: section }} />;
}
