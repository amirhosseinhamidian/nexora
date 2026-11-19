"use client";

import type {
  ActionResponse,
  AuthenticationOptionsResponse,
  SessionResponse,
} from "@nexora/contracts";
import { Drawer, IconButton } from "@nexora/ui/primitives";
import { LogOut, Menu, PanelLeftClose, PanelLeftOpen } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { createContext, type ReactNode, useCallback, useContext, useEffect, useState } from "react";

import { FoundationControls } from "@/components/foundation-controls";
import { StatePanel } from "@/components/state-panel";
import { WorkspaceNavigation } from "@/components/workspace-navigation";
import { WorkspaceTimeZone } from "@/components/workspace-time";
import type { Locale } from "@/i18n/config";
import type { Dictionary } from "@/i18n/dictionaries";
import { ApiRequestError, SESSION_EXPIRED_EVENT, apiRequest } from "@/lib/api-client";
import {
  defaultDisplayPreferences,
  readDisplayPreferences,
  writeDisplayPreferences,
  type DisplayPreferences,
} from "@/lib/display-preferences";
import { createPasskeyAssertion } from "@/lib/webauthn";

type ShellState = "authenticated" | "expired" | "loading" | "offline";

type AuthenticatedShellProps = {
  children: ReactNode;
  dictionary: Dictionary;
  locale: Locale;
};

const WorkspaceContext = createContext<
  | (Omit<AuthenticatedShellProps, "children"> & {
      session: SessionResponse;
      reauthenticate: (signal: AbortSignal) => Promise<void>;
      refreshSession: (signal: AbortSignal) => Promise<void>;
      displayPreferences: DisplayPreferences;
      updateDisplayPreferences: (patch: Partial<DisplayPreferences>) => boolean;
    })
  | null
>(null);

export function useWorkspace() {
  const context = useContext(WorkspaceContext);
  if (!context) throw new Error("Workspace content requires the authenticated shell.");
  return context;
}

export function AuthenticatedShell({ children, dictionary, locale }: AuthenticatedShellProps) {
  const pathname = usePathname();
  const [state, setState] = useState<ShellState>("loading");
  const [session, setSession] = useState<SessionResponse>();
  const [servicesReady, setServicesReady] = useState(false);
  const [display, setDisplay] = useState<{ ownerId: string; preferences: DisplayPreferences }>();
  const [mobileOpen, setMobileOpen] = useState(false);
  const closeMobile = () => setMobileOpen(false);

  useEffect(() => {
    const desktop = window.matchMedia("(width > 900px)");
    const closeOnDesktop = (event: MediaQueryListEvent) => {
      if (event.matches) setMobileOpen(false);
    };
    const closeOnHistoryChange = () => setMobileOpen(false);
    desktop.addEventListener("change", closeOnDesktop);
    window.addEventListener("popstate", closeOnHistoryChange);
    return () => {
      desktop.removeEventListener("change", closeOnDesktop);
      window.removeEventListener("popstate", closeOnHistoryChange);
    };
  }, []);

  const restore = useCallback(async () => {
    try {
      const current = await apiRequest<SessionResponse>("/api/v1/auth/session", {
        signalSessionExpiry: false,
      });
      const preferences = readDisplayPreferences(current.owner_id);
      setDisplay((previous) =>
        previous?.ownerId === current.owner_id
          ? previous
          : { ownerId: current.owner_id, preferences },
      );
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
    const expire = () => {
      setMobileOpen(false);
      setState("expired");
    };
    const offline = () => {
      setMobileOpen(false);
      setState("offline");
    };
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

  async function refreshSession(signal: AbortSignal) {
    const current = await apiRequest<SessionResponse>("/api/v1/auth/session", { signal });
    signal.throwIfAborted();
    setSession(current);
  }

  async function reauthenticate(signal: AbortSignal) {
    const options = await apiRequest<AuthenticationOptionsResponse>(
      "/api/v1/auth/reauthentication/options",
      { body: {}, method: "POST", signal, signalSessionExpiry: false },
    );
    const assertion = await createPasskeyAssertion(options, signal);
    signal.throwIfAborted();
    const verified = await apiRequest<SessionResponse>("/api/v1/auth/reauthentication/complete", {
      body: assertion,
      method: "POST",
      signal,
      signalSessionExpiry: false,
    });
    signal.throwIfAborted();
    if (!verified.recently_reauthenticated || verified.owner_id !== session?.owner_id) {
      throw new Error("Reauthentication was not confirmed");
    }
    setSession((current) =>
      current?.owner_id === verified.owner_id ? { ...current, ...verified } : current,
    );
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
    const login =
      pathname === `/${locale}/onboarding`
        ? `/${locale}/login?resume=onboarding`
        : `/${locale}/login`;
    return (
      <StatePanel
        action={{ href: login, label: dictionary.states.signIn }}
        description={dictionary.states.expiredDescription}
        kind="session"
        title={dictionary.states.expiredTitle}
      />
    );
  }

  const copy = dictionary.workspacePages;
  const displayPreferences =
    display?.ownerId === session.owner_id ? display.preferences : defaultDisplayPreferences;
  const collapsed = displayPreferences.sidebarCollapsed;

  function updateDisplayPreferences(patch: Partial<DisplayPreferences>) {
    if (!session) return false;
    const preferences = { ...displayPreferences, ...patch };
    setDisplay({ ownerId: session.owner_id, preferences });
    return writeDisplayPreferences(session.owner_id, preferences);
  }
  const SidebarIcon = collapsed ? PanelLeftOpen : PanelLeftClose;
  const status = servicesReady ? dictionary.shell.ready : dictionary.shell.limited;
  return (
    <div className="application-shell" data-sidebar-collapsed={collapsed}>
      <a className="skip-link" href="#main-content">
        {dictionary.skipToContent}
      </a>
      <aside className="sidebar" id="desktop-sidebar">
        <Link aria-label={dictionary.brand} className="brand" href={`/${locale}/overview`}>
          <span aria-hidden="true" className="brand-mark">
            N
          </span>
          <span className="sidebar-brand-name" dir="ltr">
            {dictionary.brand}
          </span>
        </Link>
        <WorkspaceNavigation dictionary={dictionary} locale={locale} />
        <div className="sidebar-session">
          <span>{dictionary.shell.owner}</span>
          <code dir="ltr">{session.owner_id.slice(0, 8)}…</code>
        </div>
      </aside>

      <div className="workspace">
        <header className="topbar">
          <div className="topbar-leading">
            <IconButton
              aria-controls="desktop-sidebar"
              aria-expanded={!collapsed}
              aria-label={collapsed ? copy.expandSidebar : copy.collapseSidebar}
              className="sidebar-toggle"
              onClick={() => updateDisplayPreferences({ sidebarCollapsed: !collapsed })}
              title={collapsed ? copy.expandSidebar : copy.collapseSidebar}
            >
              <SidebarIcon aria-hidden="true" className="sidebar-toggle-icon" size={19} />
            </IconButton>
            <IconButton
              aria-controls="mobile-navigation"
              aria-expanded={mobileOpen}
              aria-haspopup="dialog"
              aria-label={copy.openNavigation}
              className="mobile-navigation-toggle"
              onClick={(event) => {
                event.currentTarget.focus();
                setMobileOpen(true);
              }}
            >
              <Menu aria-hidden="true" size={19} />
            </IconButton>
            <div className="environment-pill" title={status}>
              <span className={`status-dot ${servicesReady ? "" : "limited"}`} />
              <span className="environment-label">{dictionary.header.environment}</span>
              <span className="shell-sr-only">{status}</span>
            </div>
          </div>
          <div className="topbar-actions">
            <span className="mode-pill">{dictionary.header.mode}</span>
            <FoundationControls dictionary={dictionary.header} locale={locale} />
            <IconButton aria-label={dictionary.shell.logout} onClick={logout}>
              <LogOut aria-hidden="true" size={18} />
            </IconButton>
          </div>
        </header>

        <main className="main-content" id="main-content" tabIndex={-1}>
          <WorkspaceContext.Provider
            value={{
              dictionary,
              displayPreferences,
              locale,
              reauthenticate,
              refreshSession,
              session,
              updateDisplayPreferences,
            }}
          >
            <WorkspaceTimeZone.Provider
              value={
                displayPreferences.timeZone === "browser" ? undefined : displayPreferences.timeZone
              }
            >
              {children}
            </WorkspaceTimeZone.Provider>
          </WorkspaceContext.Provider>
        </main>
      </div>
      <div id="mobile-navigation">
        <Drawer
          closeLabel={copy.closeNavigation}
          onClose={closeMobile}
          open={mobileOpen}
          title={copy.navigationLabel}
        >
          <WorkspaceNavigation dictionary={dictionary} locale={locale} onNavigate={closeMobile} />
        </Drawer>
      </div>
    </div>
  );
}
