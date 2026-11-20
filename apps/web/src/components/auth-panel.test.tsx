import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import en from "../../messages/en.json";
import { SESSION_EXPIRED_EVENT } from "@/lib/api-client";
import { createPasskeyAssertion } from "@/lib/webauthn";
import { AuthPanel } from "./auth-panel";

const replace = vi.fn();
const refresh = vi.fn();
vi.mock("next/navigation", () => ({
  usePathname: () => "/en/login",
  useSearchParams: () => new URLSearchParams(),
  useRouter: () => ({ replace, refresh }),
}));
vi.mock("next-themes", () => ({ useTheme: () => ({ resolvedTheme: "dark", setTheme: vi.fn() }) }));
vi.mock("@/lib/webauthn", () => ({
  createPasskeyAssertion: vi.fn(),
  createPasskeyRegistration: vi.fn(),
}));

const request = vi.fn<typeof fetch>();
const assertion = vi.mocked(createPasskeyAssertion);
const options = {
  allow_credentials: [],
  challenge: "q".repeat(43),
  rp_id: "nexora.private",
};
const assertionPayload = {
  challenge: options.challenge,
  credential_id: "credential-id-1234",
  response_json: "{}",
};

function reply(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    headers: { "Content-Type": "application/json" },
    status,
  });
}

describe("AuthPanel", () => {
  beforeEach(() => {
    request.mockReset();
    assertion.mockReset();
    assertion.mockResolvedValue(assertionPayload);
    replace.mockReset();
    refresh.mockReset();
    vi.stubGlobal("fetch", request);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it.each([
    ["no existing CSRF cookie", "", null],
    ["a previous CSRF cookie", "__Host-nexora_csrf=fixture-previous-csrf", "fixture-previous-csrf"],
  ] as const)(
    "completes passkey login with %s and no browser token storage",
    async (_case, cookies, csrf) => {
      vi.spyOn(document, "cookie", "get").mockReturnValue(cookies);
      request
        .mockResolvedValueOnce(reply(options))
        .mockResolvedValueOnce(reply({ recently_reauthenticated: true, rotation_required: false }));

      render(<AuthPanel dictionary={en} locale="en" mode="login" />);
      fireEvent.click(screen.getByRole("button", { name: "Sign in with passkey" }));

      await waitFor(() => expect(replace).toHaveBeenCalledWith("/en"));
      expect(request).toHaveBeenCalledTimes(2);
      expect(request).toHaveBeenNthCalledWith(
        1,
        "/api/v1/auth/authentication/options",
        expect.objectContaining({ body: "{}", method: "POST", credentials: "same-origin" }),
      );
      expect(request).toHaveBeenNthCalledWith(
        2,
        "/api/v1/auth/authentication/complete",
        expect.objectContaining({
          body: JSON.stringify(assertionPayload),
          method: "POST",
          credentials: "same-origin",
        }),
      );
      for (const [, init] of request.mock.calls) {
        expect(new Headers(init?.headers).get("X-CSRF-Token")).toBe(csrf);
      }
      expect(localStorage).toHaveLength(0);
      expect(sessionStorage).toHaveLength(0);
    },
  );

  it("returns to onboarding after an interrupted setup login", async () => {
    request.mockResolvedValueOnce(reply(options)).mockResolvedValueOnce(reply({}));

    render(<AuthPanel dictionary={en} locale="en" mode="login" resumeOnboarding />);
    fireEvent.click(screen.getByRole("button", { name: "Sign in with passkey" }));
    await waitFor(() => expect(replace).toHaveBeenCalledWith("/en/onboarding"));
  });

  it.each([
    ["CSRF_DENIED", en.auth.sessionConflict],
    ["ORIGIN_DENIED", en.auth.originDenied],
  ])("shows a specific message for %s without reflecting the response", async (code, message) => {
    request.mockResolvedValueOnce(reply({ error: { code, message: "fixture-private-data" } }, 403));
    render(<AuthPanel dictionary={en} locale="en" mode="login" />);
    fireEvent.click(screen.getByRole("button", { name: "Sign in with passkey" }));

    await expect(screen.findByRole("alert")).resolves.toHaveTextContent(message);
    expect(screen.queryByText("fixture-private-data")).not.toBeInTheDocument();
    expect(assertion).not.toHaveBeenCalled();
    expect(replace).not.toHaveBeenCalled();
  });

  it("reports network failure separately from a passkey denial and permits retry", async () => {
    request.mockRejectedValueOnce(new TypeError("fixture network failure"));
    request.mockResolvedValueOnce(reply(options)).mockResolvedValueOnce(reply({}));
    render(<AuthPanel dictionary={en} locale="en" mode="login" />);
    const signIn = screen.getByRole("button", { name: "Sign in with passkey" });

    fireEvent.click(signIn);
    await expect(screen.findByRole("alert")).resolves.toHaveTextContent(en.auth.connectionFailed);
    expect(assertion).not.toHaveBeenCalled();
    fireEvent.click(signIn);
    await waitFor(() => expect(replace).toHaveBeenCalledWith("/en"));
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it.each([new DOMException("fixture denial", "NotAllowedError"), new TypeError("fixture error")])(
    "reports a device error without submitting an assertion",
    async (error) => {
      request.mockResolvedValueOnce(reply(options));
      assertion.mockRejectedValueOnce(error);
      render(<AuthPanel dictionary={en} locale="en" mode="login" />);
      fireEvent.click(screen.getByRole("button", { name: "Sign in with passkey" }));

      await expect(screen.findByRole("alert")).resolves.toHaveTextContent(en.auth.denied);
      expect(request).toHaveBeenCalledOnce();
      expect(replace).not.toHaveBeenCalled();
    },
  );

  it("keeps a rejected WebAuthn assertion on sign-in without signaling session expiry", async () => {
    request.mockResolvedValueOnce(reply(options));
    request.mockResolvedValueOnce(reply({ error: { code: "AUTHENTICATION_DENIED" } }, 401));
    const dispatch = vi.spyOn(window, "dispatchEvent");
    render(<AuthPanel dictionary={en} locale="en" mode="login" />);
    fireEvent.click(screen.getByRole("button", { name: "Sign in with passkey" }));

    await expect(screen.findByRole("alert")).resolves.toHaveTextContent(en.auth.denied);
    expect(dispatch.mock.calls.some(([event]) => event.type === SESSION_EXPIRED_EVENT)).toBe(false);
    expect(replace).not.toHaveBeenCalled();
  });
});
