"use client";

import {
  Alert,
  Button,
  ErrorState,
  FormField,
  IconButton,
  Select,
  Spinner,
  ToastRegion,
} from "@nexora/ui/primitives";
import Link from "next/link";
import { useTheme } from "next-themes";
import { useEffect, useId, useState, useSyncExternalStore } from "react";

import { useWorkspace } from "@/components/authenticated-shell";
import { decisionFeedPage, type ProviderStatus } from "@/lib/decision-intelligence";
import {
  displayTimeZones,
  isDisplayTimeZone,
  rememberLocale,
  type DisplayPreferences,
} from "@/lib/display-preferences";
import { watchlistsHref } from "@/lib/monitoring";

type ProviderResult = { revision: number; provider?: ProviderStatus };

export function SettingsWorkspace() {
  const { dictionary, displayPreferences, locale, updateDisplayPreferences } = useWorkspace();
  const copy = dictionary.settings;
  const id = useId();
  const { theme, setTheme } = useTheme();
  const mounted = useSyncExternalStore(
    () => () => undefined,
    () => true,
    () => false,
  );
  const [notice, setNotice] = useState<{ title: string; tone: "success" | "warning" }>();
  const [revision, setRevision] = useState(0);
  const [result, setResult] = useState<ProviderResult>();
  const provider = result?.revision === revision ? result.provider : undefined;

  useEffect(() => {
    const controller = new AbortController();
    const { signal } = controller;
    void decisionFeedPage(null, signal, 1).then(
      ({ provider }) => {
        if (!signal.aborted) setResult({ revision, provider });
      },
      () => {
        if (!signal.aborted) setResult({ revision });
      },
    );
    return () => controller.abort();
  }, [revision]);

  function saveDisplay(patch: Partial<DisplayPreferences>) {
    setNotice(
      updateDisplayPreferences(patch)
        ? { title: copy.saved, tone: "success" }
        : { title: copy.storageUnavailable, tone: "warning" },
    );
  }

  return (
    <div className="settings-workspace">
      <ToastRegion
        label={copy.notifications}
        messages={
          notice
            ? [
                {
                  ...notice,
                  id: "display-settings",
                  action: (
                    <IconButton aria-label={copy.dismiss} onClick={() => setNotice(undefined)}>
                      <span aria-hidden="true">×</span>
                    </IconButton>
                  ),
                },
              ]
            : []
        }
      />
      <section className="settings-card" aria-labelledby={`${id}-display`}>
        <h2 id={`${id}-display`}>{copy.display}</h2>
        <p>{copy.displayScope}</p>
        <div className="settings-fields">
          <div>
            <span id={`${id}-language`}>{copy.language}</span>
            <nav aria-labelledby={`${id}-language`} className="accounting-navigation">
              <Link
                aria-current={locale === "fa" ? "page" : undefined}
                href="/fa/settings"
                hrefLang="fa"
                lang="fa"
                onNavigate={() => rememberLocale("fa")}
                prefetch={false}
              >
                فارسی
              </Link>
              <Link
                aria-current={locale === "en" ? "page" : undefined}
                href="/en/settings"
                hrefLang="en"
                lang="en"
                onNavigate={() => rememberLocale("en")}
                prefetch={false}
              >
                English
              </Link>
            </nav>
          </div>
          <FormField id={`${id}-theme`} label={copy.theme}>
            <Select
              disabled={!mounted}
              id={`${id}-theme`}
              value={mounted && theme ? theme : "system"}
              options={Object.entries(copy.themes).map(([value, label]) => ({ value, label }))}
              onValueChange={setTheme}
            />
          </FormField>
          <FormField id={`${id}-time-zone`} label={copy.timeZone} description={copy.timeZoneHint}>
            <Select
              aria-describedby={`${id}-time-zone-description`}
              id={`${id}-time-zone`}
              options={displayTimeZones.map((value) => ({ value, label: copy.timeZones[value] }))}
              value={displayPreferences.timeZone}
              onValueChange={(value) => {
                if (isDisplayTimeZone(value)) saveDisplay({ timeZone: value });
              }}
            />
          </FormField>
          <FormField id={`${id}-sidebar`} label={copy.sidebar}>
            <Select
              id={`${id}-sidebar`}
              options={Object.entries(copy.sidebarStates).map(([value, label]) => ({
                value,
                label,
              }))}
              value={displayPreferences.sidebarCollapsed ? "collapsed" : "expanded"}
              onValueChange={(value) => saveDisplay({ sidebarCollapsed: value === "collapsed" })}
            />
          </FormField>
        </div>
      </section>
      <section className="settings-card" aria-labelledby={`${id}-monitoring`}>
        <h2 id={`${id}-monitoring`}>{copy.monitoring}</h2>
        <p>{copy.monitoringHint}</p>
        <Link className="secondary-button" href={watchlistsHref(locale)}>
          {copy.openMonitoring}
        </Link>
      </section>
      <section className="settings-card" aria-labelledby={`${id}-provider`}>
        <h2 id={`${id}-provider`}>{copy.provider}</h2>
        {result?.revision !== revision ? <Spinner label={copy.providerLoading} /> : null}
        {result?.revision === revision && !provider ? (
          <ErrorState
            title={copy.providerError}
            action={
              <Button onClick={() => setRevision((value) => value + 1)} variant="secondary">
                {copy.retry}
              </Button>
            }
          />
        ) : null}
        {provider ? (
          <>
            <Alert role="status" tone={provider.state === "ready" ? "success" : "warning"}>
              <strong>{copy.providerStates[provider.state]}</strong>
              <p>{dictionary.decisionFeed.providerStates[provider.state]}</p>
            </Alert>
            <dl className="accounting-evidence">
              <div>
                <dt>{copy.providerVersion}</dt>
                <dd>
                  {provider.provider_version ? (
                    <bdi>{provider.provider_version}</bdi>
                  ) : (
                    copy.unavailable
                  )}
                </dd>
              </div>
              <div>
                <dt>{copy.providerContract}</dt>
                <dd>
                  {provider.contract_version ? (
                    <bdi>{provider.contract_version}</bdi>
                  ) : (
                    copy.unavailable
                  )}
                </dd>
              </div>
            </dl>
          </>
        ) : null}
      </section>
    </div>
  );
}
