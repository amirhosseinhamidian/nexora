from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
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
from nexora.risk_gate_explanation import RiskGateEvidenceInvalid, RiskGateExplanationService
from nexora.security_config import SecuritySettings
from pydantic import SecretStr

ORIGIN = "https://nexora.private"
OWNER_ID = UUID("113f777b-f75b-46e5-91da-91d9601c03ea")
SESSION_ID = UUID("549b8f36-d335-43c5-8227-7fd40ea74268")
NOW = datetime(2026, 11, 15, 10, tzinfo=UTC)
EVALUATION_ID = "decision-evaluation-0123456789abcdef"
CANDIDATE_ID = "decision-candidate-0123456789abcdef"


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def _risk_payload(*, rejected: bool = True) -> dict[str, object]:
    decision = "rejected" if rejected else "approved"
    disposition = "rejected" if rejected else "accepted"
    reason_codes = ["risk_policy_rejected"] if rejected else []
    checks = [
        {
            "name": "candidate_fresh",
            "passed": True,
            "actual_value": NOW.isoformat(),
            "limit_value": "<2026-11-15T11:00:00+00:00",
            "explanation": "Candidate remains inside its immutable validity interval.",
        },
        {
            "name": "ranking_score",
            "passed": not rejected,
            "actual_value": "0.250000" if rejected else "0.750000",
            "limit_value": "0.300000",
            "explanation": "Deterministic ranking score must meet the policy floor.",
        },
        {
            "name": "reward_risk",
            "passed": True,
            "actual_value": "2.000000",
            "limit_value": "1.500000",
            "explanation": "Reward-to-risk ratio must meet the policy floor.",
        },
        {
            "name": "risk_budget",
            "passed": True,
            "actual_value": "0.010000",
            "limit_value": "0.020000",
            "explanation": "Candidate risk must remain inside the offline policy budget.",
        },
        {
            "name": "notional_cap",
            "passed": True,
            "actual_value": "1000.000000",
            "limit_value": "5000.000000",
            "explanation": "Candidate notional must remain inside the offline cap.",
        },
    ]
    outcome = {
        "schema_version": "decision-stage-outcome-v1",
        "outcome_id": "decision-outcome-0123456789abcdef",
        "evaluation_id": EVALUATION_ID,
        "stage": "risk_gate",
        "disposition": disposition,
        "reason_codes": reason_codes,
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
        "ranking_score": "0.250000" if rejected else "0.750000",
        "decision": decision,
        "checks": checks,
        "position_sizing": None if rejected else {"redacted_by_nexora": True},
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
        "approved_candidate_id": None if rejected else CANDIDATE_ID,
        "evaluated_at": NOW.isoformat(),
        "offline_only": True,
        "external_order_submission_allowed": False,
        "record_checksum": "6" * 64,
    }
    return {
        "resource_schema_version": "trd-bot-risk-gate-v1",
        "evaluation_id": EVALUATION_ID,
        "outcome_id": outcome["outcome_id"],
        "record_schema_version": "decision-risk-gate-record-v1",
        "candidate_ranking_checksum": "5" * 64,
        "policy_version": "decision-risk-v1",
        "policy_checksum": "3" * 64,
        "disposition": disposition,
        "decision": decision,
        "assessment_id": assessment["assessment_id"],
        "assessment_checksum": "4" * 64,
        "approved_candidate_id": None if rejected else CANDIDATE_ID,
        "has_position_sizing": not rejected,
        "evaluated_at": NOW.isoformat(),
        "offline_only": True,
        "external_order_submission_allowed": False,
        "record_checksum": "6" * 64,
        "record": record,
    }


def _record(*, rejected: bool = True) -> dict[str, object]:
    payload = _risk_payload(rejected=rejected)
    return DecisionProjectionRecord(
        resource_type=ResourceType.RISK_GATE,
        resource_id=EVALUATION_ID,
        decision_kind=DecisionKind.RISK_ASSESSMENT,
        provider_release="0.3.1",
        source_schema_version="trd-bot-risk-gate-v1",
        source_observed_at=NOW,
        source_checksum="sha256:" + "a" * 64,
        aggregate_type="risk_gate",
        aggregate_id=EVALUATION_ID,
        aggregate_version=1,
        payload=payload,
        payload_sha256=canonical_json_sha256(payload),
    ).model_dump(mode="json")


def _snapshot(*records: dict[str, object]) -> ActiveDecisionProjection:
    return ActiveDecisionProjection(
        generation=4,
        trigger="cursor_expired",
        provider_version="0.3.1",
        contract_version="nexora-trd-integration-v1",
        projection={f"record:{index}": record for index, record in enumerate(records)},
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


def test_explanation_preserves_provider_policy_reasons_checks_and_missing_uncertainty() -> None:
    repository = Mock()
    repository.active_snapshot.return_value = _snapshot(_record())
    service = RiskGateExplanationService(
        repository,
        TrdBotIntegrationMode.ENABLED_COMPATIBLE_PROVIDER,
    )

    response = service.detail(OWNER_ID, EVALUATION_ID)

    assert response.provider.state == "ready"
    assert response.risk_gate is not None
    explanation = response.risk_gate
    assert explanation.policy.version == "decision-risk-v1"
    assert explanation.policy.checksum == "3" * 64
    assert [(reason.namespace, reason.code) for reason in explanation.provider_reason_codes] == [
        ("trd_bot", "risk_policy_rejected")
    ]
    assert [(check.name, check.passed) for check in explanation.checks] == [
        ("candidate_fresh", True),
        ("ranking_score", False),
        ("reward_risk", True),
        ("risk_budget", True),
        ("notional_cap", True),
    ]
    assert explanation.uncertainty.state == "not_supplied"
    assert explanation.uncertainty.reason_code == "TRD_BOT_RISK_UNCERTAINTY_NOT_SUPPLIED"
    assert explanation.uncertainty.value is None
    assert explanation.source.resource_type == "risk_gate"
    assert explanation.position_sizing_exposed is False
    assert explanation.external_order_submission_allowed is False


def test_inconsistent_provider_risk_evidence_fails_closed() -> None:
    repository = Mock()
    record = _record()
    payload = record["payload"]
    assert isinstance(payload, dict)
    payload["policy_checksum"] = "9" * 64
    record["payload_sha256"] = canonical_json_sha256(payload)
    repository.active_snapshot.return_value = _snapshot(record)
    service = RiskGateExplanationService(
        repository,
        TrdBotIntegrationMode.ENABLED_COMPATIBLE_PROVIDER,
    )

    with pytest.raises(RiskGateEvidenceInvalid, match="risk gate evidence is invalid"):
        service.detail(OWNER_ID, EVALUATION_ID)


def test_incomplete_provider_check_set_fails_closed() -> None:
    repository = Mock()
    record = _record()
    payload = record["payload"]
    assert isinstance(payload, dict)
    provider_record = payload["record"]
    assert isinstance(provider_record, dict)
    assessment = provider_record["assessment"]
    assert isinstance(assessment, dict)
    checks = assessment["checks"]
    assert isinstance(checks, list)
    checks.pop()
    record["payload_sha256"] = canonical_json_sha256(payload)
    repository.active_snapshot.return_value = _snapshot(record)
    service = RiskGateExplanationService(
        repository,
        TrdBotIntegrationMode.ENABLED_COMPATIBLE_PROVIDER,
    )

    with pytest.raises(RiskGateEvidenceInvalid, match="risk gate evidence is invalid"):
        service.detail(OWNER_ID, EVALUATION_ID)


@pytest.mark.anyio
async def test_risk_gate_api_is_authenticated_and_owner_scoped() -> None:
    repository = Mock()
    repository.active_snapshot.return_value = _snapshot(_record(rejected=False))
    application = _application(repository)

    async with AsyncClient(transport=ASGITransport(app=application), base_url=ORIGIN) as client:
        unauthorized = await client.get(f"/v1/risk-gates/{EVALUATION_ID}")
        client.cookies.set("__Host-nexora_session", "s" * 43, domain="nexora.private", path="/")
        response = await client.get(f"/v1/risk-gates/{EVALUATION_ID}")

    assert unauthorized.status_code == 401
    assert response.status_code == 200
    assert response.json()["risk_gate"]["decision"] == "approved"
    assert response.json()["risk_gate"]["provider_reason_codes"] == []
    assert repository.active_snapshot.call_args.args == (OWNER_ID,)
