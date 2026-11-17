from __future__ import annotations

import hashlib
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any, cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.engine import Connection
from sqlalchemy.exc import InvalidRequestError
from sqlalchemy.orm import Session, sessionmaker

from nexora.adapters.postgresql.models import (
    AccountRecord,
    AlertStateHistoryRecord,
    AssetIdentifierRecord,
    AssetRecord,
    DecisionProjectionState,
    DecisionReviewDeliveryRecord,
    DecisionReviewRecord,
    DecisionReviewStateRecord,
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
    OutcomeJournalEntryRecord,
    OwnerAlertStateRecord,
    PortfolioRecord,
    PriceObservationRecord,
    ReconciliationCaseRecord,
    ReconciliationDecisionRecord,
    SourceReference,
    TransactionLegRecord,
    TransactionRecord,
    TrdBotSyncReceipt,
    WatchlistItemRecord,
    WatchlistOperationRecord,
    WatchlistPreferenceRecord,
    WatchlistRecord,
)
from nexora.adapters.postgresql.paper_shadow_projection import PaperShadowProjectionRepository
from nexora.adapters.postgresql.performance import PortfolioPerformanceRepository
from nexora.adapters.trd_bot import ResourceType
from nexora.holdings_projection import CostBasisMethod
from nexora.performance import PerformanceSeries, PortfolioAnalyticsSnapshot
from nexora.portfolio_export import (
    MAX_EXPORT_RECORDS,
    PHASE_THREE_REQUIRED_DATASETS,
    JsonRecord,
    JsonValue,
    PortfolioExportCapacityExceeded,
    PortfolioExportProfile,
    PortfolioExportSnapshot,
    canonical_json_sha256,
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
    ("decision_projection_states", DecisionProjectionState),
    ("decision_review_states", DecisionReviewStateRecord),
    ("human_reviews", DecisionReviewRecord),
    ("decision_review_deliveries", DecisionReviewDeliveryRecord),
    ("owner_alert_states", OwnerAlertStateRecord),
    ("alert_state_history", AlertStateHistoryRecord),
    ("watchlists", WatchlistRecord),
    ("watchlist_items", WatchlistItemRecord),
    ("watchlist_preferences", WatchlistPreferenceRecord),
    ("watchlist_operations", WatchlistOperationRecord),
    ("outcome_journal", OutcomeJournalEntryRecord),
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
    "decision_projection_states": frozenset({"projection", "resource_progress", "aggregate_versions", "quarantine"}),
    "human_reviews": frozenset({"reason_note", "idempotency_key", "request_sha256"}),
    "decision_review_deliveries": frozenset({"provider_command_id", "provider_correlation_id", "last_error_code"}),
    "alert_state_history": frozenset({"idempotency_key", "request_sha256"}),
    "watchlists": frozenset({"name"}),
    "watchlist_items": frozenset({"label"}),
    "watchlist_operations": frozenset({"idempotency_key", "request_sha256"}),
    "outcome_journal": frozenset({"content", "uncertainty_note", "idempotency_key", "request_sha256"}),
    "decision_records": frozenset({"payload"}),
    "portfolio_impacts": frozenset({"payload"}),
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


def _phase_three_projection_datasets(
    projection_states: tuple[JsonRecord, ...],
    profile: PortfolioExportProfile,
) -> tuple[tuple[JsonRecord, ...], tuple[JsonRecord, ...]]:
    decisions: list[JsonRecord] = []
    portfolio_impacts: list[JsonRecord] = []
    validated_states: list[tuple[int, str, str, str | None, JsonRecord]] = []
    for state in projection_states:
        generation = state.get("generation")
        state_id = state.get("projection_state_id")
        status = state.get("status")
        projection_sha256 = state.get("projection_sha256")
        if (
            not isinstance(generation, int)
            or isinstance(generation, bool)
            or not isinstance(state_id, str)
            or not isinstance(status, str)
            or (projection_sha256 is not None and not isinstance(projection_sha256, str))
        ):
            raise TypeError("decision projection export identity is invalid")
        validated_states.append((generation, state_id, status, projection_sha256, state))
    for generation, _, status, projection_sha256, state in sorted(
        validated_states, key=lambda item: (item[0], item[1])
    ):
        projection = state.get("projection")
        if not isinstance(projection, dict):
            raise TypeError("decision projection export source must be an object")
        for projection_key in sorted(projection):
            raw_record = projection[projection_key]
            if not isinstance(raw_record, dict):
                raise TypeError("decision projection export record must be an object")
            record = _json_record(raw_record)
            record["projection_generation"] = generation
            record["projection_status"] = status
            record["projection_sha256"] = projection_sha256
            if profile is PortfolioExportProfile.AI_SAFE:
                record.pop("payload", None)
            decisions.append(record)
            if record.get("resource_type") == ResourceType.PORTFOLIO_INTELLIGENCE.value:
                portfolio_impacts.append(dict(record))
    return tuple(decisions), tuple(portfolio_impacts)


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


def _repeatable_read_connection(session: Session) -> Connection:
    bind = session.get_bind()
    if isinstance(bind, Connection) and bind.in_transaction():
        isolation_level = bind.get_isolation_level().upper().replace("_", " ")
        if isolation_level != "REPEATABLE READ":
            raise InvalidRequestError(
                "portfolio export cannot join an existing transaction unless its isolation level is REPEATABLE READ"
            )
        return session.connection()
    return session.connection(execution_options={"isolation_level": "REPEATABLE READ"})


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
        raw_projection_states: tuple[JsonRecord, ...] = ()
        total = 0
        with self._session_factory() as session:
            connection = _repeatable_read_connection(session)
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
                if name == "decision_projection_states":
                    raw_projection_states = tuple(
                        _record(name, row, PortfolioExportProfile.PRIVATE_COMPLETE) for row in rows
                    )
                datasets[name] = tuple(_record(name, row, profile) for row in rows)
                total += len(rows)

            decision_records, portfolio_impacts = _phase_three_projection_datasets(
                raw_projection_states,
                profile,
            )
            datasets["decision_records"] = decision_records
            datasets["portfolio_impacts"] = portfolio_impacts
            total += len(decision_records) + len(portfolio_impacts)
            if total > MAX_EXPORT_RECORDS:
                raise PortfolioExportCapacityExceeded("complete export exceeds the source record budget")

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
        review_actions = {
            action: sum(1 for item in datasets["human_reviews"] if item.get("action") == action)
            for action in ("accept", "reject", "defer")
        }
        alert_states = {
            state: sum(1 for item in datasets["alert_state_history"] if item.get("state") == state)
            for state in ("open", "acknowledged", "snoozed", "resolved", "expired")
        }
        journal_uncertainty = {
            level: sum(1 for item in datasets["outcome_journal"] if item.get("uncertainty_level") == level)
            for level in ("low", "medium", "high", "unknown")
        }
        phase_three_dataset_sha256 = {
            name: canonical_json_sha256(list(datasets[name])) for name in sorted(PHASE_THREE_REQUIRED_DATASETS)
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
                "phase_three_dataset_sha256": cast(JsonValue, phase_three_dataset_sha256),
                "decision_record_count": len(datasets["decision_records"]),
                "human_review_count": len(datasets["human_reviews"]),
                "alert_history_count": len(datasets["alert_state_history"]),
                "outcome_journal_count": len(datasets["outcome_journal"]),
            },
            uncertainty={
                "paper_shadow_complete": projection.complete,
                "paper_shadow_issue_count": len(projection.issues),
                "open_reconciliation_case_count": open_reconciliation,
                "quarantined_import_row_count": quarantined_rows,
                "holdings_rebuild_issue_count": len(datasets["holdings_rebuild_issues"]),
                "portfolio_analytics_states": cast(JsonValue, analytics_states),
                "review_actions": cast(JsonValue, review_actions),
                "alert_states": cast(JsonValue, alert_states),
                "journal_uncertainty_levels": cast(JsonValue, journal_uncertainty),
            },
            excluded_fields=excluded_fields,
        )
