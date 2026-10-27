"use client";

import type { ActionResponse, SessionResponse } from "@nexora/contracts";
import {
  Activity,
  Bell,
  BookOpen,
  BriefcaseBusiness,
  CheckCircle2,
  Download,
  FileChartColumn,
  LayoutDashboard,
  LogOut,
  ShieldCheck,
  SlidersHorizontal,
} from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { FoundationControls } from "@/components/foundation-controls";
import { StatePanel } from "@/components/state-panel";
import type { Locale } from "@/i18n/config";
import type { Dictionary } from "@/i18n/dictionaries";
import { ApiRequestError, SESSION_EXPIRED_EVENT, apiRequest } from "@/lib/api-client";

const navigationIcons = [
  LayoutDashboard,
  BriefcaseBusiness,
  FileChartColumn,
  Bell,
  BookOpen,
  Download,
  SlidersHorizontal,
] as const;

type ShellState = "authenticated" | "expired" | "loading" | "offline";

type AuthenticatedShellProps = {
  dictionary: Dictionary;
  locale: Locale;
};

export function AuthenticatedShell({ dictionary, locale }: AuthenticatedShellProps) {
  const [state, setState] = useState<ShellState>("loading");
  const [session, setSession] = useState<SessionResponse>();
  const [servicesReady, setServicesReady] = useState(false);

  const restore = useCallback(async () => {
    try {
      const current = await apiRequest<SessionResponse>("/api/v1/auth/session", {
        signalSessionExpiry: false,
      });
      setSession(current);
      setState("authenticated");
      try {
        await apiRequest<unknown>("/api/health/ready", { signalSessionExpiry: false });
        setServicesReady(true);
      } catch (error) {
        if (error instanceof ApiRequestError && error.status === 503) setServicesReady(false);
        else throw error;
      }
    } catch (error) {
      setServicesReady(false);
      if (error instanceof ApiRequestError && error.status === 401) setState("expired");
      else setState("offline");
    }
  }, []);

  useEffect(() => {
    const initialRestore = window.setTimeout(() => void restore(), 0);
    const expire = () => setState("expired");
    const offline = () => setState("offline");
    const online = () => void restore();
    window.addEventListener(SESSION_EXPIRED_EVENT, expire);
    window.addEventListener("offline", offline);
    window.addEventListener("online", online);
    return () => {
      window.clearTimeout(initialRestore);
      window.removeEventListener(SESSION_EXPIRED_EVENT, expire);
      window.removeEventListener("offline", offline);
      window.removeEventListener("online", online);
    };
  }, [restore]);

  async function logout() {
    try {
      await apiRequest<ActionResponse>("/api/v1/auth/logout", { body: {}, method: "POST" });
    } finally {
      setSession(undefined);
      setState("expired");
    }
  }

  if (state === "loading") {
    return (
      <StatePanel
        description={dictionary.states.loadingDescription}
        kind="loading"
        title={dictionary.states.loadingTitle}
      />
    );
  }
  if (state === "offline") {
    return (
      <StatePanel
        action={{
          label: dictionary.states.retry,
          onClick: () => {
            setState("loading");
            void restore();
          },
        }}
        description={dictionary.states.offlineDescription}
        kind="offline"
        title={dictionary.states.offlineTitle}
      />
    );
  }
  if (state === "expired" || !session) {
    return (
      <StatePanel
        action={{ href: `/${locale}/login`, label: dictionary.states.signIn }}
        description={dictionary.states.expiredDescription}
        kind="session"
        title={dictionary.states.expiredTitle}
      />
    );
  }

  const navigation = Object.values(dictionary.navigation);
  const status = servicesReady ? dictionary.shell.ready : dictionary.shell.limited;
  return (
    <div className="application-shell">
      <a className="skip-link" href="#main-content">
        {dictionary.skipToContent}
      </a>
      <aside className="sidebar">
        <Link className="brand" dir="ltr" href={`/${locale}`}>
          <span aria-hidden="true" className="brand-mark">
            N
          </span>
          <span>{dictionary.brand}</span>
        </Link>
        <nav aria-label={dictionary.navigation.overview}>
          <ul className="navigation-list">
            {navigation.map((label, index) => {
              const Icon = navigationIcons[index];
              return (
                <li key={label}>
                  {index === 0 ? (
                    <Link
                      aria-current="page"
                      className="navigation-link active"
                      href={`/${locale}`}
                    >
                      <Icon aria-hidden="true" size={19} />
                      <span>{label}</span>
                    </Link>
                  ) : (
                    <span
                      aria-disabled="true"
                      className="navigation-link disabled"
                      title={dictionary.shell.phaseTwo}
                    >
                      <Icon aria-hidden="true" size={19} />
                      <span>{label}</span>
                    </span>
                  )}
                </li>
              );
            })}
          </ul>
        </nav>
        <div className="sidebar-session">
          <span>{dictionary.shell.owner}</span>
          <code dir="ltr">{session.owner_id.slice(0, 8)}…</code>
        </div>
      </aside>

      <div className="workspace">
        <header className="topbar">
          <div className="environment-pill">
            <span className="status-dot" />
            {dictionary.header.environment}
          </div>
          <div className="topbar-actions">
            <span className="mode-pill">{dictionary.header.mode}</span>
            <FoundationControls dictionary={dictionary.header} locale={locale} />
            <button
              aria-label={dictionary.shell.logout}
              className="control-button icon-only"
              onClick={logout}
              type="button"
            >
              <LogOut aria-hidden="true" size={18} />
            </button>
          </div>
        </header>

        <main className="main-content" id="main-content">
          <div className="page-heading">
            <div>
              <p className="eyebrow">{dictionary.shell.eyebrow}</p>
              <h1>{dictionary.shell.title}</h1>
              <p>{dictionary.shell.description}</p>
            </div>
            <div className="ready-badge">
              <CheckCircle2 aria-hidden="true" size={18} />
              {dictionary.shell.authenticated}
            </div>
          </div>

          <section aria-label={dictionary.shell.serviceStatus} className="metric-grid">
            {[
              [dictionary.shell.api, Activity],
              [dictionary.shell.identity, ShieldCheck],
              [dictionary.shell.artifacts, Download],
            ].map(([label, Icon]) => (
              <article className="metric-card" key={String(label)}>
                <div className="metric-card-heading">
                  <span>{String(label)}</span>
                  <Icon aria-hidden="true" size={20} />
                </div>
                <strong>{status}</strong>
                <p>
                  {servicesReady
                    ? dictionary.shell.authenticated
                    : dictionary.states.offlineDescription}
                </p>
              </article>
            ))}
          </section>

          <section className="empty-state-card">
            <BriefcaseBusiness aria-hidden="true" size={32} />
            <div>
              <h2>{dictionary.shell.emptyTitle}</h2>
              <p>{dictionary.shell.emptyDescription}</p>
            </div>
          </section>

          <section className="boundary-card">
            <div className="boundary-heading">
              <h2>{dictionary.shell.securityTitle}</h2>
              <ShieldCheck aria-hidden="true" size={28} />
            </div>
            <ul className="boundary-list">
              {Object.values(dictionary.shell.securityItems).map((item) => (
                <li key={item}>
                  <CheckCircle2 aria-hidden="true" size={18} />
                  <span>{item}</span>
                </li>
              ))}
            </ul>
          </section>
        </main>
      </div>
    </div>
  );
}
