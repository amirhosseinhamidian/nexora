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
  method?: "GET" | "POST";
  signalSessionExpiry?: boolean;
};

export async function apiRequest<T>(path: string, options: ApiOptions = {}): Promise<T> {
  sameOriginApiPath(path);
  const method = options.method ?? "GET";
  const headers = new Headers({ Accept: "application/json" });
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
): Promise<void> {
  const parts = [artifactType, artifactId, version].map((part) => encodeURIComponent(part));
  const path = `/api/v1/exports/${parts[0]}/${parts[1]}/versions/${parts[2]}/download`;
  sameOriginApiPath(path);
  const response = await fetch(path, { cache: "no-store", credentials: "same-origin" });
  if (!response.ok) {
    if (response.status === 401) window.dispatchEvent(new Event(SESSION_EXPIRED_EVENT));
    throw new ApiRequestError(response.status, `HTTP_${response.status}`);
  }
  const blob = await response.blob();
  const disposition = response.headers.get("content-disposition") ?? "";
  const encodedName = disposition.match(/filename\*=UTF-8''([^;]+)/i)?.[1];
  const fileName = encodedName ? decodeURIComponent(encodedName) : "nexora-export.bin";
  const url = URL.createObjectURL(blob);
  try {
    const link = document.createElement("a");
    link.href = url;
    link.download = fileName;
    link.rel = "noopener";
    link.click();
  } finally {
    URL.revokeObjectURL(url);
  }
}
