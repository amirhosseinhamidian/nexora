import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import en from "../../messages/en.json";
import { apiRequest } from "@/lib/api-client";
import { createPasskeyAssertion } from "@/lib/webauthn";
import { AuthPanel } from "./auth-panel";

const replace = vi.fn();
const refresh = vi.fn();
vi.mock("next/navigation", () => ({
  usePathname: () => "/en/login",
  useRouter: () => ({ replace, refresh }),
}));
vi.mock("next-themes", () => ({ useTheme: () => ({ resolvedTheme: "dark", setTheme: vi.fn() }) }));
vi.mock("@/lib/api-client", () => ({
  ApiRequestError: class extends Error {},
  apiRequest: vi.fn(),
}));
vi.mock("@/lib/webauthn", () => ({
  createPasskeyAssertion: vi.fn(),
  createPasskeyRegistration: vi.fn(),
}));

const request = vi.mocked(apiRequest);
const assertion = vi.mocked(createPasskeyAssertion);

describe("AuthPanel", () => {
  beforeEach(() => {
    request.mockReset();
    assertion.mockReset();
    replace.mockReset();
    refresh.mockReset();
  });

  it("completes passkey login without browser token storage", async () => {
    const options = {
      allow_credentials: [],
      challenge: "q".repeat(43),
      rp_id: "nexora.private",
    };
    request.mockResolvedValueOnce(options).mockResolvedValueOnce({
      owner_id: "113f777b-f75b-46e5-91da-91d9601c03ea",
      recently_reauthenticated: true,
      rotation_required: false,
    });
    assertion.mockResolvedValue({
      challenge: options.challenge,
      credential_id: "credential-id-1234",
      response_json: "{}",
    });

    render(<AuthPanel dictionary={en} locale="en" mode="login" />);
    fireEvent.click(screen.getByRole("button", { name: "Sign in with passkey" }));

    await waitFor(() => expect(replace).toHaveBeenCalledWith("/en"));
    expect(request).toHaveBeenNthCalledWith(1, "/api/v1/auth/authentication/options", {
      body: {},
      method: "POST",
      signalSessionExpiry: false,
    });
    expect(request).toHaveBeenNthCalledWith(
      2,
      "/api/v1/auth/authentication/complete",
      expect.objectContaining({ method: "POST", signalSessionExpiry: false }),
    );
    expect(localStorage).toHaveLength(0);
    expect(sessionStorage).toHaveLength(0);
  });
});
