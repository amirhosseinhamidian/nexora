"use client";

import type {
  AuthenticationOptionsResponse,
  BootstrapCompleteResponse,
  RegistrationOptionsResponse,
  SessionResponse,
} from "@nexora/contracts";
import { Fingerprint, KeyRound, ShieldCheck } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { FoundationControls } from "@/components/foundation-controls";
import type { Locale } from "@/i18n/config";
import type { Dictionary } from "@/i18n/dictionaries";
import { ApiRequestError, apiRequest } from "@/lib/api-client";
import { createPasskeyAssertion, createPasskeyRegistration } from "@/lib/webauthn";

type AuthPanelProps = {
  dictionary: Dictionary;
  locale: Locale;
  mode: "bootstrap" | "login";
};

function errorMessage(error: unknown, dictionary: Dictionary["auth"]): string {
  if (error instanceof Error && error.message === "WEBAUTHN_UNAVAILABLE")
    return dictionary.unavailable;
  if (error instanceof DOMException && ["AbortError", "NotAllowedError"].includes(error.name)) {
    return dictionary.denied;
  }
  if (error instanceof ApiRequestError && error.code === "AUTHENTICATION_DENIED")
    return dictionary.denied;
  return dictionary.failed;
}

export function AuthPanel({ dictionary, locale, mode }: AuthPanelProps) {
  const router = useRouter();
  const [bootstrapToken, setBootstrapToken] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string>();
  const [recoveryCodes, setRecoveryCodes] = useState<string[]>();
  const auth = dictionary.auth;

  async function login() {
    setBusy(true);
    setError(undefined);
    try {
      const options = await apiRequest<AuthenticationOptionsResponse>(
        "/api/v1/auth/authentication/options",
        { body: {}, method: "POST", signalSessionExpiry: false },
      );
      const assertion = await createPasskeyAssertion(options);
      await apiRequest<SessionResponse>("/api/v1/auth/authentication/complete", {
        body: assertion,
        method: "POST",
        signalSessionExpiry: false,
      });
      router.replace(`/${locale}`);
      router.refresh();
    } catch (caught) {
      setError(errorMessage(caught, auth));
    } finally {
      setBusy(false);
    }
  }

  async function bootstrap() {
    if (bootstrapToken.length < 32) return;
    setBusy(true);
    setError(undefined);
    const token = bootstrapToken;
    try {
      const options = await apiRequest<RegistrationOptionsResponse>(
        "/api/v1/auth/bootstrap/options",
        {
          body: { bootstrap_token: token },
          method: "POST",
          signalSessionExpiry: false,
        },
      );
      const responseJson = await createPasskeyRegistration(options, token);
      const completed = await apiRequest<BootstrapCompleteResponse>(
        "/api/v1/auth/bootstrap/complete",
        {
          body: { bootstrap_token: token, response_json: responseJson },
          method: "POST",
          signalSessionExpiry: false,
        },
      );
      setBootstrapToken("");
      setRecoveryCodes(completed.recovery_codes);
    } catch (caught) {
      setError(errorMessage(caught, auth));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="auth-page">
      <header className="auth-header">
        <Link className="brand" dir="ltr" href={`/${locale}`}>
          <span aria-hidden="true" className="brand-mark">
            N
          </span>
          <span>{dictionary.brand}</span>
        </Link>
        <FoundationControls dictionary={dictionary.header} locale={locale} />
      </header>
      <main className="auth-main" id="main-content">
        <section className="auth-card">
          <span className="auth-icon">
            <ShieldCheck aria-hidden="true" size={28} />
          </span>
          <p className="eyebrow">{auth.eyebrow}</p>
          {recoveryCodes ? (
            <>
              <h1>{auth.recoveryTitle}</h1>
              <p className="auth-description">{auth.recoveryDescription}</p>
              <ol className="recovery-codes" dir="ltr">
                {recoveryCodes.map((code) => (
                  <li key={code}>{code}</li>
                ))}
              </ol>
              <Link className="primary-button" href={`/${locale}/login`}>
                {auth.recoverySaved}
              </Link>
            </>
          ) : mode === "login" ? (
            <>
              <h1>{auth.loginTitle}</h1>
              <p className="auth-description">{auth.loginDescription}</p>
              <button className="primary-button" disabled={busy} onClick={login} type="button">
                <Fingerprint aria-hidden="true" size={19} />
                {busy ? auth.working : auth.loginAction}
              </button>
              <Link className="text-link" href={`/${locale}/bootstrap`}>
                {auth.bootstrapLink}
              </Link>
            </>
          ) : (
            <>
              <h1>{auth.bootstrapTitle}</h1>
              <p className="auth-description">{auth.bootstrapDescription}</p>
              <label className="field-label" htmlFor="bootstrap-token">
                {auth.bootstrapToken}
              </label>
              <div className="secure-input">
                <KeyRound aria-hidden="true" size={19} />
                <input
                  autoComplete="off"
                  id="bootstrap-token"
                  onChange={(event) => setBootstrapToken(event.target.value.trim())}
                  spellCheck={false}
                  type="password"
                  value={bootstrapToken}
                />
              </div>
              <button
                className="primary-button"
                disabled={busy || bootstrapToken.length < 32}
                onClick={bootstrap}
                type="button"
              >
                <Fingerprint aria-hidden="true" size={19} />
                {busy ? auth.working : auth.bootstrapAction}
              </button>
              <Link className="text-link" href={`/${locale}/login`}>
                {auth.loginLink}
              </Link>
            </>
          )}
          {error ? (
            <p className="form-error" role="alert">
              {error}
            </p>
          ) : null}
        </section>
      </main>
    </div>
  );
}
