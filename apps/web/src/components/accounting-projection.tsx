import {
  Alert,
  Button,
  Disclosure,
  EmptyState,
  FormField,
  ResponsiveRecordList,
  Select,
} from "@nexora/ui/primitives";
import { useId, type ReactNode } from "react";

import type { PortfolioWorkspaceContext } from "@/components/portfolio-dashboard";
import { WorkspaceTime } from "@/components/workspace-time";
import type { Locale } from "@/i18n/config";
import type { Dictionary } from "@/i18n/dictionaries";
import {
  exactDecimal,
  type AccountingData,
  type CostBasisMethod,
} from "@/lib/portfolio-accounting";
import { localizeDigits } from "@/lib/portfolio-analytics";

export function AccountingProjection({
  basis,
  busy,
  context,
  copy,
  data,
  locale,
  onBasisChange,
  onRebuild,
}: {
  basis: CostBasisMethod;
  busy: boolean;
  context: PortfolioWorkspaceContext;
  copy: Dictionary["portfolioOperations"];
  data: Extract<AccountingData, { view: "holdings" | "lots" }>;
  locale: Locale;
  onBasisChange: (basis: CostBasisMethod) => void;
  onRebuild: () => void;
}) {
  const fieldId = useId();
  const positions = data.view === "holdings";
  const title = positions ? copy.holdings.positions : copy.holdings.lots;
  const checkpoint = data.projection?.checkpoint;
  const assets = new Map(context.assets.map((asset) => [asset.asset_id, asset]));
  const accounts = new Map(context.accounts.map((account) => [account.account_id, account.name]));
  const rows = data.projection?.items ?? [];
  const amount = (value: string | null, assetId: string | null) => {
    if (value === null) return "—";
    return (
      <bdi dir="ltr">
        {exactDecimal(value, locale)} {assetId ? (assets.get(assetId)?.symbol ?? assetId) : ""}
      </bdi>
    );
  };

  return (
    <>
      <div className="panel-heading holdings-controls">
        <div>
          <h3>{title}</h3>
          <p>{copy.holdings.description}</p>
        </div>
        <div className="accounting-controls">
          <FormField id={fieldId} label={copy.holdings.method}>
            <Select
              disabled={busy}
              id={fieldId}
              onValueChange={(value) => {
                if (value === "fifo" || value === "weighted_average") onBasisChange(value);
              }}
              options={[
                { value: "fifo", label: copy.holdings.fifo },
                { value: "weighted_average", label: copy.holdings.weightedAverage },
              ]}
              value={basis}
            />
          </FormField>
          <Button disabled={busy} onClick={onRebuild} variant="secondary">
            {copy.holdings.rebuild}
          </Button>
        </div>
      </div>
      {!checkpoint ? (
        <Alert className="projection-empty" tone="warning">
          {copy.holdings.notBuilt}
        </Alert>
      ) : (
        <>
          <Disclosure className="accounting-disclosure" label={copy.holdings.checkpoint} open>
            <dl className="projection-checkpoint">
              <div>
                <dt>{copy.holdings.version}</dt>
                <dd>
                  <code dir="ltr">{checkpoint.projection_version}</code>
                </dd>
              </div>
              <div>
                <dt>{copy.holdings.transactions}</dt>
                <dd>{localizeDigits(String(checkpoint.journal_transaction_count), locale)}</dd>
              </div>
              <div>
                <dt>{copy.holdings.rebuiltAt}</dt>
                <dd>
                  <WorkspaceTime dateTime={checkpoint.rebuilt_at} locale={locale} />
                </dd>
              </div>
              <div>
                <dt>{copy.holdings.journalChecksum}</dt>
                <dd>
                  <code dir="ltr">{checkpoint.journal_sha256}</code>
                </dd>
              </div>
            </dl>
          </Disclosure>
          {rows.length === 0 ? (
            <EmptyState title={positions ? copy.holdings.empty : copy.holdings.noLots} />
          ) : (
            <ResponsiveRecordList className="responsive-data-grid" label={title}>
              {rows.map((row) => {
                const isLot = "lot_key" in row;
                const asset = assets.get(row.asset_id);
                let details: [string, ReactNode][];
                if (isLot) {
                  details = [
                    [
                      copy.holdings.acquired,
                      <WorkspaceTime key="acquired" dateTime={row.acquired_at} locale={locale} />,
                    ],
                    [copy.holdings.originalQuantity, amount(row.original_quantity, row.asset_id)],
                    [copy.holdings.remaining, amount(row.remaining_quantity, row.asset_id)],
                    [
                      copy.holdings.costBasis,
                      amount(row.remaining_cost_basis, row.cost_basis_asset_id),
                    ],
                    [
                      copy.holdings.acquisitionRecord,
                      <code dir="ltr" key="acquisition">
                        {row.acquisition_transaction_id}
                      </code>,
                    ],
                  ];
                } else {
                  details = [
                    [copy.holdings.quantity, amount(row.quantity, row.asset_id)],
                    [
                      copy.holdings.costBasis,
                      amount(row.total_cost_basis, row.cost_basis_asset_id),
                    ],
                    [
                      copy.holdings.unitCost,
                      amount(row.average_unit_cost, row.cost_basis_asset_id),
                    ],
                  ];
                }
                return (
                  <li
                    className="data-card"
                    key={isLot ? row.lot_key : `${row.account_id}:${row.asset_id}`}
                  >
                    <div>
                      <strong>{asset?.name ?? row.asset_id}</strong>
                      <span className={`basis-badge ${row.basis_status}`}>
                        {copy.basisStatus[row.basis_status]}
                      </span>
                    </div>
                    <dl>
                      <div>
                        <dt>{copy.holdings.account}</dt>
                        <dd>{accounts.get(row.account_id) ?? row.account_id}</dd>
                      </div>
                      {details.map(([label, value]) => (
                        <div key={label}>
                          <dt>{label}</dt>
                          <dd>{value}</dd>
                        </div>
                      ))}
                    </dl>
                  </li>
                );
              })}
            </ResponsiveRecordList>
          )}
        </>
      )}
    </>
  );
}
