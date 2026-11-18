import { Button, ResponsiveRecordList } from "@nexora/ui/primitives";
import Link from "next/link";

import type { Locale } from "@/i18n/config";
import type { Dictionary } from "@/i18n/dictionaries";
import {
  registryRecordId,
  type RegistryAsset,
  type RegistryRecord,
  type RegistrySection,
  type RegistrySnapshot,
} from "@/lib/portfolio-registry";

function recordDetails(
  record: RegistryRecord,
  snapshot: RegistrySnapshot,
  dictionary: Dictionary,
  locale: Locale,
): [string, string][] {
  const copy = dictionary.registry;
  const labels = dictionary.onboarding;
  if ("asset_id" in record) {
    return [
      [labels.symbol, record.symbol],
      [labels.assetClass, labels.assetClasses[record.asset_class]],
      [labels.precision, new Intl.NumberFormat(locale).format(record.precision)],
    ];
  }
  if ("account_id" in record) {
    const portfolio = snapshot.portfolios.find((item) => item.portfolio_id === record.portfolio_id);
    return [
      [copy.kind, labels.accountKinds[record.kind]],
      [copy.portfolio, portfolio?.name ?? copy.unavailable],
      [copy.institution, record.institution_name ?? copy.unspecified],
    ];
  }
  const asset = snapshot.assets.find((item) => item.asset_id === record.base_asset_id);
  return [
    [copy.kind, labels.portfolioKinds[record.kind]],
    [labels.baseAsset, asset ? `${asset.name} (${asset.symbol})` : copy.unavailable],
  ];
}

export function RegistryRecordList({
  busy,
  dictionary,
  locale,
  onAddIdentifier,
  onLifecycle,
  records,
  section,
  snapshot,
}: {
  busy: boolean;
  dictionary: Dictionary;
  locale: Locale;
  onAddIdentifier: (asset: RegistryAsset) => void;
  onLifecycle: (record: RegistryRecord) => void;
  records: RegistryRecord[];
  section: RegistrySection;
  snapshot: RegistrySnapshot;
}) {
  const copy = dictionary.registry;
  const sectionCopy = copy[section];
  return (
    <ResponsiveRecordList className="registry-records" label={sectionCopy.listLabel}>
      {records.map((record) => (
        <li className="registry-record" key={registryRecordId(record)}>
          <header className="registry-record__heading">
            <h3>
              <bdi>{record.name}</bdi>
            </h3>
            <span className={`status-badge ${record.status}`}>{copy.statuses[record.status]}</span>
          </header>
          <dl className="registry-record__details">
            {recordDetails(record, snapshot, dictionary, locale).map(([label, value]) => (
              <div key={label}>
                <dt>{label}</dt>
                <dd>
                  <bdi>{value}</bdi>
                </dd>
              </div>
            ))}
          </dl>
          {"base_asset_id" in record || record.status === "active" ? (
            <div className="registry-record__actions">
              {"base_asset_id" in record ? (
                <Link
                  className="nx-button nx-button--secondary nx-control--md"
                  href={`/${locale}/portfolios/${encodeURIComponent(record.portfolio_id)}`}
                >
                  {dictionary.workspacePages.openPortfolioDetails}
                </Link>
              ) : null}
              {"asset_id" in record && record.status === "active" ? (
                <Button disabled={busy} onClick={() => onAddIdentifier(record)} variant="secondary">
                  {copy.addIdentifier}
                </Button>
              ) : null}
              {record.status === "active" ? (
                <Button disabled={busy} onClick={() => onLifecycle(record)} variant="ghost">
                  {sectionCopy.action}
                </Button>
              ) : null}
            </div>
          ) : null}
        </li>
      ))}
    </ResponsiveRecordList>
  );
}
