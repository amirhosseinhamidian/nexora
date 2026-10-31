#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "contracts/nexora-v0.1-phase-two-portfolio-domain.json"
P1_13_ACCEPTANCE_PATH = ROOT / "artifacts/p1-13/phase-one-final-acceptance.json"
FREEZE_PATH = ROOT / "artifacts/p2-01/portfolio-domain-roadmap-freeze.json"
CONTRACT_CHECKSUM = "932187af8a74d5d30ed21fa83eb06a1038ab00c49086dcb2a71900a0d175eba5"
P1_13_ACCEPTANCE_CHECKSUM = "86e69a8a50ab75c2be9c5501ad90c8504a5c0d230cb18e90d787bb76dad86dfb"
P1_13_RECORD_CHECKSUM = "a874e2a18deedab36491cd927c818f1fa26d52df22a376f9f846cd719979ca4f"
P1_13_FREEZE_COMMIT = "5708a15d1c983c45885eeabdc4b3f77375cfc1d7"
P1_13_CANDIDATE_COMMIT = "61c5eba2ecf2a3696b6b60c87ecb1afb6064d26d"
CANDIDATE_SHA = "5fad7e9f49a48fb3068634ee8ae6621af8cc6ec1"
CANDIDATE_TREE_SHA = "144759e4da09a84b18b39cc0d06fcd73a7666dfc"
CANDIDATE_MESSAGE = "feat(nexora): define P2-01 portfolio domain roadmap"
CANDIDATE_PREDECESSOR = P1_13_FREEZE_COMMIT

EXPECTED_STAGES = [f"NEX-P2-{number:02d}" for number in range(1, 13)]
EXPECTED_ENTITIES = {
    "portfolio",
    "account",
    "asset",
    "asset_identifier",
    "transaction",
    "transaction_leg",
    "lot",
    "holding_projection",
    "price_observation",
    "fx_rate_observation",
    "manual_valuation",
    "import_batch",
    "import_row",
    "reconciliation_case",
    "valuation_snapshot",
    "performance_snapshot",
}
EXPECTED_EXPORT_FORMATS = {"json", "csv", "parquet", "zip_bundle"}
EXPECTED_EXPORT_PROFILES = {"private_complete", "ai_safe"}
FORBIDDEN_CAPABILITIES = {
    "saas",
    "multi_user",
    "public_internet_deployment",
    "exchange_credentials",
    "wallet_private_keys",
    "wallet_signing",
    "fund_transfer",
    "live_order_submission",
    "live_order_cancellation",
    "autonomous_ai_execution",
    "ml_training",
    "ml_inference",
    "financial_advice",
    "direct_trd_bot_database_access",
}

EXPECTED_REGRESSION_WORKFLOWS: dict[str, tuple[int, dict[str, tuple[int, str]]]] = {
    "trd_bot_adapter": (
        40850501997,
        {
            "backend": (123368485312, "backend"),
            "adapter_contract": (123368485871, "adapter-contract"),
        },
    ),
    "private_deployment_operations": (
        40850502821,
        {
            "private_topology": (123368487762, "private-topology"),
            "backend": (123368488216, "backend"),
            "operations_contract": (123368488280, "operations-contract"),
        },
    ),
    "durable_jobs_outbox": (
        40850501926,
        {
            "postgresql_17": (123368484889, "postgresql-17"),
            "backend": (123368485018, "backend"),
            "durable_contract": (123368485217, "durable-contract"),
        },
    ),
    "contracts": (
        40850502154,
        {
            "technical_baseline": (123368485764, "technical-baseline"),
            "phase_zero_acceptance": (123368486086, "phase-zero-acceptance"),
            "security_boundary": (123368486222, "security-boundary"),
            "scope_contract": (123368486282, "scope-contract"),
            "integration_contract": (123368486414, "integration-contract"),
        },
    ),
    "application_composition": (
        40850502216,
        {
            "backend": (123368485486, "backend"),
            "composition_contract": (123368485658, "composition-contract"),
        },
    ),
    "artifact_export_storage": (
        40850501978,
        {
            "storage_contract": (123368485201, "storage-contract"),
            "backend": (123368485577, "backend"),
            "storage_runtime": (123368485664, "storage-runtime"),
        },
    ),
    "trd_bot_sync_runtime": (
        40850501922,
        {
            "postgresql_17": (123368485198, "postgresql-17"),
            "backend": (123368485518, "backend"),
            "sync_contract": (123368485673, "sync-contract"),
        },
    ),
    "phase_one_final_acceptance": (
        40850502002,
        {
            "acceptance_contract": (123368485093, "acceptance-contract"),
            "browser": (123368485458, "browser"),
            "web": (123368485482, "web"),
            "backend": (123368485528, "backend"),
            "private_topology": (123368485533, "private-topology"),
            "postgresql_17": (123368485687, "postgresql-17"),
        },
    ),
    "phase_one_roadmap_reconciliation": (
        40850502107,
        {
            "backend": (123368485621, "backend"),
            "readiness_contract": (123368486017, "readiness-contract"),
            "web": (123368486216, "web"),
        },
    ),
    "postgresql_schema": (
        40850502009,
        {
            "backend": (123368485335, "backend"),
            "postgresql_17": (123368485356, "postgresql-17"),
            "database_contract": (123368485460, "database-contract"),
        },
    ),
    "runtime_foundation": (
        40850502041,
        {
            "web": (123368485336, "web"),
            "foundation_contract": (123368485712, "foundation-contract"),
            "backend": (123368485762, "backend"),
        },
    ),
    "authenticated_web_shell": (
        40850501950,
        {
            "backend": (123368485105, "backend"),
            "web": (123368485470, "web"),
            "browser": (123368485603, "browser"),
            "web_shell_contract": (123368485608, "web-shell-contract"),
        },
    ),
    "runtime_api_auth": (
        40850502447,
        {
            "backend": (123368486465, "backend"),
            "runtime_contract": (123368486790, "runtime-contract"),
            "cross_language_contract": (123368486965, "cross-language-contract"),
            "postgresql_17": (123368487010, "postgresql-17"),
        },
    ),
    "single_owner_identity_runtime": (
        40850501616,
        {
            "postgresql_17": (123368484600, "postgresql-17"),
            "private_topology": (123368484797, "private-topology"),
            "identity_contract": (123368484828, "identity-contract"),
            "backend": (123368484944, "backend"),
        },
    ),
    "audit_observability": (
        40850501734,
        {
            "backend": (123368484646, "backend"),
            "observability_contract": (123368484781, "observability-contract"),
            "postgresql_17": (123368484801, "postgresql-17"),
        },
    ),
}


class PhaseTwoPortfolioDomainError(ValueError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise PhaseTwoPortfolioDomainError(message)


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


def _validate_workflow(
    workflow: object,
    *,
    label: str,
    run_id: int,
    expected_jobs: dict[str, tuple[int, str]],
) -> None:
    _require(isinstance(workflow, dict), f"{label} workflow evidence must be an object")
    _require(workflow.get("run_id") == run_id, f"{label} run ID drift")
    expected_url = f"https://github.com/amirhosseinhamidian/nexora/actions/runs/{run_id}"
    _require(workflow.get("run_url") == expected_url, f"{label} run URL drift")
    _require(workflow.get("head_sha") == CANDIDATE_SHA, f"{label} workflow head SHA drift")
    _require(workflow.get("event") == "push", f"{label} workflow must be a push run")
    _require(workflow.get("attempt") == 1, f"{label} workflow attempt drift")
    _require(workflow.get("conclusion") == "success", f"{label} workflow did not succeed")
    jobs = workflow.get("jobs")
    _require(isinstance(jobs, dict), f"{label} jobs must be an object")
    _require(set(jobs) == set(expected_jobs), f"{label} job inventory mismatch")
    for job_name, (job_id, displayed_name) in expected_jobs.items():
        job = jobs[job_name]
        _require(isinstance(job, dict), f"{label}/{job_name} must be an object")
        _require(job.get("job_id") == job_id, f"{label}/{job_name} job ID drift")
        _require(job.get("name") == displayed_name, f"{label}/{job_name} name drift")
        _require(job.get("conclusion") == "success", f"{label}/{job_name} did not succeed")


def validate_phase_one_prerequisite() -> None:
    acceptance = _json(P1_13_ACCEPTANCE_PATH)
    _require(canonical_checksum(acceptance) == P1_13_ACCEPTANCE_CHECKSUM, "P1-13 acceptance artifact drift")
    _require(acceptance.get("record_checksum") == P1_13_RECORD_CHECKSUM, "P1-13 record checksum drift")
    _require(acceptance.get("candidate_commit_sha") == P1_13_CANDIDATE_COMMIT, "P1-13 candidate drift")
    _require(acceptance.get("ready_to_freeze_phase_one") is True, "Phase 1 was not accepted")
    _require(acceptance.get("failed_gates") == [], "P1-13 contains failed gates")
    _require(acceptance.get("production_readiness_claimed") is False, "P1-13 cannot claim production readiness")
    server_gate = acceptance.get("server_deployment_acceptance")
    _require(isinstance(server_gate, dict), "P1-13 server deployment gate is missing")
    _require(server_gate.get("status") == "deferred_to_server_deployment", "server gate status drift")
    _require(server_gate.get("planned_country_code") == "DE", "planned VPS country drift")


def _validate_domain_model(contract: dict[str, Any]) -> None:
    domain = contract.get("domain_model")
    _require(isinstance(domain, dict), "domain_model must be an object")
    _require(set(domain.get("entities", [])) == EXPECTED_ENTITIES, "portfolio entity inventory drift")
    _require(set(domain.get("portfolio_kinds", [])) == {"personal", "paper", "shadow"}, "portfolio kinds drift")
    _require("wallet_watch_only" in domain.get("account_kinds", []), "wallet accounts must remain watch-only")

    journal = domain.get("transaction_semantics")
    _require(isinstance(journal, dict), "transaction_semantics must be an object")
    _require(journal.get("journal") == "immutable_double_entry_like_legs", "journal semantics drift")
    _require(journal.get("minimum_legs") == 2, "transactions require at least two legs")
    _require(journal.get("mutation") == "forbidden_after_posting", "posted transactions must be immutable")
    _require(journal.get("correction") == "reversal_or_supersession", "correction lineage drift")
    for key in ("idempotency_required", "source_lineage_required", "owner_scope_required"):
        _require(journal.get(key) is True, f"transaction journal requires {key}")

    projections = domain.get("projection_semantics")
    _require(isinstance(projections, dict), "projection_semantics must be an object")
    for key in ("holdings_are_derived", "lots_are_derived", "nav_is_derived", "pnl_is_derived"):
        _require(projections.get(key) is True, f"projection contract requires {key}")
    _require(projections.get("rebuildable_from_journal") is True, "projections must remain rebuildable")


def _validate_accounting_and_valuation(contract: dict[str, Any]) -> None:
    product = contract.get("product_boundary")
    _require(isinstance(product, dict), "product_boundary must be an object")
    _require(product.get("owner_model") == "single_owner", "owner model drift")
    _require(product.get("deployment_model") == "private_only", "deployment boundary drift")
    _require(product.get("financial_float_allowed") is False, "financial float is forbidden")
    _require(product.get("canonical_time") == "utc", "canonical time must remain UTC")
    _require(product.get("portfolio_product_complete") is False, "P2-01 cannot claim product completion")

    accounting = contract.get("accounting_policy")
    _require(isinstance(accounting, dict), "accounting_policy must be an object")
    _require(set(accounting.get("cost_basis_methods_initial", [])) == {"fifo", "weighted_average"}, "cost basis drift")
    _require(
        accounting.get("transfer_between_owned_accounts") == "non_disposal_with_basis_continuity",
        "transfer policy drift",
    )
    _require(accounting.get("negative_holding_default") == "reject_and_quarantine", "negative holding policy drift")
    _require(accounting.get("tax_advice_claimed") is False, "tax advice cannot be claimed")

    valuation = contract.get("valuation_policy")
    _require(isinstance(valuation, dict), "valuation_policy must be an object")
    for key in (
        "price_observation_immutable",
        "fx_observation_immutable",
        "stale_price_must_be_visible",
        "missing_price_must_be_visible",
    ):
        _require(valuation.get(key) is True, f"valuation policy requires {key}")
    _require(valuation.get("no_forward_fill_without_policy") is True, "implicit forward-fill is forbidden")


def _validate_import_and_export(contract: dict[str, Any]) -> None:
    imports = contract.get("import_and_reconciliation")
    _require(isinstance(imports, dict), "import_and_reconciliation must be an object")
    for key in (
        "dry_run_required",
        "deterministic_normalization",
        "content_checksum_required",
        "idempotent_reimport",
        "duplicate_detection",
        "unknown_rows_quarantined",
    ):
        _require(imports.get(key) is True, f"import runtime requires {key}")
    _require(imports.get("partial_publish_forbidden") is True, "partial import publication is forbidden")
    _require(imports.get("destructive_auto_fix") is False, "destructive reconciliation is forbidden")

    exports = contract.get("export_policy")
    _require(isinstance(exports, dict), "export_policy must be an object")
    _require(exports.get("export_first") is True, "export-first policy is required")
    _require(set(exports.get("formats", [])) == EXPECTED_EXPORT_FORMATS, "export format inventory drift")
    _require(set(exports.get("profiles", [])) == EXPECTED_EXPORT_PROFILES, "export profiles drift")
    for forbidden in ("credentials", "tokens", "recovery_codes", "private_keys", "session_identifiers"):
        _require(forbidden in exports.get("ai_safe_excludes", []), f"AI-safe export must exclude {forbidden}")
    _require(exports.get("public_download") is False, "public export download is forbidden")


def _validate_roadmap_and_boundaries(contract: dict[str, Any]) -> None:
    roadmap = contract.get("phase_two_roadmap")
    _require(isinstance(roadmap, list), "phase_two_roadmap must be a list")
    _require([stage.get("stage_id") for stage in roadmap] == EXPECTED_STAGES, "Phase 2 stage order drift")
    _require(roadmap[0].get("status") == "candidate", "P2-01 must remain candidate before Freeze")
    _require(all(stage.get("status") == "planned" for stage in roadmap[1:]), "future stages must remain planned")

    security = contract.get("security_boundary")
    _require(isinstance(security, dict), "security_boundary must be an object")
    _require(set(security) == FORBIDDEN_CAPABILITIES, "security capability inventory drift")
    for capability in FORBIDDEN_CAPABILITIES:
        _require(security.get(capability) is False, f"forbidden capability enabled: {capability}")

    trd_bot = contract.get("trd_bot_boundary")
    _require(isinstance(trd_bot, dict), "trd_bot_boundary must be an object")
    _require(trd_bot.get("trd_bot_0_3_0_compatible") is False, "TRD Bot 0.3.0 cannot be marked compatible")
    _require(trd_bot.get("runtime_mode") == "disabled_incompatible_provider", "TRD Bot runtime mode drift")
    _require(trd_bot.get("paper_shadow_only") is True, "TRD Bot projection must remain Paper/Shadow only")
    _require(trd_bot.get("live_orders") is False, "live orders are forbidden")
    _require(trd_bot.get("direct_database_access") is False, "direct TRD Bot database access is forbidden")

    server = contract.get("server_deployment_gate")
    _require(isinstance(server, dict), "server_deployment_gate must be an object")
    _require(server.get("gate_id") == "NEX-V0.1-SERVER-DEPLOYMENT-ACCEPTANCE", "server gate ID drift")
    _require(server.get("planned_country_code") == "DE", "planned VPS country drift")
    _require(server.get("status") == "deferred_to_server_deployment", "VPS gate must remain deferred")

    transition = contract.get("transition")
    _require(isinstance(transition, dict), "transition must be an object")
    _require(transition.get("next_allowed_stage") == "NEX-P2-01-FREEZE", "next stage must be P2-01 Freeze")
    _require(transition.get("post_freeze_stage") == "NEX-P2-02", "post-Freeze stage must be P2-02")
    _require(transition.get("requires_successful_ci_on_candidate_sha") is True, "candidate CI binding is required")
    _require(transition.get("freeze_before_implementation") is True, "P2-01 must Freeze before implementation")


def validate_contract(contract: dict[str, Any]) -> None:
    _require(contract.get("schema_version") == "nexora-phase-two-portfolio-domain-v1", "invalid schema version")
    _require(contract.get("decision_id") == "NEX-P2-01", "invalid decision ID")
    _require(contract.get("decision_date") == "2026-10-29", "invalid decision date")
    _require(contract.get("status") == "candidate", "P2-01 must remain a candidate")

    prerequisite = contract.get("prerequisite")
    _require(isinstance(prerequisite, dict), "prerequisite must be an object")
    _require(prerequisite.get("freeze_commit_sha") == P1_13_FREEZE_COMMIT, "P1-13 Freeze commit drift")
    _require(prerequisite.get("accepted_candidate_commit_sha") == P1_13_CANDIDATE_COMMIT, "P1-13 candidate drift")
    _require(prerequisite.get("artifact_checksum") == P1_13_ACCEPTANCE_CHECKSUM, "P1-13 artifact checksum drift")
    _require(prerequisite.get("record_checksum") == P1_13_RECORD_CHECKSUM, "P1-13 record checksum drift")
    _require(prerequisite.get("phase_one_complete") is True, "Phase 1 prerequisite must be complete")

    _validate_domain_model(contract)
    _validate_accounting_and_valuation(contract)
    _validate_import_and_export(contract)
    _validate_roadmap_and_boundaries(contract)


def validate_freeze_record(record: dict[str, Any], contract: dict[str, Any]) -> None:
    _require(
        record.get("schema_version") == "nexora-phase-two-portfolio-domain-freeze-v1",
        "invalid freeze schema",
    )
    _require(record.get("decision_id") == "NEX-P2-01", "invalid freeze decision ID")
    _require(record.get("repository") == "amirhosseinhamidian/nexora", "repository drift")
    _require(record.get("candidate_commit_sha") == CANDIDATE_SHA, "candidate SHA drift")
    _require(record.get("candidate_tree_sha") == CANDIDATE_TREE_SHA, "candidate tree drift")
    _require(record.get("candidate_commit_message") == CANDIDATE_MESSAGE, "candidate message drift")
    _require(record.get("candidate_predecessor_sha") == CANDIDATE_PREDECESSOR, "candidate parent drift")

    primary = record.get("github_actions")
    _validate_workflow(
        primary,
        label="phase two portfolio domain",
        run_id=40850501702,
        expected_jobs={
            "portfolio_domain_contract": (123368484562, "portfolio-domain-contract"),
            "web_regression": (123368484827, "web-regression"),
            "backend_regression": (123368484834, "backend-regression"),
        },
    )
    _require(primary.get("head_branch") == "feature/v0.1-portfolio-core", "primary workflow branch drift")
    required_markers = {
        "portfolio_domain_contract": (
            "phase_one_prerequisite_passed",
            "portfolio_domain_verifier_passed",
            "portfolio_domain_tests_passed",
            "repository_contract_tests_passed",
        ),
        "web_regression": (
            "locked_dependencies_installed",
            "format_passed",
            "lint_passed",
            "typecheck_passed",
            "tests_passed",
            "build_passed",
        ),
        "backend_regression": (
            "locked_dependencies_installed",
            "format_passed",
            "lint_passed",
            "typecheck_passed",
            "tests_passed",
        ),
    }
    for job_name, markers in required_markers.items():
        for marker in markers:
            _require(primary["jobs"][job_name].get(marker) is True, f"{job_name} did not confirm {marker}")

    regressions = record.get("regression_workflows")
    _require(isinstance(regressions, dict), "regression workflow evidence must be an object")
    _require(set(regressions) == set(EXPECTED_REGRESSION_WORKFLOWS), "regression workflow inventory mismatch")
    for label, (run_id, jobs) in EXPECTED_REGRESSION_WORKFLOWS.items():
        _validate_workflow(regressions[label], label=label, run_id=run_id, expected_jobs=jobs)

    evidence = record.get("portfolio_domain_contract")
    _require(isinstance(evidence, dict), "portfolio domain evidence must be an object")
    _require(evidence.get("schema_version") == contract.get("schema_version"), "contract schema mismatch")
    _require(
        evidence.get("path") == "contracts/nexora-v0.1-phase-two-portfolio-domain.json",
        "contract path drift",
    )
    _require(evidence.get("checksum") == CONTRACT_CHECKSUM, "recorded contract checksum drift")
    _require(evidence.get("checksum") == canonical_checksum(contract), "contract checksum mismatch")

    prerequisite = record.get("phase_one_prerequisite")
    _require(isinstance(prerequisite, dict), "Phase 1 prerequisite must be an object")
    _require(prerequisite.get("decision_id") == "NEX-P1-13", "Phase 1 prerequisite decision drift")
    _require(prerequisite.get("frozen") is True, "Phase 1 prerequisite is not frozen")
    _require(prerequisite.get("freeze_commit_sha") == P1_13_FREEZE_COMMIT, "P1-13 Freeze commit drift")
    _require(
        prerequisite.get("accepted_candidate_commit_sha") == P1_13_CANDIDATE_COMMIT,
        "P1-13 candidate drift",
    )
    _require(
        prerequisite.get("acceptance_record_path") == "artifacts/p1-13/phase-one-final-acceptance.json",
        "P1-13 acceptance path drift",
    )
    _require(
        prerequisite.get("acceptance_record_checksum")
        == canonical_checksum(_json(P1_13_ACCEPTANCE_PATH))
        == P1_13_ACCEPTANCE_CHECKSUM,
        "P1-13 acceptance checksum mismatch",
    )

    _require(record.get("recorded_on") == "2026-10-31", "invalid freeze record date")
    _require(record.get("frozen") is True, "P2-01 is not frozen")
    _require(record.get("portfolio_product_complete") is False, "P2-01 cannot claim product completion")
    _require(record.get("production_readiness_claimed") is False, "production readiness remains deferred")
    _require(
        record.get("server_deployment_gate") == "deferred_to_server_deployment",
        "server deployment gate drift",
    )
    for key in (
        "public_internet_deployment",
        "multi_user",
        "exchange_credentials",
        "wallet_private_keys_or_signing",
        "fund_transfer",
        "live_order_capability",
        "autonomous_ai_execution",
        "ml_training_or_inference",
        "financial_advice",
        "direct_trd_bot_database_access",
    ):
        _require(record.get(key) is False, f"freeze record cannot enable {key}")
    _require(record.get("next_allowed_stage") == "NEX-P2-02", "post-Freeze stage drift")


def main() -> int:
    validate_phase_one_prerequisite()
    contract = load_contract()
    validate_contract(contract)
    _require(canonical_checksum(contract) == CONTRACT_CHECKSUM, "P2-01 contract checksum drift")
    validate_freeze_record(load_freeze_record(), contract)
    print(f"schema_version={contract['schema_version']}")
    print(f"decision_id={contract['decision_id']}")
    print(f"contract_checksum={CONTRACT_CHECKSUM}")
    print("NEX_P1_13_PREREQUISITE=PASS")
    print("NEX_P2_01_PORTFOLIO_DOMAIN=PASS")
    print(f"candidate_commit_sha={CANDIDATE_SHA}")
    print("NEX_P2_01_FREEZE=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
