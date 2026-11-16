from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from unittest.mock import Mock
from uuid import UUID

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from nexora.adapters.postgresql.decision_projection import ActiveDecisionProjection
from nexora.adapters.trd_bot import ResourceType, TrdBotIntegrationMode
from nexora.api import create_app
from nexora.composition import compose_application
from nexora.config import load_settings
from nexora.decision_event_projection import DecisionKind, DecisionProjectionRecord, canonical_json_sha256
from nexora.identity import AuthenticatedSession
from nexora.portfolio_candidate_impact import (
    PortfolioCandidateImpactService,
    PortfolioImpactEvidenceInvalid,
)
from nexora.security_config import SecuritySettings
from pydantic import SecretStr

ORIGIN = "https://nexora.private"
OWNER_ID = UUID("113f777b-f75b-46e5-91da-91d9601c03ea")
SESSION_ID = UUID("549b8f36-d335-43c5-8227-7fd40ea74268")
NOW = datetime(2026, 11, 16, 10, tzinfo=UTC)
EVALUATION_ID = "decision-evaluation-0123456789abcdef"
CANDIDATE_ID = "decision-candidate-0123456789abcdef"
RISK_CHECKSUM = "6" * 64


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def _risk_payload() -> dict[str, object]:
    check_names = (
        "candidate_fresh",
        "ranking_score",
        "reward_risk",
        "risk_budget",
        "notional_cap",
    )
    checks = [
        {
            "name": name,
            "passed": True,
            "actual_value": "1.000000",
            "limit_value": "1.000000",
            "explanation": "The provider-owned offline risk check passed.",
        }
        for name in check_names
    ]
    outcome = {
        "schema_version": "decision-stage-outcome-v1",
        "outcome_id": "decision-outcome-risk-0123456789abcdef",
        "evaluation_id": EVALUATION_ID,
        "stage": "risk_gate",
        "disposition": "accepted",
        "reason_codes": [],
        "evaluated_at": NOW.isoformat(),
        "offline_only": True,
        "external_order_submission_allowed": False,
        "outcome_checksum": "1" * 64,
    }
    assessment = {
        "schema_version": "decision-risk-assessment-v1",
        "assessment_id": "decision-risk-0123456789abcdef",
        "evaluation_id": EVALUATION_ID,
        "candidate_id": CANDIDATE_ID,
        "candidate_checksum": "2" * 64,
        "rank": 1,
        "ranking_score": "0.750000",
        "decision": "approved",
        "checks": checks,
        "position_sizing": {"redacted_by_nexora": True},
        "evaluated_at": NOW.isoformat(),
        "policy_checksum": "3" * 64,
        "offline_only": True,
        "external_order_submission_allowed": False,
        "assessment_checksum": "4" * 64,
    }
    record = {
        "schema_version": "decision-risk-gate-record-v1",
        "evaluation_id": EVALUATION_ID,
        "outcome": outcome,
        "candidate_ranking_checksum": "5" * 64,
        "policy_version": "decision-risk-v1",
        "policy_checksum": "3" * 64,
        "assessment": assessment,
        "approved_candidate_id": CANDIDATE_ID,
        "evaluated_at": NOW.isoformat(),
        "offline_only": True,
        "external_order_submission_allowed": False,
        "record_checksum": RISK_CHECKSUM,
    }
    return {
        "resource_schema_version": "trd-bot-risk-gate-v1",
        "evaluation_id": EVALUATION_ID,
        "outcome_id": outcome["outcome_id"],
        "record_schema_version": "decision-risk-gate-record-v1",
        "candidate_ranking_checksum": "5" * 64,
        "policy_version": "decision-risk-v1",
        "policy_checksum": "3" * 64,
        "disposition": "accepted",
        "decision": "approved",
        "assessment_id": assessment["assessment_id"],
        "assessment_checksum": "4" * 64,
        "approved_candidate_id": CANDIDATE_ID,
        "has_position_sizing": True,
        "evaluated_at": NOW.isoformat(),
        "offline_only": True,
        "external_order_submission_allowed": False,
        "record_checksum": RISK_CHECKSUM,
        "record": record,
    }


def _portfolio_payload(*, unavailable: bool = False) -> dict[str, object]:
    outcome = {
        "schema_version": "decision-stage-outcome-v1",
        "outcome_id": "decision-outcome-portfolio-0123456789abcdef",
        "evaluation_id": EVALUATION_ID,
        "stage": "portfolio_simulation",
        "disposition": "unavailable" if unavailable else "rejected",
        "reason_codes": ["portfolio_unavailable"] if unavailable else ["portfolio_policy_rejected"],
        "evaluated_at": NOW.isoformat(),
        "offline_only": True,
        "external_order_submission_allowed": False,
        "outcome_checksum": "7" * 64,
    }
    checks = [
        {
            "name": name,
            "passed": name != "candidate_correlation",
            "actual_value": "unavailable" if name == "candidate_correlation" else "0.100000",
            "limit_value": "0.850000",
            "explanation": "Provider-owned deterministic portfolio policy evidence.",
        }
        for name in (
            "portfolio_active",
            "portfolio_capacity",
            "projected_exposure",
            "projected_concentration",
            "candidate_correlation",
            "scenario_loss",
            "regime_alignment",
        )
    ]
    snapshot: dict[str, object] = {
        "schema_version": "decision-portfolio-snapshot-v1",
        "snapshot_id": "decision-portfolio-snapshot-0123456789abcdef",
        "source": "empty_baseline",
        "portfolio_id": None,
        "mode": "paper",
        "dataset_id": "dataset-1",
        "status": "active",
        "as_of": NOW.isoformat(),
        "starting_equity": "10000.00000000",
        "cash": "10000.00000000",
        "equity": "10000.00000000",
        "open_positions": [],
        "snapshot_checksum": "8" * 64,
    }
    scenarios = [
        {
            "shock_fraction": shock,
            "existing_pnl": "0.00000000",
            "candidate_pnl": pnl,
            "projected_equity": equity,
            "loss_fraction": loss,
        }
        for shock, pnl, equity, loss in (
            ("-0.100000", "-100.00000000", "9900.00000000", "0.010000"),
            ("-0.050000", "-50.00000000", "9950.00000000", "0.005000"),
            ("0.050000", "50.00000000", "10050.00000000", "0.000000"),
            ("0.100000", "100.00000000", "10100.00000000", "0.000000"),
        )
    ]
    analysis = None
    if not unavailable:
        analysis = {
            "schema_version": "decision-portfolio-analysis-v1",
            "analysis_id": "decision-portfolio-0123456789abcdef",
            "evaluation_id": EVALUATION_ID,
            "candidate_id": CANDIDATE_ID,
            "snapshot": snapshot,
            "exposure": {
                "current_gross_notional": "0.00000000",
                "candidate_notional": "1000.00000000",
                "projected_gross_notional": "1000.00000000",
                "current_exposure_fraction": "0.000000",
                "projected_exposure_fraction": "0.100000",
                "projected_asset_concentration_fraction": "0.100000",
            },
            "correlation": {
                "status": "unavailable",
                "maximum_absolute_correlation": None,
                "evidence": "Pinned data cannot estimate cross-asset correlation.",
            },
            "scenarios": scenarios,
            "checks": checks,
            "recommendation": "reject",
            "exit_recommendations": [],
            "policy_checksum": "9" * 64,
            "analyzed_at": NOW.isoformat(),
            "offline_only": True,
            "external_order_submission_allowed": False,
            "analysis_checksum": "a" * 64,
        }
    record = {
        "schema_version": "decision-portfolio-intelligence-record-v1",
        "evaluation_id": EVALUATION_ID,
        "outcome": outcome,
        "risk_gate_checksum": RISK_CHECKSUM,
        "policy_version": "decision-portfolio-v1",
        "policy_checksum": "9" * 64,
        "recommendation": "unavailable" if unavailable else "reject",
        "analysis": analysis,
        "analyzed_at": NOW.isoformat(),
        "offline_only": True,
        "external_order_submission_allowed": False,
        "record_checksum": "b" * 64,
    }
    return {
        "resource_schema_version": "trd-bot-portfolio-intelligence-v1",
        "evaluation_id": EVALUATION_ID,
        "outcome_id": outcome["outcome_id"],
        "record_schema_version": "decision-portfolio-intelligence-record-v1",
        "risk_gate_checksum": RISK_CHECKSUM,
        "policy_version": "decision-portfolio-v1",
        "policy_checksum": "9" * 64,
        "disposition": "unavailable" if unavailable else "rejected",
        "recommendation": "unavailable" if unavailable else "reject",
        "has_analysis": not unavailable,
        "snapshot_id": None if unavailable else snapshot["snapshot_id"],
        "candidate_id": None if unavailable else CANDIDATE_ID,
        "analyzed_at": NOW.isoformat(),
        "offline_only": True,
        "external_order_submission_allowed": False,
        "record_checksum": "b" * 64,
        "record": record,
    }


def _record(resource_type: ResourceType, payload: dict[str, object]) -> dict[str, object]:
    return DecisionProjectionRecord(
        resource_type=resource_type,
        resource_id=EVALUATION_ID,
        decision_kind=(
            DecisionKind.RISK_ASSESSMENT
            if resource_type is ResourceType.RISK_GATE
            else DecisionKind.PORTFOLIO_ASSESSMENT
        ),
        provider_release="0.3.1",
        source_schema_version=str(payload["resource_schema_version"]),
        source_observed_at=NOW,
        source_checksum="sha256:" + "c" * 64,
        aggregate_type=resource_type.value,
        aggregate_id=EVALUATION_ID,
        aggregate_version=1,
        payload=payload,
        payload_sha256=canonical_json_sha256(payload),
    ).model_dump(mode="json")


def _snapshot(*records: dict[str, object]) -> ActiveDecisionProjection:
    return ActiveDecisionProjection(
        generation=5,
        trigger="cursor_expired",
        provider_version="0.3.1",
        contract_version="nexora-trd-integration-v1",
        projection={f"record:{index}": record for index, record in enumerate(records)},
    )


def _accepted_snapshot(*, unavailable: bool = False) -> ActiveDecisionProjection:
    return _snapshot(
        _record(ResourceType.RISK_GATE, _risk_payload()),
        _record(ResourceType.PORTFOLIO_INTELLIGENCE, _portfolio_payload(unavailable=unavailable)),
    )


def _application(repository: Mock) -> FastAPI:
    identity = Mock()
    identity.authenticate_session.return_value = AuthenticatedSession(
        session_id=SESSION_ID,
        owner_id=OWNER_ID,
        rotation_required=False,
        recently_reauthenticated=True,
    )
    security = SecuritySettings(
        canonical_origin=ORIGIN,
        rp_id="nexora.private",
        auth_pepper=SecretStr("p" * 43),
        canonical_origin_file=Path("/run/secrets/nexora_origin"),
        auth_pepper_file=Path("/run/secrets/nexora_pepper"),
    )
    container = replace(
        compose_application(load_settings({})),
        identity_repository=identity,
        owner_identity_service=Mock(),
        security=security,
        decision_event_projection_repository=repository,
        trd_bot_integration_mode=TrdBotIntegrationMode.ENABLED_COMPATIBLE_PROVIDER,
    )
    return create_app(container=container)


def test_portfolio_impact_preserves_provider_analysis_and_explicit_uncertainty() -> None:
    repository = Mock()
    repository.active_snapshot.return_value = _accepted_snapshot()
    service = PortfolioCandidateImpactService(repository, TrdBotIntegrationMode.ENABLED_COMPATIBLE_PROVIDER)

    response = service.detail(OWNER_ID, EVALUATION_ID)

    assert response.provider.state == "ready"
    assert response.portfolio_impact is not None
    impact = response.portfolio_impact
    assert impact.policy.version == "decision-portfolio-v1"
    assert impact.recommendation == "reject"
    assert impact.analysis is not None
    assert [item.shock_fraction for item in impact.analysis.scenarios] == [
        Decimal("-0.100000"),
        Decimal("-0.050000"),
        Decimal("0.050000"),
        Decimal("0.100000"),
    ]
    assert [item.name for item in impact.analysis.checks] == [
        "portfolio_active",
        "portfolio_capacity",
        "projected_exposure",
        "projected_concentration",
        "candidate_correlation",
        "scenario_loss",
        "regime_alignment",
    ]
    assert impact.uncertainty.state == "not_supplied"
    assert impact.uncertainty.reason_code == "TRD_BOT_PORTFOLIO_UNCERTAINTY_NOT_SUPPLIED"
    assert impact.risk_gate_checksum_cross_validated is True
    assert impact.transaction_created is False
    assert impact.order_intent_created is False


def test_unavailable_portfolio_impact_is_explicit_and_not_fabricated() -> None:
    repository = Mock()
    repository.active_snapshot.return_value = _accepted_snapshot(unavailable=True)
    service = PortfolioCandidateImpactService(repository, TrdBotIntegrationMode.ENABLED_COMPATIBLE_PROVIDER)

    impact = service.detail(OWNER_ID, EVALUATION_ID).portfolio_impact

    assert impact is not None
    assert impact.recommendation == "unavailable"
    assert impact.analysis is None
    assert [reason.code for reason in impact.provider_reason_codes] == ["portfolio_unavailable"]


def test_incomplete_portfolio_scenario_set_fails_closed() -> None:
    repository = Mock()
    payload = _portfolio_payload()
    record = payload["record"]
    assert isinstance(record, dict)
    analysis = record["analysis"]
    assert isinstance(analysis, dict)
    scenarios = analysis["scenarios"]
    assert isinstance(scenarios, list)
    scenarios.pop()
    repository.active_snapshot.return_value = _snapshot(
        _record(ResourceType.RISK_GATE, _risk_payload()),
        _record(ResourceType.PORTFOLIO_INTELLIGENCE, payload),
    )
    service = PortfolioCandidateImpactService(repository, TrdBotIntegrationMode.ENABLED_COMPATIBLE_PROVIDER)

    with pytest.raises(PortfolioImpactEvidenceInvalid, match="portfolio impact evidence is invalid"):
        service.detail(OWNER_ID, EVALUATION_ID)


def test_mismatched_risk_gate_checksum_fails_closed() -> None:
    repository = Mock()
    payload = _portfolio_payload()
    payload["risk_gate_checksum"] = "d" * 64
    record = payload["record"]
    assert isinstance(record, dict)
    record["risk_gate_checksum"] = "d" * 64
    repository.active_snapshot.return_value = _snapshot(
        _record(ResourceType.RISK_GATE, _risk_payload()),
        _record(ResourceType.PORTFOLIO_INTELLIGENCE, payload),
    )
    service = PortfolioCandidateImpactService(repository, TrdBotIntegrationMode.ENABLED_COMPATIBLE_PROVIDER)

    with pytest.raises(PortfolioImpactEvidenceInvalid, match="risk lineage is invalid"):
        service.detail(OWNER_ID, EVALUATION_ID)


def test_missing_matching_risk_gate_fails_closed() -> None:
    repository = Mock()
    repository.active_snapshot.return_value = _snapshot(
        _record(ResourceType.PORTFOLIO_INTELLIGENCE, _portfolio_payload())
    )
    service = PortfolioCandidateImpactService(repository, TrdBotIntegrationMode.ENABLED_COMPATIBLE_PROVIDER)

    with pytest.raises(PortfolioImpactEvidenceInvalid, match="risk gate evidence is unavailable"):
        service.detail(OWNER_ID, EVALUATION_ID)


@pytest.mark.anyio
async def test_portfolio_impact_api_is_authenticated_and_owner_scoped() -> None:
    repository = Mock()
    repository.active_snapshot.return_value = _accepted_snapshot()
    application = _application(repository)

    async with AsyncClient(transport=ASGITransport(app=application), base_url=ORIGIN) as client:
        unauthorized = await client.get(f"/v1/portfolio-impacts/{EVALUATION_ID}")
        client.cookies.set("__Host-nexora_session", "s" * 43, domain="nexora.private", path="/")
        response = await client.get(f"/v1/portfolio-impacts/{EVALUATION_ID}")

    assert unauthorized.status_code == 401
    assert response.status_code == 200
    assert response.json()["portfolio_impact"]["recommendation"] == "reject"
    assert response.json()["portfolio_impact"]["risk_gate_checksum_cross_validated"] is True
    assert repository.active_snapshot.call_args.args == (OWNER_ID,)
