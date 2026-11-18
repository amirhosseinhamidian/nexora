import { notFound } from "next/navigation";

import { WorkspaceView } from "@/components/workspace-view";
import { accountingViews, type AccountingQuery } from "@/lib/portfolio-accounting";

export default async function AccountingPage({
  params,
  searchParams,
}: {
  params: Promise<{ view: string }>;
  searchParams: Promise<AccountingQuery>;
}) {
  const { view } = await params;
  const section = accountingViews.find((item) => item !== "journal" && item === view);
  if (!section) notFound();
  return <WorkspaceView query={await searchParams} section="transactions" view={section} />;
}
