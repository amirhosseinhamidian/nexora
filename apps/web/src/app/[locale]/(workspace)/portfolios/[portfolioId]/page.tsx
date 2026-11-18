import { WorkspaceView } from "@/components/workspace-view";

export default async function PortfolioDetailPage({
  params,
}: {
  params: Promise<{ portfolioId: string }>;
}) {
  const { portfolioId } = await params;
  return <WorkspaceView key={portfolioId} portfolioId={portfolioId} section="portfolioDetail" />;
}
