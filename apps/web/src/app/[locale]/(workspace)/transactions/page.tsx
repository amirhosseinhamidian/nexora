import { WorkspaceView } from "@/components/workspace-view";
import type { AccountingQuery } from "@/lib/portfolio-accounting";

export default async function TransactionsPage({
  searchParams,
}: {
  searchParams: Promise<AccountingQuery>;
}) {
  return <WorkspaceView query={await searchParams} section="transactions" view="journal" />;
}
