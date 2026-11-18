import { Disclosure, EmptyState, ResponsiveRecordList } from "@nexora/ui/primitives";

import type { PortfolioWorkspaceContext } from "@/components/portfolio-dashboard";
import type { Locale } from "@/i18n/config";
import type { Dictionary } from "@/i18n/dictionaries";
import { exactDecimal, type Transaction } from "@/lib/portfolio-accounting";
import { formatTimestamp } from "@/lib/portfolio-analytics";

export function AccountingJournal({
  context,
  copy,
  locale,
  transactions,
}: {
  context: PortfolioWorkspaceContext;
  copy: Dictionary["portfolioOperations"];
  locale: Locale;
  transactions: Transaction[];
}) {
  const accounts = new Map(context.accounts.map((account) => [account.account_id, account.name]));
  const assets = new Map(context.assets.map((asset) => [asset.asset_id, asset.symbol]));
  if (!transactions.length) {
    return (
      <EmptyState headingLevel={3} title={copy.journal.empty}>
        {copy.journal.description}
      </EmptyState>
    );
  }
  return (
    <>
      <h3>{copy.journal.title}</h3>
      <p>{copy.journal.description}</p>
      <ResponsiveRecordList className="operations-card-list" label={copy.journal.title}>
        {transactions.map((transaction) => (
          <li className="operation-card" key={transaction.transaction_id}>
            <div className="operation-card-heading">
              <div>
                <span className="status-badge active">
                  {copy.transactionKind[transaction.transaction_kind]}
                </span>
                {transaction.correction_kind ? (
                  <span className="status-badge archived">
                    {copy.correctionKind[transaction.correction_kind]}
                  </span>
                ) : null}
              </div>
              <time dateTime={transaction.occurred_at}>
                {formatTimestamp(transaction.occurred_at, locale)}
              </time>
            </div>
            <p>{transaction.memo ?? copy.journal.noMemo}</p>
            <ResponsiveRecordList className="journal-legs" label={copy.journal.legs}>
              {transaction.legs.map((leg) => (
                <li key={leg.transaction_leg_id}>
                  <span>
                    {leg.account_id
                      ? (accounts.get(leg.account_id) ?? leg.account_id)
                      : (leg.external_counterparty ?? copy.journal.external)}
                  </span>
                  <bdi dir="ltr">
                    {exactDecimal(leg.quantity, locale)} {assets.get(leg.asset_id) ?? leg.asset_id}
                  </bdi>
                </li>
              ))}
            </ResponsiveRecordList>
            <Disclosure className="accounting-disclosure" label={copy.journal.evidence}>
              <dl className="accounting-evidence">
                <div>
                  <dt>{copy.journal.recordId}</dt>
                  <dd>
                    <code dir="ltr">{transaction.transaction_id}</code>
                  </dd>
                </div>
                <div>
                  <dt>{copy.journal.source}</dt>
                  <dd>
                    {copy.sourceKind[transaction.source_kind]}{" "}
                    <bdi>{transaction.source_reference}</bdi>
                  </dd>
                </div>
                <div>
                  <dt>{copy.journal.recordedAt}</dt>
                  <dd>
                    <time dateTime={transaction.recorded_at}>
                      {formatTimestamp(transaction.recorded_at, locale)}
                    </time>
                  </dd>
                </div>
                {transaction.correction_of_transaction_id ? (
                  <div>
                    <dt>{copy.journal.previousRecord}</dt>
                    <dd>
                      <code dir="ltr">{transaction.correction_of_transaction_id}</code>
                    </dd>
                  </div>
                ) : null}
                {transaction.correction_reason ? (
                  <div>
                    <dt>{copy.reason}</dt>
                    <dd>
                      <bdi>{transaction.correction_reason}</bdi>
                    </dd>
                  </div>
                ) : null}
                {transaction.source_payload_sha256 ? (
                  <div>
                    <dt>{copy.journal.sourceChecksum}</dt>
                    <dd>
                      <code dir="ltr">{transaction.source_payload_sha256}</code>
                    </dd>
                  </div>
                ) : null}
              </dl>
            </Disclosure>
          </li>
        ))}
      </ResponsiveRecordList>
    </>
  );
}
