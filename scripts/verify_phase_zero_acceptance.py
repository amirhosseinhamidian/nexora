#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import importlib.util
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "contracts" / "nexora-v0.1-phase-zero-acceptance.json"
MATRIX_PATH = ROOT / "contracts" / "acceptance" / "v1" / "phase-zero-traceability.json"
DOCUMENT_PATH = ROOT / "docs" / "v0.1" / "04-phase-zero-acceptance-matrix.md"
ADR_PATH = ROOT / "docs" / "adr" / "0013-evidence-gated-phase-transition.md"
FREEZE_PATH = ROOT / "artifacts" / "p0-05" / "phase-zero-freeze.json"
SECURITY_VERIFIER_PATH = ROOT / "scripts" / "verify_security_boundary.py"

EXPECTED_PREREQUISITES = {
    "NEX-P0-01": {
        "contract_path": "contracts/nexora-v0.1-scope.json",
        "freeze_record_path": "artifacts/p0-01/scope-freeze.json",
        "freeze_commit_sha": "3327d9b4daa816eb271fa241247ad4ce21c708a3",
        "contract_checksum": "9ca6c10fb916861bab9a3e8facf7f24e5a84855e97a1f689a48954625377217c",
    },
    "NEX-P0-02": {
        "contract_path": "contracts/nexora-v0.1-technical-baseline.json",
        "freeze_record_path": "artifacts/p0-02/technical-baseline-freeze.json",
        "freeze_commit_sha": "386526c1324ffbf42e081dda0c362b5e92e21fce",
        "contract_checksum": "fba77f5f95c0dcaa59db9d5ed0b0e95290066a90a50d79f97a102375ddde69d3",
    },
    "NEX-P0-03": {
        "contract_path": "contracts/integration/v1/integration-contract.json",
        "freeze_record_path": "artifacts/p0-03/integration-contract-freeze.json",
        "freeze_commit_sha": "6243f0f28c6e7970d1323bad164e54b06bf2e173",
        "contract_checksum": "435e96fc928b71c5c98ebcb6f4e41a928f9f32e073c30ab567246f52c6d78c88",
    },
    "NEX-P0-04": {
        "contract_path": "contracts/nexora-v0.1-security-boundary.json",
        "freeze_record_path": "artifacts/p0-04/security-boundary-freeze.json",
        "freeze_commit_sha": "53e87e875d874f79def32468ece5dae43d8ddccf",
        "contract_checksum": "42120711a6884797b9dbf8db0304d4d24b69743a9ad1077bd0bf23ab488464ca",
    },
}
EXPECTED_VERIFIERS = {
    "verify_scope_contract",
    "verify_technical_baseline",
    "verify_integration_contracts",
    "verify_security_boundary",
    "verify_phase_zero_acceptance",
}
EXPECTED_DEBT_DISPOSITIONS = {
    "NEX-DEBT-P0-02-001": "transferred",
    "NEX-DEBT-P0-02-002": "closed",
    "NEX-DEBT-P0-02-003": "closed",
    "NEX-DEBT-P0-02-004": "closed",
    "NEX-DEBT-P0-02-005": "closed",
}
EXPECTED_SECURITY_KEYS = {
    "live_order_capability",
    "exchange_credentials",
    "wallet_or_fund_transfer",
    "direct_trd_bot_database_access",
    "autonomous_ai_execution",
    "public_internet_production_profile",
    "multi_tenant_identity",
}
SHA256 = re.compile(r"^[0-9a-f]{64}$")
GIT_SHA = re.compile(r"^[0-9a-f]{40}$")


class PhaseZeroAcceptanceError(ValueError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise PhaseZeroAcceptanceError(message)


def _load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as stream:
        payload = json.load(stream)
    _require(isinstance(payload, dict), f"{path.name} must contain a JSON object")
    return payload


def load_contract(path: Path = CONTRACT_PATH) -> dict[str, Any]:
    return _load_json(path)


def load_matrix(path: Path = MATRIX_PATH) -> dict[str, Any]:
    return _load_json(path)


def load_freeze_record(path: Path = FREEZE_PATH) -> dict[str, Any]:
    return _load_json(path)


def canonical_checksum(payload: dict[str, Any]) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _load_security_verifier() -> Any:
    spec = importlib.util.spec_from_file_location(
        "verify_security_boundary",
        SECURITY_VERIFIER_PATH,
    )
    if spec is None or spec.loader is None:
        raise PhaseZeroAcceptanceError("unable to load the frozen P0-04 verifier")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def validate_frozen_security_boundary() -> None:
    module = _load_security_verifier()
    module.validate_frozen_integration_contract()
    contract = module.load_contract()
    operational_policy = module.load_operational_policy()
    module.validate_contract(contract)
    module.validate_deployment_profiles(module.load_deployment_profiles())
    module.validate_security_headers(module.load_security_headers())
    module.validate_threat_model(module.load_threat_model())
    module.validate_operational_policy(operational_policy, contract)
    module.validate_audit_contract(
        module.load_audit_schema(),
        module.load_audit_fixture(),
        contract,
    )
    module.validate_documents()
    module.validate_freeze_record(module.load_freeze_record(), contract, operational_policy)


def _safe_repository_file(relative: Any, label: str) -> Path:
    _require(isinstance(relative, str) and relative, f"{label} must be a path")
    path = (ROOT / relative).resolve()
    try:
        path.relative_to(ROOT.resolve())
    except ValueError as error:
        raise PhaseZeroAcceptanceError(f"{label} escapes the repository") from error
    _require(path.is_file(), f"missing {label}: {relative}")
    return path


def validate_prerequisites(prerequisites: Any) -> None:
    _require(isinstance(prerequisites, list), "frozen_prerequisites must be an array")
    _require(len(prerequisites) == 4, "exactly four frozen prerequisites are required")
    _require(
        [item.get("decision_id") for item in prerequisites if isinstance(item, dict)]
        == list(EXPECTED_PREREQUISITES),
        "prerequisites must preserve the P0-01 through P0-04 order",
    )
    for item in prerequisites:
        _require(isinstance(item, dict), "each prerequisite must be an object")
        decision_id = item.get("decision_id")
        expected = EXPECTED_PREREQUISITES.get(decision_id)
        _require(expected is not None, f"unexpected prerequisite: {decision_id}")
        _require(item.get("frozen") is True, f"{decision_id} prerequisite is not frozen")
        for key, value in expected.items():
            _require(item.get(key) == value, f"{decision_id} {key} does not match frozen evidence")
        _require(GIT_SHA.fullmatch(item["freeze_commit_sha"]) is not None, f"{decision_id} freeze SHA is invalid")
        _require(SHA256.fullmatch(item["contract_checksum"]) is not None, f"{decision_id} checksum is invalid")
        contract = _load_json(_safe_repository_file(item["contract_path"], f"{decision_id} contract"))
        _require(
            canonical_checksum(contract) == item["contract_checksum"],
            f"{decision_id} contract checksum drift",
        )
        freeze = _load_json(_safe_repository_file(item["freeze_record_path"], f"{decision_id} freeze record"))
        _require(freeze.get("decision_id") == decision_id, f"{decision_id} freeze decision mismatch")
        _require(freeze.get("frozen") is True, f"{decision_id} freeze record is not frozen")


def _validate_debt_disposition(items: Any) -> None:
    _require(isinstance(items, list) and len(items) == 5, "all five baseline debts require disposition")
    baseline = _load_json(ROOT / "contracts" / "nexora-v0.1-technical-baseline.json")
    baseline_debts = {item["id"]: item for item in baseline.get("debt_inventory", [])}
    _require(set(baseline_debts) == set(EXPECTED_DEBT_DISPOSITIONS), "baseline debt inventory has drifted")
    seen: set[str] = set()
    for item in items:
        _require(isinstance(item, dict), "each debt disposition must be an object")
        debt_id = item.get("debt_id")
        _require(debt_id not in seen, f"duplicate debt disposition: {debt_id}")
        seen.add(debt_id)
        _require(debt_id in EXPECTED_DEBT_DISPOSITIONS, f"unknown debt disposition: {debt_id}")
        source = baseline_debts[debt_id]
        _require(item.get("disposition") == EXPECTED_DEBT_DISPOSITIONS[debt_id], f"invalid disposition for {debt_id}")
        _require(item.get("owner") == source["owner"], f"debt owner drift for {debt_id}")
        _require(item.get("due_stage") == source["due_stage"], f"debt due stage drift for {debt_id}")
        _require(item.get("blocking_phase_zero_freeze") is False, f"unresolved Phase 0 blocker: {debt_id}")
        _require(bool(item.get("rationale")), f"debt rationale is required: {debt_id}")
    _require(seen == set(EXPECTED_DEBT_DISPOSITIONS), "debt disposition is incomplete")


def validate_contract(contract: dict[str, Any]) -> None:
    _require(contract.get("schema_version") == "nexora-phase-zero-acceptance-v1", "invalid acceptance schema")
    _require(contract.get("decision_id") == "NEX-P0-05", "invalid acceptance decision ID")
    _require(contract.get("decision_date") == "2026-10-24", "invalid acceptance decision date")
    _require(contract.get("status") == "candidate", "P0-05 must remain a candidate before final freeze")

    product = contract.get("product")
    _require(isinstance(product, dict), "product must be an object")
    _require(product == {
        "name": "Nexora",
        "version": "0.1.0",
        "edition": "personal",
        "operating_model": "single_owner",
    }, "product boundary has drifted")

    phase = contract.get("phase")
    _require(isinstance(phase, dict), "phase must be an object")
    _require(phase.get("id") == "phase_zero", "invalid phase ID")
    _require(phase.get("runtime_delivered") is False, "Phase 0 cannot claim runtime delivery")
    _require(phase.get("production_readiness_claimed") is False, "Phase 0 cannot claim production readiness")
    _require(bool(phase.get("purpose")), "Phase 0 purpose is required")

    expected_artifacts = {
        "traceability_matrix": "contracts/acceptance/v1/phase-zero-traceability.json",
        "acceptance_document": "docs/v0.1/04-phase-zero-acceptance-matrix.md",
        "transition_adr": "docs/adr/0013-evidence-gated-phase-transition.md",
    }
    _require(contract.get("artifacts") == expected_artifacts, "acceptance artifact inventory has drifted")
    for label, relative in expected_artifacts.items():
        _safe_repository_file(relative, label)

    validate_prerequisites(contract.get("frozen_prerequisites"))

    supplemental = contract.get("supplemental_evidence")
    _require(isinstance(supplemental, list) and len(supplemental) == 1, "operational evidence is required")
    operations = supplemental[0]
    _require(operations.get("id") == "NEX-P0-EVIDENCE-OPERATIONS", "invalid operational evidence ID")
    _require(operations.get("schema_version") == "nexora-private-operations-policy-v1", "invalid operations schema")
    _require(operations.get("checksum") == "59f43b15ba53bb37b86897a6207b35ebdc9962b5a209720fb1c49671daee70bd", "operational evidence checksum drift")
    operations_payload = _load_json(_safe_repository_file(operations.get("path"), "operational evidence"))
    _require(canonical_checksum(operations_payload) == operations["checksum"], "operational policy content drift")

    summary = contract.get("acceptance_summary")
    _require(isinstance(summary, dict), "acceptance_summary must be an object")
    _require(summary.get("matrix_schema_version") == "nexora-phase-zero-traceability-v1", "matrix schema mismatch")
    _require(summary.get("required_requirement_count") == 12, "exactly twelve acceptance requirements are required")
    _require(summary.get("required_status") == "pass", "acceptance status must be pass")
    for key in ("all_decisions_require_owner", "all_requirements_require_evidence", "all_requirements_require_automated_verifier"):
        _require(summary.get(key) is True, f"acceptance summary requires {key}")
    _require(summary.get("unresolved_phase_zero_blockers") == 0, "Phase 0 blockers remain unresolved")

    _validate_debt_disposition(contract.get("debt_disposition"))

    deferred = contract.get("deferred_decisions")
    expected_deferred = {
        "NEX-DEFER-P1-RUNTIME",
        "NEX-DEFER-P1-DATA",
        "NEX-DEFER-P1-TRD",
        "NEX-DEFER-FUTURE-SAAS",
        "NEX-DEFER-FUTURE-ML",
    }
    _require(isinstance(deferred, list), "deferred_decisions must be an array")
    _require({item.get("id") for item in deferred if isinstance(item, dict)} == expected_deferred, "deferred decision inventory has drifted")
    for item in deferred:
        _require(bool(item.get("owner")), f"deferred decision owner is required: {item.get('id')}")
        _require(bool(item.get("decision")), f"deferred decision description is required: {item.get('id')}")
        _require(bool(item.get("phase_zero_boundary")), f"deferred boundary is required: {item.get('id')}")

    security = contract.get("security_boundary")
    _require(isinstance(security, dict) and set(security) == EXPECTED_SECURITY_KEYS, "security boundary inventory has drifted")
    for key in EXPECTED_SECURITY_KEYS:
        _require(security.get(key) is False, f"forbidden capability enabled: {key}")

    expected_gates = {
        "frozen_scope_verifier",
        "frozen_technical_baseline_verifier",
        "frozen_integration_contract_verifier",
        "frozen_security_boundary_verifier",
        "phase_zero_traceability_verifier",
        "all_contract_tests",
        "candidate_sha_bound_to_successful_github_actions_run",
        "final_freeze_record_committed_separately",
    }
    _require(set(contract.get("release_gates", [])) == expected_gates, "release gate inventory is incomplete")

    transition = contract.get("transition")
    _require(isinstance(transition, dict), "transition must be an object")
    _require(transition.get("ready_for_phase_zero_freeze") is True, "candidate is not ready for Phase 0 freeze")
    _require(transition.get("runtime_bootstrap_authorized") is False, "runtime bootstrap requires the final freeze")
    _require(transition.get("next_allowed_stage") == "NEX-P0-05-FREEZE", "next stage must be P0-05 freeze")
    _require(transition.get("post_freeze_stage") == "NEX-P1-01", "post-freeze stage must be P1-01")
    _require("candidate_SHA" in transition.get("authorization_condition", ""), "transition condition must bind candidate SHA")


def validate_matrix(matrix: dict[str, Any], contract: dict[str, Any]) -> None:
    _require(matrix.get("schema_version") == "nexora-phase-zero-traceability-v1", "invalid matrix schema")
    _require(matrix.get("decision_id") == "NEX-P0-05", "invalid matrix decision ID")
    _require(matrix.get("status") == "candidate", "traceability matrix must remain a candidate")
    requirements = matrix.get("requirements")
    expected_ids = [f"NEX-P0-REQ-{index:03d}" for index in range(1, 13)]
    _require(isinstance(requirements, list) and len(requirements) == 12, "traceability matrix requires twelve rows")
    _require([item.get("id") for item in requirements if isinstance(item, dict)] == expected_ids, "requirement IDs must be unique and ordered")

    covered_decisions: set[str] = set()
    for requirement in requirements:
        requirement_id = requirement.get("id")
        _require(bool(requirement.get("title")), f"requirement title is missing: {requirement_id}")
        _require(bool(requirement.get("owner")), f"requirement owner is missing: {requirement_id}")
        _require(requirement.get("status") == "pass", f"requirement is not accepted: {requirement_id}")
        source_decisions = requirement.get("source_decisions")
        _require(isinstance(source_decisions, list) and source_decisions, f"source decision is missing: {requirement_id}")
        _require(set(source_decisions) <= {"NEX-P0-01", "NEX-P0-02", "NEX-P0-03", "NEX-P0-04", "NEX-P0-05"}, f"unknown source decision: {requirement_id}")
        covered_decisions.update(source_decisions)
        evidence = requirement.get("evidence")
        _require(isinstance(evidence, list) and len(evidence) >= 2, f"durable evidence is incomplete: {requirement_id}")
        _require(len(evidence) == len(set(evidence)), f"duplicate evidence path: {requirement_id}")
        for relative in evidence:
            _safe_repository_file(relative, f"{requirement_id} evidence")
        verifiers = requirement.get("verifiers")
        _require(isinstance(verifiers, list) and verifiers, f"automated verifier is missing: {requirement_id}")
        _require(set(verifiers) <= EXPECTED_VERIFIERS, f"unknown verifier: {requirement_id}")
        for verifier in verifiers:
            _safe_repository_file(f"scripts/{verifier}.py", f"{requirement_id} verifier")

    _require(
        covered_decisions == {"NEX-P0-01", "NEX-P0-02", "NEX-P0-03", "NEX-P0-04", "NEX-P0-05"},
        "not every Phase 0 decision is traceable",
    )
    _require(
        len(requirements) == contract["acceptance_summary"]["required_requirement_count"],
        "matrix row count disagrees with the acceptance contract",
    )


def validate_freeze_record(
    record: dict[str, Any],
    contract: dict[str, Any],
    matrix: dict[str, Any],
) -> None:
    _require(
        record.get("schema_version") == "nexora-phase-zero-freeze-v1",
        "invalid Phase 0 freeze schema",
    )
    _require(record.get("decision_id") == "NEX-P0-05", "invalid freeze decision ID")
    _require(record.get("repository") == "amirhosseinhamidian/nexora", "invalid repository")
    _require(
        record.get("candidate_commit_sha")
        == "20cf4eacc095d19711b3b80f518c56019445e87e",
        "candidate SHA does not match accepted P0-05 evidence",
    )
    _require(
        GIT_SHA.fullmatch(record.get("candidate_commit_sha", "")) is not None,
        "candidate SHA must be a full lowercase Git SHA",
    )
    _require(
        record.get("candidate_commit_message")
        == "docs(nexora): establish P0-05 phase-zero acceptance",
        "candidate commit message does not match accepted evidence",
    )

    actions = record.get("github_actions")
    _require(isinstance(actions, dict), "github_actions must be an object")
    _require(actions.get("run_id") == 40080625175, "invalid GitHub Actions run ID")
    _require(
        actions.get("run_url")
        == "https://github.com/amirhosseinhamidian/nexora/actions/runs/40080625175",
        "GitHub Actions URL does not match the accepted run",
    )
    _require(
        actions.get("head_branch") == "feature/v0.1-foundation",
        "invalid GitHub Actions head branch",
    )
    _require(actions.get("event") == "push", "invalid GitHub Actions event")
    _require(actions.get("attempt") == 1, "invalid GitHub Actions attempt")
    _require(actions.get("conclusion") == "success", "workflow was not successful")

    jobs = actions.get("jobs")
    _require(isinstance(jobs, dict), "GitHub Actions jobs must be an object")
    expected_jobs = {
        "scope_contract": (120833225184, "scope-contract"),
        "technical_baseline": (120833225186, "technical-baseline"),
        "integration_contract": (120833225261, "integration-contract"),
        "security_boundary": (120833225127, "security-boundary"),
        "phase_zero_acceptance": (120833225051, "phase-zero-acceptance"),
    }
    _require(set(jobs) == set(expected_jobs), "freeze requires all five Phase 0 CI jobs")
    for key, (job_id, name) in expected_jobs.items():
        job = jobs.get(key)
        _require(isinstance(job, dict), f"{name} evidence must be an object")
        _require(job.get("job_id") == job_id, f"invalid {name} job ID")
        _require(job.get("name") == name, f"invalid {name} job name")
        _require(job.get("conclusion") == "success", f"{name} job was not successful")
        _require(job.get("contract_tests_passed") is True, f"{name} contract tests not confirmed")

    required_markers = {
        "scope_contract": ("scope_verifier_passed",),
        "technical_baseline": ("scope_prerequisite_passed", "baseline_verifier_passed"),
        "integration_contract": (
            "scope_prerequisite_passed",
            "baseline_prerequisite_passed",
            "integration_verifier_passed",
        ),
        "security_boundary": (
            "scope_prerequisite_passed",
            "baseline_prerequisite_passed",
            "integration_prerequisite_passed",
            "security_verifier_passed",
        ),
        "phase_zero_acceptance": (
            "scope_prerequisite_passed",
            "baseline_prerequisite_passed",
            "integration_prerequisite_passed",
            "security_prerequisite_passed",
            "acceptance_verifier_passed",
        ),
    }
    for job_name, markers in required_markers.items():
        for marker in markers:
            _require(jobs[job_name].get(marker) is True, f"{job_name} did not confirm {marker}")

    contract_evidence = record.get("phase_zero_acceptance_contract")
    _require(isinstance(contract_evidence, dict), "acceptance contract evidence must be an object")
    _require(
        contract_evidence.get("schema_version") == contract.get("schema_version"),
        "acceptance contract schema mismatch",
    )
    _require(
        contract_evidence.get("checksum") == canonical_checksum(contract),
        "acceptance contract checksum mismatch",
    )

    matrix_evidence = record.get("traceability_matrix")
    _require(isinstance(matrix_evidence, dict), "traceability evidence must be an object")
    _require(
        matrix_evidence.get("schema_version") == matrix.get("schema_version"),
        "traceability schema mismatch",
    )
    _require(
        matrix_evidence.get("checksum") == canonical_checksum(matrix),
        "traceability checksum mismatch",
    )

    security_module = _load_security_verifier()
    security_contract = security_module.load_contract()
    prerequisite = record.get("security_boundary_prerequisite")
    _require(isinstance(prerequisite, dict), "security prerequisite must be an object")
    _require(prerequisite.get("decision_id") == "NEX-P0-04", "invalid security prerequisite")
    _require(prerequisite.get("frozen") is True, "security prerequisite is not frozen")
    _require(
        prerequisite.get("contract_checksum")
        == security_module.canonical_checksum(security_contract),
        "security prerequisite checksum mismatch",
    )

    _require(record.get("recorded_on") == "2026-10-24", "invalid freeze record date")
    _require(record.get("frozen") is True, "Phase 0 is not frozen")
    _require(record.get("phase_zero_complete") is True, "Phase 0 completion is not confirmed")
    _require(
        record.get("runtime_bootstrap_authorized") is True,
        "runtime bootstrap was not authorized by the final freeze",
    )
    _require(record.get("next_allowed_stage") == "NEX-P1-01", "invalid post-freeze next stage")


def validate_documents() -> None:
    document = DOCUMENT_PATH.read_text(encoding="utf-8")
    markers = (
        "NEX-P0-05",
        "وضعیت: **Frozen**",
        "NEX-P0-01",
        "NEX-P0-02",
        "NEX-P0-03",
        "NEX-P0-04",
        "NEX-DEBT-P0-02-001",
        "NEX-P0-05-FREEZE",
        "NEX-P1-01",
        "runtime_bootstrap_authorized=false",
        "NEX_P0_04_PREREQUISITE=PASS",
        "NEX_P0_05_PHASE_ZERO_ACCEPTANCE=PASS",
        "NEX_P0_05_FREEZE=PASS",
        "20cf4eacc095d19711b3b80f518c56019445e87e",
        "40080625175",
    )
    missing = [marker for marker in markers if marker not in document]
    _require(not missing, f"acceptance document is missing markers: {missing}")
    adr = ADR_PATH.read_text(encoding="utf-8")
    for marker in ("Status: Accepted and frozen by NEX-P0-05", "## Decision", "## Consequences", "candidate SHA", "NEX-P1-01"):
        _require(marker in adr, f"transition ADR is missing marker: {marker}")


def main() -> int:
    validate_frozen_security_boundary()
    contract = load_contract()
    matrix = load_matrix()
    validate_contract(contract)
    validate_matrix(matrix, contract)
    validate_documents()
    freeze_record = load_freeze_record()
    validate_freeze_record(freeze_record, contract, matrix)
    print(f"schema_version={contract['schema_version']}")
    print(f"decision_id={contract['decision_id']}")
    print(f"contract_checksum={canonical_checksum(contract)}")
    print(f"traceability_checksum={canonical_checksum(matrix)}")
    print(f"candidate_commit_sha={freeze_record['candidate_commit_sha']}")
    print("NEX_P0_04_PREREQUISITE=PASS")
    print("NEX_P0_05_PHASE_ZERO_ACCEPTANCE=PASS")
    print("NEX_P0_05_FREEZE=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
