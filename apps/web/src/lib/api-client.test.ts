import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  ApiRequestError,
  SESSION_EXPIRED_EVENT,
  apiRequest,
  downloadExport,
  readCsrfToken,
} from "./api-client";

describe("same-origin API client", () => {
  beforeEach(() => vi.restoreAllMocks());

  it("reads only the dedicated CSRF cookie", () => {
    expect(readCsrfToken("other=value; __Host-nexora_csrf=csrf-token; session=secret")).toBe(
      "csrf-token",
    );
  });

  it("rejects paths outside the same-origin API boundary", async () => {
    await expect(apiRequest("https://attacker.invalid/api")).rejects.toThrow("same-origin");
    await expect(apiRequest("//attacker.invalid/api")).rejects.toThrow("same-origin");
  });

  it("emits session expiry without reflecting an untrusted response", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({
          correlation_id: "d7d23916-e3d5-41ee-932e-1f1ae08c1825",
          error: { code: "AUTHENTICATION_DENIED", message: "request denied" },
          schema_version: "nexora-error-envelope-v1",
        }),
        { headers: { "content-type": "application/json" }, status: 401 },
      ),
    );
    const expired = vi.fn();
    window.addEventListener(SESSION_EXPIRED_EVENT, expired, { once: true });

    const error = await apiRequest("/api/v1/auth/session").catch((reason: unknown) => reason);
    expect(error).toBeInstanceOf(ApiRequestError);
    expect(error).toMatchObject({ code: "AUTHENTICATION_DENIED", status: 401 });
    expect(expired).toHaveBeenCalledOnce();
  });

  it("rejects a mismatched artifact digest header before reading or saving the file", async () => {
    const response = new Response("zip", { headers: { "X-Artifact-SHA256": "a".repeat(64) } });
    const read = vi.spyOn(response, "blob");
    const fetchExport = vi.spyOn(globalThis, "fetch").mockResolvedValue(response);

    await expect(
      downloadExport("portfolio-export", "pex_1", "v1-1", {
        expected: { sha256: "b".repeat(64), sizeBytes: 3 },
      }),
    ).rejects.toMatchObject({ status: 409, code: "ARTIFACT_INTEGRITY_FAILED" });

    expect(fetchExport).toHaveBeenCalledExactlyOnceWith(
      "/api/v1/exports/portfolio-export/pex_1/versions/v1-1/download",
      expect.objectContaining({ credentials: "same-origin", redirect: "error", cache: "no-store" }),
    );
    expect(read).not.toHaveBeenCalled();
  });
});
