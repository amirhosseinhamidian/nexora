#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "contracts/nexora-v0.1-decision-review-journal-domain.json"
P3_00_FREEZE_PATH = ROOT / "artifacts/p3-00/phase-three-roadmap-freeze.json"
FREEZE_PATH = ROOT / "artifacts/p3-01/decision-review-journal-domain-freeze.json"

CONTRACT_CHECKSUM = "8eb6721183a2ba5ea3965abfb0c7ab60fce4c04e26b834f67948a21041afcb03"
P3_00_FREEZE_CANONICAL_CHECKSUM = "5479912ecd162738b2a742e86c1b5f9d64802509cd40e1784c5d3b54c2c1b0de"
P3_00_FREEZE_COMMIT = "adfe6291490a03f7be2f3f9e9261b5d2454dd8b3"
P3_00_CANDIDATE_COMMIT = "d4478b400d5bcadf9984a4eb89dc346d73d94fb4"
CANDIDATE_SHA = "ffa4acd39806e72f7e53d16af7e9937c12e669c5"
CANDIDATE_TREE_SHA = "b21956943411f7b7a4d6d333a4953c093be562ed"
CANDIDATE_PREDECESSOR_SHA = P3_00_FREEZE_COMMIT
CANDIDATE_MESSAGE = "docs(nexora): freeze decision review journal domain"
PRIMARY_RUN_ID = 41859051343

EXPECTED_REGRESSION_RUNS = {
    "application_composition": 41859050955,
    "artifact_export_storage": 41859051124,
    "audit_observability": 41859050440,
    "authenticated_web_shell": 41859050519,
    "contracts": 41859051131,
    "durable_jobs_outbox": 41859050830,
    "holdings_projection": 41859051305,
    "import_reconciliation": 41859050831,
    "nav_pnl_performance": 41859050754,
    "paper_shadow_projection": 41859050599,
    "phase_one_final_acceptance": 41859050814,
    "phase_one_readiness": 41859050746,
    "phase_three_roadmap": 41859050811,
    "phase_two_final_acceptance": 41859050833,
    "phase_two_portfolio_domain": 41859051414,
    "portfolio_api_export": 41859050999,
    "portfolio_dashboard_accounts": 41859050852,
    "portfolio_registry": 41859051047,
    "postgresql_schema": 41859051031,
    "private_deployment_operations": 41859051236,
    "runtime_api_auth": 41859050914,
    "runtime_foundation": 41859050467,
    "server_deployment_acceptance": 41859050853,
    "single_owner_identity_runtime": 41859050821,
    "transaction_journal": 41859050892,
    "transactions_holdings_reconciliation_ui": 41859050973,
    "trd_bot_adapter": 41859050703,
    "trd_bot_sync_runtime": 41859051032,
    "valuation_evidence": 41859050433,
}

EXPECTED_REVIEW_ACTIONS = {"accept", "reject", "defer"}
EXPECTED_DECISION_KINDS = {
    "candidate",
    "risk_assessment",
    "portfolio_assessment",
    "monitoring_alert",
}
EXPECTED_LOCAL_STATES = {
    "review_pending",
    "accepted",
    "rejected",
    "deferred",
    "expired",
    "superseded",
}
EXPECTED_EXPORT_PROFILES = {"private_complete", "ai_safe"}
EXPECTED_EXPORT_DOMAINS = {
    "decision_records",
    "source_references",
    "human_reviews",
    "portfolio_impacts",
    "alert_state_history",
    "watchlists",
    "outcome_journal",
    "lineage",
    "uncertainty",
}
EXPECTED_AI_SAFE_EXCLUSIONS = {
    "credentials",
    "tokens",
    "session_identifiers",
    "recovery_material",
    "private_keys",
    "raw_security_context",
}
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


class DecisionReviewJournalDomainError(ValueError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise DecisionReviewJournalDomainError(message)


def _json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    _require(isinstance(payload, dict), f"{path.name} must contain an object")
    return payload


def canonical_checksum(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def load_contract(path: Path = CONTRACT_PATH) -> dict[str, Any]:
    return _json(path)


def load_freeze_record(path: Path = FREEZE_PATH) -> dict[str, Any]:
    return _json(path)


def validate_p3_00_prerequisite(path: Path = P3_00_FREEZE_PATH) -> None:
    record = _json(path)
    _require(
        canonical_checksum(record) == P3_00_FREEZE_CANONICAL_CHECKSUM,
        "P3-00 Freeze artifact drift",
    )
    _require(record.get("schema_version") == "nexora-phase-three-roadmap-freeze-v1", "P3-00 schema drift")
    _require(record.get("decision_id") == "NEX-P3-00", "P3-00 decision drift")
    _require(record.get("frozen") is True, "P3-00 is not frozen")
    _require(record.get("candidate_commit_sha") == P3_00_CANDIDATE_COMMIT, "P3-00 candidate drift")
    _require(record.get("next_allowed_stage") == "NEX-P3-01", "P3-00 did not open P3-01")
    _require(record.get("production_readiness_claimed") is False, "P3-00 production claim")
    _require(record.get("phase_three_product_complete") is False, "P3-00 product completion claim")
    server = record.get("server_deployment_acceptance")
    _require(isinstance(server, dict), "P3-00 server gate evidence must be an object")
    _require(server.get("removed") is False, "P3-00 removed the server gate")
    _require(server.get("bypassed") is False, "P3-00 bypassed the server gate")
    _require(server.get("required_evidence_unchanged") is True, "P3-00 weakened server evidence")
    _require(set(server.get("blocks", [])) == EXPECTED_RELEASE_BLOCKERS, "P3-00 blocker drift")


def _validate_source_and_decision(contract: dict[str, Any]) -> None:
    boundary = contract.get("domain_boundary")
    _require(isinstance(boundary, dict), "domain boundary must be an object")
    _require(boundary.get("owner_model") == "single_owner", "owner model drift")
    _require(boundary.get("direct_trd_bot_database_access") is False, "direct TRD Bot database access enabled")
    _require(boundary.get("provider_evidence_mutation") is False, "provider evidence mutation enabled")
    _require(boundary.get("review_is_execution_authorization") is False, "review became execution authorization")
    _require(boundary.get("review_posts_portfolio_transaction") is False, "review posts a transaction")
    _require(boundary.get("portfolio_impact_is_advisory") is True, "Portfolio impact must remain advisory")

    evidence = contract.get("source_evidence")
    _require(isinstance(evidence, dict), "source evidence must be an object")
    _require(evidence.get("immutable") is True, "source evidence must be immutable")
    _require(evidence.get("owner_scoped_projection") is True, "source projection must be owner-scoped")
    _require(evidence.get("canonical_time") == "utc", "canonical time drift")
    _require(evidence.get("unknown_schema_action") == "quarantine", "unknown schema action drift")
    _require(evidence.get("checksum_mismatch_action") == "reject_and_quarantine", "checksum action drift")
    for key in ("provider_degraded_state_visible", "missing_evidence_state_visible", "stale_evidence_state_visible"):
        _require(evidence.get(key) is True, f"evidence state hidden: {key}")

    decision = contract.get("decision_projection")
    _require(isinstance(decision, dict), "decision projection must be an object")
    _require(set(decision.get("decision_kinds", [])) == EXPECTED_DECISION_KINDS, "decision kinds drift")
    _require(set(decision.get("local_states", [])) == EXPECTED_LOCAL_STATES, "decision states drift")
    _require(decision.get("source_mutation") == "forbidden", "source mutation enabled")
    for key in (
        "local_state_is_derived",
        "latest_state_from_append_only_reviews",
        "optimistic_projection_version_required",
        "duplicate_source_delivery_idempotent",
        "expired_cursor_requires_full_resync",
    ):
        _require(decision.get(key) is True, f"decision invariant disabled: {key}")


def _validate_review_and_impact(contract: dict[str, Any]) -> None:
    review = contract.get("human_review")
    _require(isinstance(review, dict), "human review must be an object")
    _require(set(review.get("actions", [])) == EXPECTED_REVIEW_ACTIONS, "review actions drift")
    for key in (
        "owner_actor_required",
        "decision_reference_required",
        "source_evidence_checksum_required",
        "reason_code_required",
        "reviewed_at_required",
        "recorded_at_required",
        "idempotency_key_required",
        "expected_version_required",
        "optimistic_concurrency_required",
        "latest_review_is_derived",
        "provider_reason_codes_remain_namespaced",
        "owner_reason_codes_remain_namespaced",
        "other_reason_requires_note",
    ):
        _require(review.get(key) is True, f"review invariant disabled: {key}")
    _require(review.get("mutation_after_recording") == "forbidden", "review mutation enabled")
    _require(review.get("correction") == "superseding_review", "review correction lineage drift")
    _require(review.get("accept_creates_order_intent") is False, "Accept creates an OrderIntent")
    _require(review.get("accept_posts_transaction") is False, "Accept posts a transaction")
    reason_codes = review.get("owner_reason_code_namespaces")
    _require(isinstance(reason_codes, dict), "owner reason namespaces must be an object")
    _require(set(reason_codes) == EXPECTED_REVIEW_ACTIONS, "owner reason namespace drift")
    for action, codes in reason_codes.items():
        _require(isinstance(codes, list) and codes, f"{action} reason codes must be non-empty")
        _require(all(code.startswith(f"owner.{action}.") for code in codes), f"{action} reason namespace drift")
        _require(codes[-1] == f"owner.{action}.other_with_note", f"{action} other reason drift")

    impact = contract.get("portfolio_impact")
    _require(isinstance(impact, dict), "Portfolio impact must be an object")
    for key in (
        "advisory_only",
        "portfolio_snapshot_reference_required",
        "candidate_reference_required",
        "calculation_version_required",
        "input_checksums_required",
        "uncertainty_required",
    ):
        _require(impact.get(key) is True, f"Portfolio impact invariant disabled: {key}")
    _require(impact.get("what_if_persists_accounting_transaction") is False, "What-if posts a transaction")
    _require(impact.get("what_if_submits_order") is False, "What-if submits an order")


def _validate_alert_watchlist_journal(contract: dict[str, Any]) -> None:
    alert = contract.get("alert_domain")
    _require(isinstance(alert, dict), "alert domain must be an object")
    for key in ("source_alert_immutable", "acknowledgement_is_idempotent", "state_history_append_only"):
        _require(alert.get(key) is True, f"alert invariant disabled: {key}")
    _require(alert.get("source_alert_deletion_forbidden") is True, "source alert deletion enabled")
    _require(alert.get("notification_delivery_deferred") is True, "notification delivery opened early")

    watchlist = contract.get("watchlist_domain")
    _require(isinstance(watchlist, dict), "watchlist domain must be an object")
    for key in (
        "owner_scoped",
        "monitoring_preferences_bounded",
        "optimistic_concurrency_required",
        "duplicate_item_idempotent",
    ):
        _require(watchlist.get(key) is True, f"watchlist invariant disabled: {key}")
    _require(watchlist.get("creates_trade_instruction") is False, "watchlist creates a trade instruction")

    journal = contract.get("outcome_journal")
    _require(isinstance(journal, dict), "outcome journal must be an object")
    for key in (
        "append_only",
        "owner_scoped",
        "decision_reference_required",
        "occurred_at_required",
        "recorded_at_required",
        "source_lineage_required_for_observed_outcome",
        "uncertainty_visible",
    ):
        _require(journal.get(key) is True, f"journal invariant disabled: {key}")
    _require(journal.get("mutation_after_recording") == "forbidden", "journal mutation enabled")
    _require(journal.get("correction") == "superseding_entry", "journal correction lineage drift")
    _require(journal.get("ai_generated_entry_allowed") is False, "AI-generated journal entries opened early")
    _require(journal.get("human_note_rewritten_by_provider_sync") is False, "provider sync rewrites human notes")


def _validate_export_deferred_and_security(contract: dict[str, Any]) -> None:
    export = contract.get("export_policy")
    _require(isinstance(export, dict), "export policy must be an object")
    _require(export.get("export_first") is True, "export-first policy disabled")
    _require(set(export.get("profiles", [])) == EXPECTED_EXPORT_PROFILES, "export profiles drift")
    _require(set(export.get("required_domains", [])) == EXPECTED_EXPORT_DOMAINS, "export domains drift")
    _require(set(export.get("ai_safe_excludes", [])) == EXPECTED_AI_SAFE_EXCLUSIONS, "AI-safe exclusions drift")
    _require(export.get("public_download") is False, "public export download enabled")

    persistence = contract.get("persistence_boundary")
    _require(isinstance(persistence, dict), "persistence boundary must be an object")
    _require(persistence.get("schema_and_migrations_deferred_to") == "NEX-P3-03", "persistence stage drift")
    for key in (
        "api_and_ui_implementation_allowed_in_p3_01",
        "provider_runtime_registration_allowed_in_p3_01",
        "database_tables_added_in_p3_01",
        "runtime_behavior_added_in_p3_01",
    ):
        _require(persistence.get(key) is False, f"P3-01 implementation boundary widened: {key}")

    dependency = contract.get("trd_bot_dependency")
    _require(isinstance(dependency, dict), "TRD Bot dependency must be an object")
    _require(dependency.get("current_release") == "0.3.0", "current TRD Bot release drift")
    _require(dependency.get("current_release_compatible") is False, "TRD Bot 0.3.0 cannot be compatible")
    _require(dependency.get("target_release") == "0.3.1", "target TRD Bot release drift")
    _require(dependency.get("integration_contract_deferred_to") == "NEX-P3-02", "integration stage drift")
    _require(dependency.get("direct_database_access") is False, "direct TRD Bot database access enabled")

    server = contract.get("server_deployment_gate")
    _require(isinstance(server, dict), "server gate must be an object")
    _require(server.get("gate_id") == "NEX-V0.1-SERVER-DEPLOYMENT-ACCEPTANCE", "server gate ID drift")
    _require(server.get("status") == "deferred_until_private_vps_available", "server gate status drift")
    _require(server.get("removed") is False, "server gate removed")
    _require(server.get("bypassed") is False, "server gate bypassed")
    _require(set(server.get("required_before", [])) == EXPECTED_RELEASE_BLOCKERS, "release blockers drift")

    security = contract.get("security_boundary")
    _require(isinstance(security, dict), "security boundary must be an object")
    _require(set(security) == FORBIDDEN_CAPABILITIES, "security capability inventory drift")
    _require(not any(security.values()), "P3-01 enabled a forbidden capability")


def validate_contract(contract: dict[str, Any]) -> None:
    _require(
        contract.get("schema_version") == "nexora-decision-review-journal-domain-v1",
        "invalid schema version",
    )
    _require(contract.get("decision_id") == "NEX-P3-01", "invalid decision ID")
    _require(contract.get("decision_date") == "2026-11-04", "invalid decision date")
    _require(contract.get("status") == "candidate", "P3-01 must remain a candidate")

    prerequisite = contract.get("p3_00_prerequisite")
    _require(isinstance(prerequisite, dict), "P3-00 prerequisite must be an object")
    _require(prerequisite.get("frozen") is True, "P3-00 prerequisite must be frozen")
    _require(prerequisite.get("freeze_commit_sha") == P3_00_FREEZE_COMMIT, "P3-00 Freeze commit drift")
    _require(
        prerequisite.get("accepted_candidate_commit_sha") == P3_00_CANDIDATE_COMMIT,
        "P3-00 candidate drift",
    )
    _require(
        prerequisite.get("freeze_record_canonical_checksum") == P3_00_FREEZE_CANONICAL_CHECKSUM,
        "P3-00 artifact checksum drift",
    )
    _require(prerequisite.get("phase_three_roadmap_frozen") is True, "Phase 3 roadmap not frozen")
    _require(prerequisite.get("server_deployment_gate_preserved") is True, "server gate not preserved")
    _require(prerequisite.get("production_readiness_claimed") is False, "P3-00 production claim")

    _validate_source_and_decision(contract)
    _validate_review_and_impact(contract)
    _validate_alert_watchlist_journal(contract)
    _validate_export_deferred_and_security(contract)

    transition = contract.get("transition")
    _require(isinstance(transition, dict), "transition must be an object")
    _require(transition.get("next_allowed_stage") == "NEX-P3-01-FREEZE", "next stage drift")
    _require(transition.get("post_freeze_stage") == "NEX-P3-02", "post-Freeze stage drift")
    _require(transition.get("freeze_before_implementation") is True, "implementation opened before Freeze")
    _require(transition.get("requires_successful_ci_on_candidate_sha") is True, "candidate CI gate removed")


def _validate_workflow(workflow: object, *, label: str, run_id: int) -> None:
    _require(isinstance(workflow, dict), f"{label} workflow evidence must be an object")
    _require(workflow.get("run_id") == run_id, f"{label} run ID drift")
    _require(
        workflow.get("run_url") == f"https://github.com/amirhosseinhamidian/nexora/actions/runs/{run_id}",
        f"{label} run URL drift",
    )
    _require(workflow.get("head_sha") == CANDIDATE_SHA, f"{label} workflow head SHA drift")
    _require(
        workflow.get("head_branch") == "feature/v0.1-decision-intelligence",
        f"{label} workflow branch drift",
    )
    _require(workflow.get("event") == "push", f"{label} workflow must be a push run")
    _require(workflow.get("attempt") == 1, f"{label} workflow attempt drift")
    _require(workflow.get("conclusion") == "success", f"{label} workflow did not succeed")
    jobs = workflow.get("jobs")
    _require(isinstance(jobs, dict) and jobs, f"{label} job inventory must be non-empty")
    for job_name, job in jobs.items():
        _require(isinstance(job, dict), f"{label}/{job_name} must be an object")
        _require(isinstance(job.get("job_id"), int), f"{label}/{job_name} job ID missing")
        _require(job.get("conclusion") == "success", f"{label}/{job_name} did not succeed")


def validate_freeze_record(record: dict[str, Any], contract: dict[str, Any]) -> None:
    _require(
        record.get("schema_version") == "nexora-decision-review-journal-domain-freeze-v1",
        "invalid freeze schema",
    )
    _require(record.get("decision_id") == "NEX-P3-01", "invalid freeze decision ID")
    _require(record.get("repository") == "amirhosseinhamidian/nexora", "repository drift")
    _require(record.get("candidate_commit_sha") == CANDIDATE_SHA, "candidate SHA drift")
    _require(record.get("candidate_tree_sha") == CANDIDATE_TREE_SHA, "candidate tree drift")
    _require(record.get("candidate_commit_message") == CANDIDATE_MESSAGE, "candidate message drift")
    _require(
        record.get("candidate_predecessor_sha") == CANDIDATE_PREDECESSOR_SHA,
        "candidate predecessor drift",
    )

    primary = record.get("github_actions")
    _validate_workflow(primary, label="decision review journal domain", run_id=PRIMARY_RUN_ID)
    _require(
        primary.get("workflow_path") == ".github/workflows/decision-review-journal-domain.yml",
        "workflow path drift",
    )
    jobs = primary["jobs"]
    _require(
        set(jobs) == {"decision_review_journal_contract", "backend_regression", "web_regression"},
        "primary job inventory mismatch",
    )
    _require(
        jobs["decision_review_journal_contract"].get("job_id") == 126675486244,
        "contract job ID drift",
    )
    _require(jobs["backend_regression"].get("job_id") == 126675485254, "backend job ID drift")
    _require(jobs["web_regression"].get("job_id") == 126675485699, "web job ID drift")
    for marker in (
        "p3_00_prerequisite_passed",
        "decision_review_journal_verifier_passed",
        "decision_review_journal_tests_passed",
        "repository_contract_tests_passed",
    ):
        _require(
            jobs["decision_review_journal_contract"].get(marker) is True,
            f"contract job missing {marker}",
        )
    for job_name in ("backend_regression", "web_regression"):
        for marker in (
            "locked_dependencies_installed",
            "format_passed",
            "lint_passed",
            "typecheck_passed",
            "tests_passed",
        ):
            _require(jobs[job_name].get(marker) is True, f"{job_name} missing {marker}")
    _require(jobs["web_regression"].get("build_passed") is True, "Web build evidence missing")

    regressions = record.get("regression_workflows")
    _require(isinstance(regressions, dict), "regression workflow evidence must be an object")
    _require(set(regressions) == set(EXPECTED_REGRESSION_RUNS), "regression workflow inventory mismatch")
    for label, run_id in EXPECTED_REGRESSION_RUNS.items():
        _validate_workflow(regressions[label], label=label, run_id=run_id)

    evidence = record.get("decision_review_journal_contract")
    _require(isinstance(evidence, dict), "domain contract evidence must be an object")
    _require(evidence.get("schema_version") == contract.get("schema_version"), "contract schema mismatch")
    _require(
        evidence.get("path") == "contracts/nexora-v0.1-decision-review-journal-domain.json",
        "contract path drift",
    )
    _require(evidence.get("checksum") == CONTRACT_CHECKSUM, "recorded contract checksum drift")
    _require(evidence.get("checksum") == canonical_checksum(contract), "contract checksum mismatch")

    prerequisite = record.get("p3_00_prerequisite")
    _require(isinstance(prerequisite, dict), "P3-00 prerequisite evidence must be an object")
    _require(prerequisite.get("decision_id") == "NEX-P3-00", "P3-00 prerequisite drift")
    _require(prerequisite.get("frozen") is True, "P3-00 prerequisite is not frozen")
    _require(prerequisite.get("freeze_commit_sha") == P3_00_FREEZE_COMMIT, "P3-00 Freeze commit drift")
    _require(
        prerequisite.get("accepted_candidate_commit_sha") == P3_00_CANDIDATE_COMMIT,
        "P3-00 candidate drift",
    )
    _require(
        prerequisite.get("freeze_record_canonical_checksum") == P3_00_FREEZE_CANONICAL_CHECKSUM,
        "P3-00 artifact checksum drift",
    )

    _require(record.get("recorded_on") == "2026-11-04", "invalid freeze record date")
    _require(record.get("frozen") is True, "P3-01 is not frozen")
    _require(record.get("domain_contract_only") is True, "P3-01 must remain contract-only")
    for key in (
        "database_tables_added",
        "runtime_behavior_added",
        "api_or_ui_added",
        "provider_runtime_registered",
    ):
        _require(record.get(key) is False, f"P3-01 cannot add {key}")
    _require(record.get("decision_source_evidence_immutable") is True, "source evidence immutability drift")
    _require(set(record.get("human_review_actions", [])) == EXPECTED_REVIEW_ACTIONS, "review actions drift")
    _require(record.get("review_is_execution_authorization") is False, "review became execution authorization")
    _require(record.get("accept_creates_order_intent") is False, "Accept creates an OrderIntent")
    _require(record.get("accept_posts_portfolio_transaction") is False, "Accept posts a Portfolio transaction")
    _require(record.get("portfolio_impact_advisory_only") is True, "Portfolio impact is not advisory")
    _require(record.get("what_if_submits_order") is False, "What-if submits an order")
    _require(record.get("outcome_journal_append_only") is True, "Outcome Journal is not append-only")
    _require(record.get("correction_preserves_history") is True, "correction history was weakened")
    _require(record.get("provider_sync_rewrites_human_notes") is False, "provider sync rewrites human notes")
    _require(record.get("phase_three_product_complete") is False, "P3-01 cannot claim product completion")
    _require(record.get("production_readiness_claimed") is False, "production readiness remains deferred")

    server = record.get("server_deployment_acceptance")
    _require(isinstance(server, dict), "server gate evidence must be an object")
    _require(server.get("gate_id") == "NEX-V0.1-SERVER-DEPLOYMENT-ACCEPTANCE", "server gate ID drift")
    _require(server.get("debt_id") == "NEX-DEBT-P1-13-001", "server debt drift")
    _require(server.get("status") == "deferred_until_private_vps_available", "server gate status drift")
    _require(server.get("removed") is False, "server gate was removed")
    _require(server.get("bypassed") is False, "server gate was bypassed")
    _require(server.get("required_evidence_unchanged") is True, "server evidence was weakened")
    _require(set(server.get("blocks", [])) == EXPECTED_RELEASE_BLOCKERS, "server blockers drift")

    for key in FORBIDDEN_CAPABILITIES:
        _require(record.get(key) is False, f"freeze record cannot enable {key}")
    _require(record.get("trd_bot_0_3_0_compatible") is False, "TRD Bot 0.3.0 remains incompatible")
    _require(record.get("target_trd_bot_release") == "0.3.1", "TRD Bot target release drift")
    _require(record.get("next_allowed_stage") == "NEX-P3-02", "post-Freeze stage drift")


def validate_files_and_markers() -> None:
    expected = {
        "README.md": "`NEX-P3-01` is frozen.",
        "docs/v0.1/33-decision-review-journal-domain.md": "# NEX-P3-01",
        ".github/workflows/decision-review-journal-domain.yml": "name: Decision review journal domain",
        "tests/test_decision_review_journal_domain.py": "class DecisionReviewJournalDomainTests",
    }
    for relative, marker in expected.items():
        content = (ROOT / relative).read_text(encoding="utf-8")
        _require(marker in content, f"{relative} is missing the P3-01 marker")


def main() -> int:
    validate_p3_00_prerequisite()
    contract = load_contract()
    validate_contract(contract)
    _require(canonical_checksum(contract) == CONTRACT_CHECKSUM, "P3-01 contract checksum drift")
    validate_freeze_record(load_freeze_record(), contract)
    validate_files_and_markers()
    print(f"schema_version={contract['schema_version']}")
    print(f"decision_id={contract['decision_id']}")
    print(f"contract_checksum={CONTRACT_CHECKSUM}")
    print("NEX_P3_00_PREREQUISITE=PASS")
    print("NEX_P3_01_DECISION_REVIEW_JOURNAL_DOMAIN=PASS")
    print(f"candidate_commit_sha={CANDIDATE_SHA}")
    print("NEX_P3_01_FREEZE=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
