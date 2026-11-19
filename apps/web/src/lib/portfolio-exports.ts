import { apiRequest } from "@/lib/api-client";

export const exportProfiles = ["ai_safe", "private_complete"] as const;
export const exportFormats = ["json", "csv", "parquet"] as const;
export type ExportProfile = (typeof exportProfiles)[number];
export type ExportFormat = (typeof exportFormats)[number];

export type ExportRequest = { profile: ExportProfile; formats: ExportFormat[]; pinned: boolean };

export type ExportReceipt = {
  id: string;
  version: string;
  sha256: string;
  snapshotSha256: string;
  sizeBytes: number;
  generatedAt: string;
  profile: ExportProfile;
  formats: ExportFormat[];
  recordCount: number;
  pinned: boolean;
};

type ExportManifest = {
  schema_version: string;
  export_id: string;
  complete: boolean;
  public_download: boolean;
  delivery_format: string;
  content_formats: ExportFormat[];
  generated_at: string;
  profile: ExportProfile;
  record_count: number;
  snapshot_sha256: string;
};

type ExportPublication = {
  schema_version: string;
  manifest: ExportManifest;
  artifact_version: string;
  artifact_sha256: string;
  artifact_size_bytes: number;
  retention_class: "pinned_export" | "unpinned_export";
  download_path: string;
};

const hash = /^[a-f0-9]{64}$/;
const idPattern = /^pex_[a-f0-9]{24}$/;
const maxHistory = 20;

function isExportReceipt(value: unknown): value is ExportReceipt {
  if (!value || typeof value !== "object") return false;
  const item = value as Partial<ExportReceipt>;
  return (
    typeof item.id === "string" &&
    idPattern.test(item.id) &&
    typeof item.sha256 === "string" &&
    hash.test(item.sha256) &&
    item.version === `v1-${item.sha256.slice(0, 16)}` &&
    typeof item.snapshotSha256 === "string" &&
    hash.test(item.snapshotSha256) &&
    typeof item.generatedAt === "string" &&
    Number.isFinite(Date.parse(item.generatedAt)) &&
    typeof item.sizeBytes === "number" &&
    Number.isSafeInteger(item.sizeBytes) &&
    item.sizeBytes > 0 &&
    typeof item.recordCount === "number" &&
    Number.isSafeInteger(item.recordCount) &&
    item.recordCount >= 0 &&
    (item.profile === "ai_safe" || item.profile === "private_complete") &&
    typeof item.pinned === "boolean" &&
    Array.isArray(item.formats) &&
    item.formats.length > 0 &&
    item.formats.every((format) => exportFormats.includes(format)) &&
    new Set(item.formats).size === item.formats.length
  );
}

export async function createPortfolioExport(request: ExportRequest, signal: AbortSignal) {
  const result = await apiRequest<ExportPublication>("/api/v1/portfolio-exports", {
    body: request,
    method: "POST",
    signal,
  });
  const { manifest } = result;
  const receipt: ExportReceipt = {
    id: manifest.export_id,
    version: result.artifact_version,
    sha256: result.artifact_sha256,
    snapshotSha256: manifest.snapshot_sha256,
    generatedAt: manifest.generated_at,
    sizeBytes: result.artifact_size_bytes,
    profile: manifest.profile,
    formats: manifest.content_formats,
    recordCount: manifest.record_count,
    pinned: result.retention_class === "pinned_export",
  };
  if (
    !isExportReceipt(receipt) ||
    result.schema_version !== "nexora-portfolio-export-publication-v1" ||
    manifest.schema_version !== "nexora-portfolio-export-manifest-v1" ||
    manifest.complete !== true ||
    manifest.public_download !== false ||
    manifest.delivery_format !== "zip_bundle" ||
    receipt.profile !== request.profile ||
    result.retention_class !== (request.pinned ? "pinned_export" : "unpinned_export") ||
    receipt.formats.length !== request.formats.length ||
    !request.formats.every((format) => receipt.formats.includes(format)) ||
    result.download_path !==
      `/v1/exports/portfolio-export/${receipt.id}/versions/${receipt.version}/download`
  ) {
    throw new Error("Invalid portfolio export receipt");
  }
  return receipt;
}

function historyKey(ownerId: string) {
  return `nexora-export-receipts-v1:${ownerId}`;
}

export function readExportHistory(ownerId: string): ExportReceipt[] {
  try {
    const value: unknown = JSON.parse(localStorage.getItem(historyKey(ownerId)) ?? "null");
    return Array.isArray(value) ? value.filter(isExportReceipt).slice(0, maxHistory) : [];
  } catch {
    return [];
  }
}

export function rememberExport(ownerId: string, receipt: ExportReceipt, current: ExportReceipt[]) {
  const recent = new Map<string, ExportReceipt>();
  for (const item of [receipt, ...readExportHistory(ownerId), ...current]) {
    if (!recent.has(item.id)) recent.set(item.id, item);
  }
  const history = [...recent.values()]
    .sort((a, b) => Date.parse(b.generatedAt) - Date.parse(a.generatedAt))
    .slice(0, maxHistory);
  try {
    localStorage.setItem(historyKey(ownerId), JSON.stringify(history));
    return { history, persisted: true };
  } catch {
    return { history, persisted: false };
  }
}
