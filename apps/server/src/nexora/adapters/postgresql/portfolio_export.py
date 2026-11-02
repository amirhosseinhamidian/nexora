from __future__ import annotations

import hashlib
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any, cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from nexora.adapters.postgresql.models import (
    AccountRecord,
    AssetIdentifierRecord,
    AssetRecord,
    FxRateObservationRecord,
    HoldingProjectionRecord,
    HoldingsRebuildIssueRecord,
    HoldingsRebuildRecord,
    ImmutableSourceEvidence,
    ImportBatchRecord,
    ImportRowRecord,
    LotConsumptionRecord,
    LotProjectionRecord,
    ManualValuationRecord,
    PortfolioRecord,
    PriceObservationRecord,
    ReconciliationCaseRecord,
    ReconciliationDecisionRecord,
    SourceReference,
    TransactionLegRecord,
    TransactionRecord,
    TrdBotSyncReceipt,
)
from nexora.adapters.postgresql.paper_shadow_projection import PaperShadowProjectionRepository
from nexora.adapters.postgresql.performance import PortfolioPerformanceRepository
from nexora.holdings_projection import CostBasisMethod
from nexora.performance import PerformanceSeries, PortfolioAnalyticsSnapshot
from nexora.portfolio_export import (
    MAX_EXPORT_RECORDS,
    JsonRecord,
    JsonValue,
    PortfolioExportCapacityExceeded,
    PortfolioExportProfile,
    PortfolioExportSnapshot,
)

DATASET_MODELS: tuple[tuple[str, type[Any]], ...] = (
    ("source_references", SourceReference),
    ("immutable_source_evidence", ImmutableSourceEvidence),
    ("trd_bot_sync_receipts", TrdBotSyncReceipt),
    ("assets", AssetRecord),
    ("asset_identifiers", AssetIdentifierRecord),
    ("portfolios", PortfolioRecord),
    ("accounts", AccountRecord),
    ("transactions", TransactionRecord),
    ("transaction_legs", TransactionLegRecord),
    ("import_batches", ImportBatchRecord),
    ("import_rows", ImportRowRecord),
    ("reconciliation_cases", ReconciliationCaseRecord),
    ("reconciliation_decisions", ReconciliationDecisionRecord),
    ("holdings_rebuilds", HoldingsRebuildRecord),
    ("holdings", HoldingProjectionRecord),
    ("lots", LotProjectionRecord),
    ("lot_consumptions", LotConsumptionRecord),
    ("holdings_rebuild_issues", HoldingsRebuildIssueRecord),
    ("price_observations", PriceObservationRecord),
    ("fx_rate_observations", FxRateObservationRecord),
    ("manual_valuations", ManualValuationRecord),
)

AI_SAFE_EXCLUDED_FIELDS: Mapping[str, frozenset[str]] = {
    "source_references": frozenset({"source_entity_id", "correlation_id"}),
    "immutable_source_evidence": frozenset({"payload"}),
    "trd_bot_sync_receipts": frozenset({"event_id", "envelope"}),
    "accounts": frozenset({"external_reference"}),
    "transactions": frozenset({"idempotency_key", "source_reference", "memo", "correction_reason"}),
    "transaction_legs": frozenset({"external_counterparty", "memo"}),
    "import_batches": frozenset({"review_reason"}),
    "import_rows": frozenset({"external_row_id", "normalized_payload"}),
    "reconciliation_cases": frozenset({"reason"}),
    "reconciliation_decisions": frozenset({"reason"}),
    "price_observations": frozenset({"source_reference", "idempotency_key"}),
    "fx_rate_observations": frozenset({"source_reference", "idempotency_key"}),
    "manual_valuations": frozenset({"reason", "source_reference", "idempotency_key"}),
}


def _decimal_text(value: Decimal) -> str:
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return "0" if text in {"", "-0"} else text


def _json_value(value: object) -> JsonValue:
    if value is None or isinstance(value, (str, int, bool)):
        return value
    if isinstance(value, float):
        raise TypeError("binary floating-point is forbidden in portfolio exports")
    if isinstance(value, Decimal):
        return _decimal_text(value)
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, datetime):
        if value.tzinfo is None:
            raise TypeError("export timestamps must be timezone-aware")
        return value.astimezone(UTC).isoformat().replace("+00:00", "Z")
    if isinstance(value, Enum):
        return str(value.value)
    if isinstance(value, Mapping):
        return {str(key): _json_value(item) for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    raise TypeError(f"unsupported portfolio export value: {type(value).__name__}")


def _json_record(value: object) -> JsonRecord:
    result = _json_value(value)
    if not isinstance(result, dict):
        raise TypeError("portfolio export record must be a JSON object")
    return result


def _record(dataset: str, row: object, profile: PortfolioExportProfile) -> JsonRecord:
    excluded = (
        AI_SAFE_EXCLUDED_FIELDS.get(dataset, frozenset()) if profile is PortfolioExportProfile.AI_SAFE else frozenset()
    )
    result: JsonRecord = {}
    table = cast(Any, row).__table__
    for column in table.columns:
        name = str(column.key)
        if name == "owner_id" or name in excluded:
            continue
        result[name] = _json_value(getattr(row, name))
    return result


def _analytics_record(snapshot: PortfolioAnalyticsSnapshot) -> JsonRecord:
    return {
        "portfolio_id": str(snapshot.portfolio_id),
        "base_asset_id": str(snapshot.base_asset_id),
        "as_of": _json_value(snapshot.as_of),
        "cost_basis_method": snapshot.cost_basis_method.value,
        "policy_version": snapshot.policy_version,
        "journal_sha256": snapshot.journal_sha256,
        "journal_transaction_count": snapshot.journal_transaction_count,
        "state": snapshot.state.value,
        "nav": _json_value(snapshot.nav),
        "priced_value": _json_value(snapshot.priced_value),
        "realized_pnl": _json_value(snapshot.realized_pnl),
        "unrealized_pnl": _json_value(snapshot.unrealized_pnl),
        "positions": [
            {
                "account_id": str(item.account_id),
                "asset_id": str(item.asset_id),
                "quantity": _json_value(item.quantity),
                "state": item.valuation.state.value,
                "evidence_kind": item.valuation.evidence_kind.value,
                "unit_value": _json_value(item.valuation.unit_value),
                "evidence_ids": [str(value) for value in item.valuation.evidence_ids],
                "evidence_at": _json_value(item.valuation.evidence_at),
                "valid_until": _json_value(item.valuation.valid_until),
                "source_references": list(item.valuation.source_references),
                "market_value": _json_value(item.market_value),
                "basis_status": item.basis_status.value,
                "cost_basis_asset_id": _json_value(item.cost_basis_asset_id),
                "cost_basis": _json_value(item.cost_basis),
                "cost_basis_in_base": _json_value(item.cost_basis_in_base),
                "unrealized_pnl": _json_value(item.unrealized_pnl),
            }
            for item in snapshot.positions
        ],
        "realized_events": [
            {
                "transaction_id": str(item.transaction_id),
                "occurred_at": _json_value(item.occurred_at),
                "proceeds_in_base": _json_value(item.proceeds_in_base),
                "cost_basis_in_base": _json_value(item.cost_basis_in_base),
                "realized_pnl": _json_value(item.realized_pnl),
                "state": item.state.value,
                "reason_code": item.reason_code,
            }
            for item in snapshot.realized_events
        ],
    }


def _performance_record(series: PerformanceSeries) -> JsonRecord:
    return {
        "portfolio_id": str(series.portfolio_id),
        "base_asset_id": str(series.base_asset_id),
        "cost_basis_method": series.cost_basis_method.value,
        "policy_version": series.policy_version,
        "start_at": _json_value(series.start_at),
        "end_at": _json_value(series.end_at),
        "points": [
            {
                "as_of": _json_value(item.as_of),
                "nav": _json_value(item.nav),
                "external_flow": _json_value(item.external_flow),
                "period_return": _json_value(item.period_return),
                "cumulative_return": _json_value(item.cumulative_return),
                "state": item.state.value,
                "reason_code": item.reason_code,
            }
            for item in series.points
        ],
    }


class PostgreSQLPortfolioExportSource:
    """Capture one repeatable-read, owner-scoped financial export snapshot."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def snapshot(
        self,
        *,
        owner_id: UUID,
        profile: PortfolioExportProfile,
        captured_at: datetime,
    ) -> PortfolioExportSnapshot:
        if captured_at.tzinfo is None or captured_at.utcoffset() != UTC.utcoffset(captured_at):
            raise ValueError("export capture timestamp must be timezone-aware UTC")
        datasets: dict[str, tuple[JsonRecord, ...]] = {}
        total = 0
        with self._session_factory() as session:
            connection = session.connection(execution_options={"isolation_level": "REPEATABLE READ"})
            snapshot_factory = sessionmaker(
                bind=connection,
                class_=Session,
                expire_on_commit=False,
                join_transaction_mode="create_savepoint",
            )
            for name, model in DATASET_MODELS:
                remaining = MAX_EXPORT_RECORDS - total
                statement = (
                    select(model)
                    .where(model.owner_id == owner_id)
                    .order_by(*model.__table__.primary_key.columns)
                    .limit(remaining + 1)
                )
                rows = tuple(session.execute(statement).scalars())
                if len(rows) > remaining:
                    raise PortfolioExportCapacityExceeded("complete export exceeds the source record budget")
                datasets[name] = tuple(_record(name, row, profile) for row in rows)
                total += len(rows)

            performance_repository = PortfolioPerformanceRepository(snapshot_factory)
            paper_shadow_repository = PaperShadowProjectionRepository(snapshot_factory)
            portfolios = datasets["portfolios"]
            analytics = tuple(
                _analytics_record(
                    performance_repository.snapshot(
                        owner_id=owner_id,
                        portfolio_id=UUID(str(portfolio["portfolio_id"])),
                        as_of=captured_at,
                        cost_basis_method=CostBasisMethod.FIFO,
                    )
                )
                for portfolio in portfolios
            )
            performance = tuple(
                _performance_record(
                    performance_repository.performance_series(
                        owner_id=owner_id,
                        portfolio_id=UUID(str(portfolio["portfolio_id"])),
                        start_at=captured_at - timedelta(days=30),
                        end_at=captured_at,
                        point_count=31,
                        cost_basis_method=CostBasisMethod.FIFO,
                    )
                )
                for portfolio in portfolios
            )
            projection = paper_shadow_repository.rebuild(owner_id=owner_id)
            projection_payload = projection.model_dump(mode="json")
            datasets["portfolio_analytics"] = analytics
            datasets["performance_series"] = performance
            datasets["paper_shadow_portfolios"] = tuple(_json_record(item) for item in projection_payload["portfolios"])
            datasets["paper_shadow_positions"] = tuple(_json_record(item) for item in projection_payload["positions"])
            datasets["paper_shadow_issues"] = tuple(_json_record(item) for item in projection_payload["issues"])

        open_reconciliation = sum(1 for item in datasets["reconciliation_cases"] if item.get("state") == "open")
        quarantined_rows = sum(1 for item in datasets["import_rows"] if item.get("status") == "quarantined")
        analytics_states = {
            state: sum(1 for item in analytics if item.get("state") == state)
            for state in ("complete", "stale", "missing")
        }
        excluded_fields = (
            tuple(
                sorted(f"{dataset}.{field}" for dataset, fields in AI_SAFE_EXCLUDED_FIELDS.items() for field in fields)
            )
            if profile is PortfolioExportProfile.AI_SAFE
            else ()
        )
        return PortfolioExportSnapshot(
            captured_at=captured_at,
            profile=profile,
            owner_scope_checksum=hashlib.sha256(f"nexora-owner-scope-v1:{owner_id}".encode()).hexdigest(),
            datasets=datasets,
            lineage={
                "source_reference_count": len(datasets["source_references"]),
                "immutable_evidence_count": len(datasets["immutable_source_evidence"]),
                "trd_bot_sync_receipt_count": len(datasets["trd_bot_sync_receipts"]),
                "journal_transaction_count": len(datasets["transactions"]),
                "paper_shadow_projection_sha256": projection.projection_sha256,
            },
            uncertainty={
                "paper_shadow_complete": projection.complete,
                "paper_shadow_issue_count": len(projection.issues),
                "open_reconciliation_case_count": open_reconciliation,
                "quarantined_import_row_count": quarantined_rows,
                "holdings_rebuild_issue_count": len(datasets["holdings_rebuild_issues"]),
                "portfolio_analytics_states": cast(JsonValue, analytics_states),
            },
            excluded_fields=excluded_fields,
        )
