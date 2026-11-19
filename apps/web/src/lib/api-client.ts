import type { ErrorEnvelope } from "@nexora/contracts";

export const SESSION_EXPIRED_EVENT = "nexora:session-expired";
const CSRF_COOKIE = "__Host-nexora_csrf";

export class ApiRequestError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
  ) {
    super(code);
    this.name = "ApiRequestError";
  }
}

export function readCsrfToken(cookieSource = document.cookie): string | undefined {
  return cookieSource
    .split(";")
    .map((part) => part.trim().split("=", 2))
    .find(([name]) => name === CSRF_COOKIE)?.[1];
}

function sameOriginApiPath(path: string): void {
  if (!path.startsWith("/api/") || path.startsWith("//") || path.includes("\\")) {
    throw new Error("API requests must use the same-origin /api boundary");
  }
}

type ApiOptions = {
  body?: unknown;
  headers?: Record<string, string>;
  method?: "GET" | "POST";
  signal?: AbortSignal;
  signalSessionExpiry?: boolean;
};

export async function apiRequest<T>(path: string, options: ApiOptions = {}): Promise<T> {
  sameOriginApiPath(path);
  const method = options.method ?? "GET";
  const headers = new Headers({ Accept: "application/json" });
  for (const [name, value] of Object.entries(options.headers ?? {})) headers.set(name, value);
  if (method === "POST") {
    headers.set("Content-Type", "application/json");
    const csrf = readCsrfToken();
    if (csrf) headers.set("X-CSRF-Token", csrf);
  }
  const response = await fetch(path, {
    body: options.body === undefined ? undefined : JSON.stringify(options.body),
    cache: "no-store",
    credentials: "same-origin",
    headers,
    method,
    signal: options.signal,
  });
  if (!response.ok) {
    let error: ErrorEnvelope | undefined;
    try {
      error = (await response.json()) as ErrorEnvelope;
    } catch {
      error = undefined;
    }
    if (response.status === 401 && options.signalSessionExpiry !== false) {
      window.dispatchEvent(new Event(SESSION_EXPIRED_EVENT));
    }
    throw new ApiRequestError(response.status, error?.error.code ?? `HTTP_${response.status}`);
  }
  return (await response.json()) as T;
}

export async function downloadExport(
  artifactType: string,
  artifactId: string,
  version: string,
  options: {
    expected?: { sha256: string; sizeBytes: number };
    save?: boolean;
    signal?: AbortSignal;
  } = {},
): Promise<void> {
  const parts = [artifactType, artifactId, version].map((part) => encodeURIComponent(part));
  const path = `/api/v1/exports/${parts[0]}/${parts[1]}/versions/${parts[2]}/download`;
  sameOriginApiPath(path);
  const response = await fetch(path, {
    cache: "no-store",
    credentials: "same-origin",
    redirect: "error",
    signal: options.signal,
  });
  if (!response.ok) {
    if (response.status === 401) window.dispatchEvent(new Event(SESSION_EXPIRED_EVENT));
    throw new ApiRequestError(response.status, `HTTP_${response.status}`);
  }
  const { expected } = options;
  const integrityError = () => new ApiRequestError(409, "ARTIFACT_INTEGRITY_FAILED");
  if (expected) {
    const length = response.headers.get("content-length");
    if (
      response.headers.get("X-Artifact-SHA256") !== expected.sha256 ||
      (length !== null && Number(length) !== expected.sizeBytes)
    ) {
      await response.body?.cancel();
      throw integrityError();
    }
  }
  const blob = await response.blob();
  if (expected) {
    if (blob.size !== expected.sizeBytes) throw integrityError();
    const digest = await crypto.subtle.digest("SHA-256", await blob.arrayBuffer());
    const sha256 = Array.from(new Uint8Array(digest), (part) =>
      part.toString(16).padStart(2, "0"),
    ).join("");
    if (sha256 !== expected.sha256) throw integrityError();
  }
  options.signal?.throwIfAborted();
  if (options.save === false) return;
  const disposition = response.headers.get("content-disposition") ?? "";
  const encodedName = disposition.match(/filename\*=UTF-8''([^;]+)/i)?.[1];
  const fileName = expected
    ? `${artifactId}.zip`
    : encodedName
      ? decodeURIComponent(encodedName)
      : "nexora-export.bin";
  const url = URL.createObjectURL(blob);
  try {
    const link = document.createElement("a");
    link.href = url;
    link.download = fileName;
    link.rel = "noopener";
    link.click();
  } finally {
    window.setTimeout(() => URL.revokeObjectURL(url), 30_000);
  }
}
