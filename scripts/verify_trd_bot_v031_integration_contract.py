#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "contracts/nexora-v0.1-trd-bot-v031-integration.json"
PROFILE_PATH = ROOT / "contracts/integration/v1/trd-bot-v0.3.1-provider-profile.json"
FREEZE_PATH = ROOT / "artifacts/p3-02/trd-bot-v031-integration-contract-freeze.json"
P3_01_FREEZE_PATH = ROOT / "artifacts/p3-01/decision-review-journal-domain-freeze.json"
P0_CONTRACT_PATH = ROOT / "contracts/integration/v1/integration-contract.json"
P0_OPENAPI_PATH = ROOT / "contracts/integration/v1/openapi.json"

P3_01_FREEZE_COMMIT = "9e84bc0c64bed12ff928c18f035df870bb31f5a3"
P3_01_CANDIDATE_COMMIT = "ffa4acd39806e72f7e53d16af7e9937c12e669c5"
P3_01_FREEZE_CHECKSUM = "d8535def20eefd0490f9bb06cc55b8bb90c9e3937e68f5997d4540bf48ae3e89"
P0_CONTRACT_CHECKSUM = "435e96fc928b71c5c98ebcb6f4e41a928f9f32e073c30ab567246f52c6d78c88"
P0_OPENAPI_CHECKSUM = "3c02fc3c47e8fb53e4a8f4f25fec2e5fbdd126e2b9d8c8318f05f6fd7c2b77e1"
PROFILE_CHECKSUM = "48cfcd61b8f2cb866e4c921d31f5c61db83d3f08e5123d690a069a57c3aba109"
TRD_BOT_V030_COMMIT = "bbb9fd4fbc25e25aa512a9fde1dda912321cdd33"
P3_02_CANDIDATE_COMMIT = "c32e2d6ef923413bb159615f8f980ca52207663b"
P3_02_CANDIDATE_TREE = "5cc823d27f768609d0bd408b2f496ec730bb3287"
P3_02_FREEZE_CHECKSUM = "720b7fbf735882f1660e623743f24d49f2587ed48ccbba64bef3ea0c00309c4f"
P3_02_PRIMARY_RUN_ID = 41866030157

EXPECTED_REGRESSION_RUNS = {
    "application_composition": 41866030145,
    "artifact_export_storage": 41866030184,
    "audit_observability": 41866030001,
    "authenticated_web_shell": 41866029839,
    "contracts": 41866029925,
    "decision_review_journal_domain": 41866030390,
    "durable_jobs_outbox": 41866030194,
    "holdings_projection": 41866029885,
    "import_reconciliation": 41866030160,
    "nav_pnl_performance": 41866029995,
    "paper_shadow_projection": 41866030208,
    "phase_one_final_acceptance": 41866029872,
    "phase_one_readiness": 41866030144,
    "phase_three_roadmap": 41866029912,
    "phase_two_final_acceptance": 41866030034,
    "phase_two_portfolio_domain": 41866029811,
    "portfolio_api_export": 41866029993,
    "portfolio_dashboard_accounts": 41866030255,
    "portfolio_registry": 41866030074,
    "postgresql_schema": 41866030192,
    "private_deployment_operations": 41866030096,
    "runtime_api_auth": 41866030078,
    "runtime_foundation": 41866030104,
    "server_deployment_acceptance": 41866029769,
    "single_owner_identity_runtime": 41866029820,
    "transaction_journal": 41866030056,
    "transactions_holdings_reconciliation_ui": 41866029821,
    "trd_bot_adapter": 41866030551,
    "trd_bot_sync_runtime": 41866030122,
    "valuation_evidence": 41866030093,
}

EXPECTED_FREEZE_MARKERS = {
    "NEX_P3_01_PREREQUISITE=PASS",
    "NEX_P3_02_TRD_BOT_V031_INTEGRATION_CONTRACT=PASS",
    "NEX_P3_02_PROVIDER_IMPLEMENTATION=DEFERRED_TO_TRD_BOT",
    "NEX_P3_03_PROVIDER_SMOKE_GATE=PRESERVED",
    "NEX_V0_1_SERVER_DEPLOYMENT_GATE=PRESERVED_DEFERRED",
}

EXPECTED_OPERATIONS = {
    "GET /capabilities",
    "GET /snapshots/{resource_type}",
    "GET /events",
    "GET /events/{event_id}",
    "POST /commands/decision-reviews",
    "POST /exports",
    "GET /exports/{export_id}",
    "GET /exports/{export_id}/manifest",
}
EXPECTED_GROUPS = {
    "portfolio": {
        "paper_shadow_portfolio",
        "paper_shadow_position",
        "portfolio_intelligence",
        "simulation_outcome",
    },
    "decision": {
        "market_context",
        "decision_evaluation",
        "candidate",
        "risk_gate",
    },
    "alert": {"alert", "alert_outcome"},
}
EXPECTED_COMMANDS = {
    "decision_review.accept.v1",
    "decision_review.reject.v1",
    "decision_review.defer.v1",
}
EXPECTED_ACTIONS = {"accept", "reject", "defer"}
EXPECTED_RELEASE_BLOCKERS = {"v0.1-production-deployment", "v0.1-release"}
FORBIDDEN_CAPABILITIES = {
    "saas",
    "multi_user",
    "public_internet_deployment",
    "exchange_credentials",
    "wallet_private_keys_or_signing",
    "fund_transfer",
    "live_order_capability",
    "autonomous_ai_execution",
    "ml_training_or_inference",
    "financial_advice",
    "tax_advice",
    "direct_trd_bot_database_access",
}


class TrdBotV031IntegrationContractError(ValueError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise TrdBotV031IntegrationContractError(message)


def _json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    _require(isinstance(payload, dict), f"{path.name} must contain an object")
    return payload


def canonical_checksum(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def load_contract(path: Path = CONTRACT_PATH) -> dict[str, Any]:
    return _json(path)


def load_profile(path: Path = PROFILE_PATH) -> dict[str, Any]:
    return _json(path)


def load_freeze_record(path: Path = FREEZE_PATH) -> dict[str, Any]:
    return _json(path)


def validate_freeze_record(
    record: dict[str, Any],
    contract: dict[str, Any],
    profile: dict[str, Any],
) -> None:
    _require(canonical_checksum(record) == P3_02_FREEZE_CHECKSUM, "P3-02 Freeze artifact drift")
    _require(
        record.get("schema_version") == "nexora-trd-bot-v031-integration-contract-freeze-v1",
        "P3-02 Freeze schema drift",
    )
    _require(record.get("decision_id") == "NEX-P3-02", "P3-02 Freeze decision drift")
    _require(record.get("status") == "frozen" and record.get("frozen") is True, "P3-02 is not frozen")
    _require(record.get("candidate_commit_sha") == P3_02_CANDIDATE_COMMIT, "P3-02 candidate drift")
    _require(record.get("candidate_tree_sha") == P3_02_CANDIDATE_TREE, "P3-02 candidate tree drift")

    contract_ref = record.get("contract")
    profile_ref = record.get("provider_profile")
    _require(isinstance(contract_ref, dict), "Freeze contract reference must be an object")
    _require(isinstance(profile_ref, dict), "Freeze profile reference must be an object")
    _require(contract_ref.get("canonical_checksum") == canonical_checksum(contract), "frozen contract drift")
    _require(profile_ref.get("canonical_checksum") == canonical_checksum(profile), "frozen provider profile drift")

    primary = record.get("primary_workflow")
    _require(isinstance(primary, dict), "primary workflow evidence must be an object")
    _require(primary.get("run_id") == P3_02_PRIMARY_RUN_ID, "primary workflow run drift")
    _require(primary.get("run_attempt") == 1, "primary workflow attempt drift")
    _require(primary.get("event") == "push", "primary workflow event drift")
    _require(primary.get("status") == "completed", "primary workflow did not complete")
    _require(primary.get("conclusion") == "success", "primary workflow failed")
    _require(set(primary.get("verified_markers", [])) == EXPECTED_FREEZE_MARKERS, "workflow markers drift")
    jobs = primary.get("jobs")
    _require(isinstance(jobs, dict), "primary workflow jobs must be an object")
    expected_primary_jobs = {
        "trd-bot-v031-contract": 126700325531,
        "backend-regression": 126700325932,
        "web-regression": 126700326237,
    }
    _require(set(jobs) == set(expected_primary_jobs), "primary workflow job inventory drift")
    for name, job_id in expected_primary_jobs.items():
        job = jobs.get(name)
        _require(isinstance(job, dict), f"primary workflow job missing: {name}")
        _require(job.get("job_id") == job_id, f"primary workflow job ID drift: {name}")
        _require(job.get("status") == "completed", f"primary workflow job incomplete: {name}")
        _require(job.get("conclusion") == "success", f"primary workflow job failed: {name}")

    regressions = record.get("regression_workflows")
    _require(isinstance(regressions, dict), "regression workflow evidence must be an object")
    _require(set(regressions) == set(EXPECTED_REGRESSION_RUNS), "regression workflow inventory drift")
    seen_job_ids: set[int] = set()
    for name, run_id in EXPECTED_REGRESSION_RUNS.items():
        workflow = regressions.get(name)
        _require(isinstance(workflow, dict), f"regression workflow missing: {name}")
        _require(workflow.get("run_id") == run_id, f"regression workflow run drift: {name}")
        _require(workflow.get("status") == "completed", f"regression workflow incomplete: {name}")
        _require(workflow.get("conclusion") == "success", f"regression workflow failed: {name}")
        workflow_jobs = workflow.get("jobs")
        _require(isinstance(workflow_jobs, dict) and workflow_jobs, f"regression jobs missing: {name}")
        for job_name, job in workflow_jobs.items():
            _require(isinstance(job, dict), f"invalid regression job: {name}/{job_name}")
            job_id = job.get("job_id")
            _require(isinstance(job_id, int) and job_id > 0, f"invalid regression job ID: {name}/{job_name}")
            _require(job_id not in seen_job_ids, f"duplicate regression job ID: {job_id}")
            seen_job_ids.add(job_id)
            _require(job.get("status") == "completed", f"regression job incomplete: {name}/{job_name}")
            _require(job.get("conclusion") == "success", f"regression job failed: {name}/{job_name}")

    acceptance = record.get("acceptance")
    _require(isinstance(acceptance, dict), "Freeze acceptance must be an object")
    _require(acceptance.get("workflow_count") == 31, "Freeze workflow count drift")
    _require(acceptance.get("failed_workflows") == [], "Freeze contains failed workflows")
    for key in ("contract_only_freeze", "server_deployment_gate_preserved"):
        _require(acceptance.get(key) is True, f"Freeze acceptance invariant disabled: {key}")
    for key in (
        "nexora_database_tables_added",
        "nexora_runtime_behavior_added",
        "provider_runtime_registered",
        "trd_bot_0_3_0_compatible",
        "target_trd_bot_0_3_1_implemented",
        "live_provider_smoke_passed",
        "p3_03_opened",
        "production_deployment_claimed",
        "production_release_claimed",
    ):
        _require(acceptance.get(key) is False, f"premature Freeze claim: {key}")

    transition = record.get("transition")
    _require(isinstance(transition, dict), "Freeze transition must be an object")
    _require(
        transition.get("next_allowed_stage") == "TRD-BOT-v0.3.1-INTEGRATION-IMPLEMENTATION",
        "post-Freeze provider stage drift",
    )
    _require(transition.get("nexora_next_stage") == "NEX-P3-03", "Nexora continuation drift")
    _require(
        transition.get("nexora_next_stage_blocked_until") == "compatible_provider_and_real_smoke",
        "P3-03 opened before compatible provider smoke",
    )


def validate_prerequisites() -> None:
    p3_01 = _json(P3_01_FREEZE_PATH)
    _require(canonical_checksum(p3_01) == P3_01_FREEZE_CHECKSUM, "P3-01 Freeze artifact drift")
    _require(p3_01.get("decision_id") == "NEX-P3-01", "P3-01 decision drift")
    _require(p3_01.get("frozen") is True, "P3-01 is not frozen")
    _require(p3_01.get("candidate_commit_sha") == P3_01_CANDIDATE_COMMIT, "P3-01 candidate drift")
    _require(p3_01.get("next_allowed_stage") == "NEX-P3-02", "P3-01 did not open P3-02")
    _require(p3_01.get("decision_source_evidence_immutable") is True, "P3-01 evidence mutability drift")
    _require(p3_01.get("review_is_execution_authorization") is False, "P3-01 review boundary drift")
    _require(p3_01.get("trd_bot_0_3_0_compatible") is False, "P3-01 made TRD Bot 0.3.0 compatible")

    _require(canonical_checksum(_json(P0_CONTRACT_PATH)) == P0_CONTRACT_CHECKSUM, "P0 contract drift")
    _require(canonical_checksum(_json(P0_OPENAPI_PATH)) == P0_OPENAPI_CHECKSUM, "P0 OpenAPI drift")


def _validate_authentication(profile: dict[str, Any]) -> None:
    auth = profile.get("service_authentication")
    _require(isinstance(auth, dict), "service authentication must be an object")
    _require(auth.get("scheme") == "bearer_service_token", "service auth scheme drift")
    _require(auth.get("authorization_header") == "Authorization", "authorization header drift")
    _require(auth.get("minimum_token_entropy_bytes") == 32, "service token entropy weakened")
    _require(auth.get("constant_time_comparison_required") is True, "constant-time comparison disabled")
    _require(auth.get("token_source") == "absolute_private_file", "service token source drift")
    _require(auth.get("production_transport") == "https", "production transport weakened")
    _require(auth.get("development_http_scope") == "loopback_only", "development HTTP scope widened")
    for key in (
        "query_parameter_allowed",
        "cookie_allowed",
        "browser_delivery_allowed",
        "logging_allowed",
        "export_allowed",
    ):
        _require(auth.get(key) is False, f"service token exposure enabled: {key}")
    _require(auth.get("missing_or_invalid_status") == 401, "authentication failure status drift")
    _require(auth.get("insufficient_scope_status") == 403, "authorization failure status drift")


def _validate_snapshots_and_events(profile: dict[str, Any]) -> None:
    groups = profile.get("snapshot_groups")
    _require(isinstance(groups, dict), "snapshot groups must be an object")
    _require(set(groups) == set(EXPECTED_GROUPS), "snapshot group inventory drift")
    for group, expected in EXPECTED_GROUPS.items():
        _require(set(groups.get(group, [])) == expected, f"{group} snapshot resources drift")
    flattened = [item for values in groups.values() for item in values]
    _require(len(flattened) == len(set(flattened)) == 10, "snapshot resources must be unique")

    snapshots = profile.get("snapshot_protocol")
    _require(isinstance(snapshots, dict), "snapshot protocol must be an object")
    for key in (
        "first_page_without_cursor_starts_stable_scan",
        "continuation_pages_share_one_snapshot_boundary",
        "deterministic_order_required",
        "each_item_requires_source_reference",
    ):
        _require(snapshots.get(key) is True, f"snapshot invariant disabled: {key}")
    _require(snapshots.get("expired_cursor_status") == 410, "snapshot cursor status drift")
    _require(snapshots.get("expired_cursor_action") == "full_snapshot_resync", "snapshot resync drift")
    _require(snapshots.get("silent_cursor_reset_allowed") is False, "silent snapshot cursor reset enabled")

    events = profile.get("event_feed")
    _require(isinstance(events, dict), "event feed must be an object")
    _require(events.get("delivery_semantics") == "at_least_once", "event delivery semantics drift")
    _require(events.get("ordering_scope") == "per_aggregate", "event ordering scope drift")
    _require(events.get("gap_detection") == "aggregate_version", "event gap detection drift")
    _require(set(events.get("deduplication_keys", [])) == {"event_id", "idempotency_key"}, "dedupe drift")
    _require(events.get("unknown_schema_action") == "quarantine_and_degrade", "schema action drift")
    _require(events.get("gap_action") == "pause_projection_and_backfill", "event gap action drift")
    _require(events.get("expired_cursor_action") == "full_snapshot_resync", "event resync drift")
    _require(events.get("exactly_once_claimed") is False, "exactly-once delivery claimed")

    resync = profile.get("full_resync")
    _require(isinstance(resync, dict), "full resync must be an object")
    expected_steps = [
        "pause_projection_publication",
        "scan_all_snapshot_resources",
        "validate_source_references_and_checksums",
        "replay_available_events_with_deduplication",
        "verify_contiguous_aggregate_versions",
        "publish_projection_and_checkpoint_atomically",
    ]
    _require(resync.get("steps") == expected_steps, "full resync sequence drift")
    _require(resync.get("partial_snapshot_publish_allowed") is False, "partial resync publication enabled")
    _require(resync.get("operator_intervention_required_when_gap_remains") is True, "gap escalation removed")


def _validate_commands_exports_and_smoke(profile: dict[str, Any]) -> None:
    review = profile.get("decision_review_command")
    _require(isinstance(review, dict), "decision review command must be an object")
    _require(set(review.get("actions", [])) == EXPECTED_ACTIONS, "review actions drift")
    _require(set(review.get("command_types", {}).values()) == EXPECTED_COMMANDS, "review commands drift")
    _require(review.get("idempotency_required") is True, "review idempotency disabled")
    _require(review.get("same_key_different_payload_status") == 409, "idempotency conflict drift")
    _require(review.get("source_evidence_checksum_required") is True, "review checksum disabled")
    concurrency = review.get("optimistic_concurrency")
    _require(isinstance(concurrency, dict), "review concurrency must be an object")
    _require(concurrency.get("enforced_by") == "nexora_local_owner_review", "review concurrency owner drift")
    _require(concurrency.get("expected_version_required_locally") is True, "local expected version disabled")
    _require(concurrency.get("provider_guard") == "immutable_source_evidence_checksum", "provider guard drift")
    _require(
        concurrency.get("provider_expected_version_field_required") is False,
        "provider command incorrectly owns local review version",
    )
    _require(review.get("local_owner_review_source_of_truth") == "nexora", "review ownership drift")
    _require(review.get("provider_command_purpose") == "paper_shadow_feedback_only", "command scope widened")
    for key in ("execution_authorization", "creates_live_order", "posts_portfolio_transaction"):
        _require(review.get(key) is False, f"review command enabled forbidden effect: {key}")

    export = profile.get("export_protocol")
    _require(isinstance(export, dict), "export protocol must be an object")
    _require(set(export.get("profiles", [])) == {"private", "ai_safe"}, "export profiles drift")
    _require(export.get("accepted_completion_status") == "complete", "export completion drift")
    _require(export.get("partial_export_accepted") is False, "partial export accepted")
    for key in ("checksums_required", "source_lineage_required", "secret_fields_forbidden"):
        _require(export.get(key) is True, f"export invariant disabled: {key}")

    smoke = profile.get("acceptance_smoke")
    _require(isinstance(smoke, dict), "acceptance smoke must be an object")
    _require(smoke.get("required_before") == "NEX-P3-03-FREEZE", "smoke gate stage drift")
    _require(smoke.get("fixture_contract_tests_required") is True, "fixture contract tests disabled")
    _require(smoke.get("real_provider_required") is True, "real provider smoke disabled")
    _require(smoke.get("external_network_required") is False, "external network unexpectedly required")
    scenarios = smoke.get("required_scenarios")
    _require(isinstance(scenarios, list) and len(scenarios) == 12, "acceptance smoke inventory drift")


def validate_profile(profile: dict[str, Any]) -> None:
    _require(profile.get("schema_version") == "nexora-trd-bot-v031-provider-profile-v1", "profile schema drift")
    _require(profile.get("profile_id") == "nexora-trd-bot-v0.3.1", "profile ID drift")
    _require(profile.get("contract_version") == "nexora-trd-integration-v1", "contract version drift")
    provider = profile.get("provider")
    _require(isinstance(provider, dict), "provider must be an object")
    _require(provider.get("minimum_release") == "0.3.1", "minimum provider release drift")
    _require(provider.get("accepted_release_range") == ">=0.3.1,<0.4.0", "release range drift")
    _require(provider.get("release_0_3_0_compatible") is False, "TRD Bot 0.3.0 cannot be compatible")
    _require(set(profile.get("operations", [])) == EXPECTED_OPERATIONS, "operation inventory drift")

    capabilities = profile.get("capability_negotiation")
    _require(isinstance(capabilities, dict), "capability negotiation must be an object")
    _require(capabilities.get("contract_versions") == ["nexora-trd-integration-v1"], "capability contract drift")
    _require(set(capabilities.get("commands", [])) == EXPECTED_COMMANDS, "capability commands drift")
    _require(capabilities.get("missing_or_unknown_capability_action") == "fail_closed", "capability fail-close drift")
    _require(capabilities.get("provider_version_change_action") == "invalidate_and_fail_closed", "version change drift")

    _validate_authentication(profile)
    _validate_snapshots_and_events(profile)
    _validate_commands_exports_and_smoke(profile)


def validate_contract(contract: dict[str, Any], profile: dict[str, Any]) -> None:
    _require(contract.get("schema_version") == "nexora-trd-bot-v031-integration-v1", "contract schema drift")
    _require(contract.get("decision_id") == "NEX-P3-02", "decision ID drift")
    _require(contract.get("decision_date") == "2026-11-04", "decision date drift")
    _require(contract.get("status") == "candidate", "P3-02 must remain a candidate")

    prerequisite = contract.get("p3_01_prerequisite")
    _require(isinstance(prerequisite, dict), "P3-01 prerequisite must be an object")
    _require(prerequisite.get("frozen") is True, "P3-01 prerequisite not frozen")
    _require(prerequisite.get("freeze_commit_sha") == P3_01_FREEZE_COMMIT, "P3-01 Freeze commit drift")
    _require(prerequisite.get("accepted_candidate_commit_sha") == P3_01_CANDIDATE_COMMIT, "P3-01 candidate drift")
    _require(prerequisite.get("freeze_record_canonical_checksum") == P3_01_FREEZE_CHECKSUM, "P3-01 checksum drift")
    _require(prerequisite.get("source_evidence_immutable") is True, "source evidence mutability drift")
    _require(prerequisite.get("human_review_source_of_truth") == "nexora", "review source drift")
    _require(prerequisite.get("review_is_execution_authorization") is False, "review authorization drift")

    baseline = contract.get("frozen_p0_contract_baseline")
    _require(isinstance(baseline, dict), "P0 baseline must be an object")
    _require(baseline.get("contract_canonical_checksum") == P0_CONTRACT_CHECKSUM, "P0 contract checksum drift")
    _require(baseline.get("openapi_canonical_checksum") == P0_OPENAPI_CHECKSUM, "P0 OpenAPI checksum drift")
    _require(baseline.get("modified_by_p3_02") is False, "P3-02 modified frozen P0 artifacts")

    profile_ref = contract.get("provider_profile")
    _require(isinstance(profile_ref, dict), "provider profile reference must be an object")
    _require(profile_ref.get("canonical_checksum") == PROFILE_CHECKSUM, "provider profile checksum drift")
    _require(canonical_checksum(profile) == PROFILE_CHECKSUM, "provider profile artifact drift")

    provider = contract.get("provider_baseline")
    _require(isinstance(provider, dict), "provider baseline must be an object")
    _require(provider.get("inspected_commit_sha") == TRD_BOT_V030_COMMIT, "inspected provider commit drift")
    _require(provider.get("inspected_release") == "0.3.0", "inspected provider release drift")
    _require(provider.get("compatible") is False, "TRD Bot 0.3.0 cannot be compatible")
    _require(provider.get("runtime_negotiation_allowed") is False, "TRD Bot 0.3.0 negotiation enabled")
    _require(provider.get("direct_database_fallback_allowed") is False, "direct database fallback enabled")
    _require(len(provider.get("blocking_gaps", [])) == 8, "provider gap inventory drift")

    target = contract.get("target_provider")
    _require(isinstance(target, dict), "target provider must be an object")
    _require(target.get("release") == "0.3.1", "target provider release drift")
    _require(
        target.get("compatibility_status_before_smoke") == "contract_candidate_only", "premature compatibility claim"
    )
    _require(target.get("capability_match_required") is True, "capability match disabled")
    _require(target.get("provider_release_claim_allowed_in_nexora") is False, "provider release claimed by Nexora")

    boundary = contract.get("contract_boundary")
    _require(isinstance(boundary, dict) and boundary, "contract boundary must be non-empty")
    _require(all(value is True for value in boundary.values()), "P3-02 contract boundary is incomplete")

    compatibility = contract.get("compatibility")
    _require(isinstance(compatibility, dict), "compatibility must be an object")
    _require(compatibility.get("provider_0_3_0_status") == "legacy_read_only_blocked", "0.3.0 status drift")
    _require(compatibility.get("unknown_release_action") == "fail_closed", "unknown release action drift")
    _require(compatibility.get("unknown_schema_action") == "quarantine_and_degrade", "unknown schema action drift")

    resync = contract.get("resync_invariants")
    _require(isinstance(resync, dict), "resync invariants must be an object")
    for key in (
        "snapshot_scans_are_stable",
        "all_three_snapshot_groups_required",
        "event_delivery_is_at_least_once",
        "duplicate_delivery_is_idempotent",
        "aggregate_version_detects_gaps",
        "expired_cursor_requires_full_resync",
        "checkpoint_and_projection_publish_atomically",
        "unresolved_gap_requires_operator_intervention",
    ):
        _require(resync.get(key) is True, f"resync invariant disabled: {key}")
    _require(resync.get("partial_resync_publish_allowed") is False, "partial resync publication enabled")

    review = contract.get("review_boundary")
    _require(isinstance(review, dict), "review boundary must be an object")
    _require(set(review.get("owner_actions", [])) == EXPECTED_ACTIONS, "owner review actions drift")
    for key in (
        "provider_command_replaces_local_review_record",
        "execution_authorization",
        "live_order_capability",
        "portfolio_transaction_posted",
    ):
        _require(review.get(key) is False, f"review boundary widened: {key}")

    implementation = contract.get("implementation_boundary")
    _require(isinstance(implementation, dict), "implementation boundary must be an object")
    for key in (
        "nexora_database_tables_added",
        "nexora_runtime_behavior_added",
        "provider_runtime_registered",
        "p3_02_freeze_requires_live_provider",
    ):
        _require(implementation.get(key) is False, f"P3-02 implementation widened: {key}")
    _require(implementation.get("p3_03_freeze_requires_live_provider_smoke") is True, "P3-03 smoke gate removed")

    server = contract.get("server_deployment_gate")
    _require(isinstance(server, dict), "server gate must be an object")
    _require(server.get("status") == "deferred_until_private_vps_available", "server gate status drift")
    _require(server.get("removed") is False, "server gate removed")
    _require(server.get("bypassed") is False, "server gate bypassed")
    _require(set(server.get("required_before", [])) == EXPECTED_RELEASE_BLOCKERS, "release blockers drift")

    security = contract.get("security_boundary")
    _require(isinstance(security, dict), "security boundary must be an object")
    _require(set(security) == FORBIDDEN_CAPABILITIES, "security inventory drift")
    _require(not any(security.values()), "forbidden capability enabled")

    transition = contract.get("transition")
    _require(isinstance(transition, dict), "transition must be an object")
    _require(transition.get("next_allowed_stage") == "NEX-P3-02-FREEZE", "next stage drift")
    _require(
        transition.get("post_freeze_stage") == "TRD-BOT-v0.3.1-INTEGRATION-IMPLEMENTATION", "post-Freeze stage drift"
    )
    _require(transition.get("nexora_stage_after_compatible_provider") == "NEX-P3-03", "Nexora continuation drift")
    _require(transition.get("freeze_before_provider_implementation") is True, "provider implementation opened early")


def main() -> int:
    validate_prerequisites()
    profile = load_profile()
    contract = load_contract()
    validate_profile(profile)
    validate_contract(contract, profile)
    validate_freeze_record(load_freeze_record(), contract, profile)
    print("NEX_P3_01_PREREQUISITE=PASS")
    print("NEX_P3_02_TRD_BOT_V031_INTEGRATION_CONTRACT=PASS")
    print("NEX_P3_02_FREEZE=PASS")
    print("NEX_P3_02_PROVIDER_IMPLEMENTATION=DEFERRED_TO_TRD_BOT")
    print("NEX_P3_03_PROVIDER_SMOKE_GATE=PRESERVED")
    print("NEX_V0_1_SERVER_DEPLOYMENT_GATE=PRESERVED_DEFERRED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
