#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "contracts/nexora-v0.1-durable-jobs-outbox.json"
FREEZE_PATH = ROOT / "artifacts/p1-05/durable-jobs-outbox-freeze.json"


class DurableWorkContractError(ValueError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise DurableWorkContractError(message)


def _json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    _require(isinstance(payload, dict), f"{path.name} must contain an object")
    return payload


def load_contract(path: Path = CONTRACT_PATH) -> dict[str, Any]:
    return _json(path)


def load_freeze_record(path: Path = FREEZE_PATH) -> dict[str, Any]:
    return _json(path)


def canonical_checksum(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _validate_workflow(
    workflow: object,
    *,
    label: str,
    run_id: int,
    expected_jobs: dict[str, tuple[int, str]],
    candidate_sha: str,
) -> None:
    _require(isinstance(workflow, dict), f"{label} workflow evidence must be an object")
    _require(workflow.get("run_id") == run_id, f"{label} run ID drift")
    _require(workflow.get("head_sha") == candidate_sha, f"{label} workflow head SHA drift")
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


def validate_frozen_trd_bot_adapter() -> None:
    path = ROOT / "scripts/verify_trd_bot_adapter.py"
    spec = importlib.util.spec_from_file_location("verify_trd_bot_adapter", path)
    if spec is None or spec.loader is None:
        raise DurableWorkContractError("unable to load frozen P1-04 verifier")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.validate_frozen_postgresql_schema()
    contract = module.load_contract()
    module.validate_contract(contract)
    module.validate_files()
    module.validate_documents()
    module.validate_freeze_record(module.load_freeze_record(), contract)


def validate_contract(contract: dict[str, Any]) -> None:
    _require(contract.get("schema_version") == "nexora-durable-jobs-outbox-v1", "invalid schema")
    _require(contract.get("decision_id") == "NEX-P1-05", "invalid decision ID")
    _require(contract.get("status") == "candidate", "P1-05 must remain candidate")
    prerequisite = contract.get("trd_bot_adapter_prerequisite")
    _require(isinstance(prerequisite, dict), "P1-04 prerequisite must be an object")
    _require(prerequisite.get("decision_id") == "NEX-P1-04", "invalid P1-04 prerequisite")
    _require(prerequisite.get("frozen") is True, "P1-04 prerequisite is not frozen")
    _require(
        prerequisite.get("freeze_commit_sha") == "6b76b07a4d181f232a79c46e242793f8b9cea51e",
        "P1-04 freeze commit drift",
    )
    freeze = _json(ROOT / prerequisite["freeze_record_path"])
    _require(canonical_checksum(freeze) == prerequisite.get("freeze_record_checksum"), "P1-04 freeze checksum drift")

    delivery = contract.get("delivery")
    _require(isinstance(delivery, dict), "delivery must be an object")
    _require(delivery.get("migration_revision") == "20261025_0002", "migration revision drift")
    for key in ("projection_checkpoints", "durable_background_jobs", "transactional_outbox", "generic_worker_engine"):
        _require(delivery.get(key) is True, f"P1-05 must deliver {key}")
    for key in ("provider_handler_registration", "external_provider_smoke_claimed"):
        _require(delivery.get(key) is False, f"P1-05 cannot claim {key}")

    jobs = contract.get("job_protocol")
    _require(isinstance(jobs, dict), "job protocol must be an object")
    _require(jobs.get("queue_backend") == "postgresql_17", "queue backend drift")
    _require(jobs.get("claim_locking") == "for_update_skip_locked", "job claim locking drift")
    _require(jobs.get("delivery_semantics") == "at_least_once", "job delivery semantics drift")
    for key in (
        "immutable_payload_sha256",
        "lease_reclaim",
        "lease_renewal",
        "bounded_attempts",
        "expired_final_attempt_dead_lettered",
        "lost_lease_fails_closed",
        "claim_batch_is_bounded",
    ):
        _require(jobs.get(key) is True, f"job protocol requires {key}")

    checkpoint = contract.get("checkpoint_protocol")
    _require(isinstance(checkpoint, dict), "checkpoint protocol must be an object")
    _require(
        checkpoint.get("identity") == ["owner_id", "consumer_name", "stream_name"],
        "checkpoint identity drift",
    )
    for key in ("optimistic_row_version", "cursor_nullable_for_initial_sync", "provider_version_required", "contract_version_required"):
        _require(checkpoint.get(key) is True, f"checkpoint protocol requires {key}")

    outbox = contract.get("outbox_protocol")
    _require(isinstance(outbox, dict), "outbox protocol must be an object")
    _require(outbox.get("written_in_job_completion_transaction") is True, "outbox must share completion transaction")
    _require(outbox.get("claim_locking") == "for_update_skip_locked", "outbox claim locking drift")
    _require(outbox.get("delivery_semantics") == "at_least_once", "outbox delivery semantics drift")

    worker = contract.get("worker_boundary")
    _require(isinstance(worker, dict), "worker boundary must be an object")
    _require(worker.get("handler_registry") == "explicit_dependency_injection", "handler registry drift")
    for key in ("unknown_job_types_claimed", "empty_handler_registry_claims_work", "exception_details_persisted"):
        _require(worker.get(key) is False, f"worker boundary requires false: {key}")

    security = contract.get("security_boundary")
    _require(isinstance(security, dict), "security boundary must be an object")
    for key, value in security.items():
        _require(value is False, f"forbidden capability enabled: {key}")
    transition = contract.get("transition")
    _require(isinstance(transition, dict), "transition must be an object")
    _require(transition.get("ready_for_freeze") is True, "P1-05 is not ready for freeze")
    _require(transition.get("next_allowed_stage") == "NEX-P1-05-FREEZE", "next stage must be freeze")
    _require(transition.get("post_freeze_stage") == "NEX-P1-06", "post-freeze stage drift")


def validate_files() -> None:
    required = (
        "alembic/versions/20261025_0002_durable_jobs_checkpoints_outbox.py",
        "apps/server/src/nexora/adapters/postgresql/durable.py",
        "apps/server/src/nexora/durable_worker.py",
        "apps/server/tests/test_durable_repository.py",
        "apps/server/tests/test_durable_worker.py",
        "artifacts/p1-05/durable-jobs-outbox-freeze.json",
        "contracts/nexora-v0.1-durable-jobs-outbox.json",
        "docs/adr/0019-postgresql-durable-work-coordination.md",
        "docs/v0.1/09-durable-jobs-checkpoints-and-outbox.md",
        ".github/workflows/durable-jobs-outbox.yml",
    )
    for relative in required:
        _require((ROOT / relative).is_file(), f"missing P1-05 file: {relative}")
    migration = (ROOT / required[0]).read_text(encoding="utf-8")
    for marker in (
        'revision: str = "20261025_0002"',
        'down_revision: str | None = "20261025_0001"',
        '"projection_checkpoints"',
        '"background_jobs"',
        '"outbox_events"',
        "def downgrade()",
    ):
        _require(marker in migration, f"migration marker missing: {marker}")
    repository = (ROOT / required[1]).read_text(encoding="utf-8")
    for marker in (
        "with_for_update(skip_locked=True)",
        "IdempotencyConflict",
        "LeaseLost",
        "CheckpointConflict",
        "def complete_job(",
        "def claim_outbox(",
    ):
        _require(marker in repository, f"repository marker missing: {marker}")
    for forbidden in ("redis", "kafka", "live_order", "exchange_secret", "wallet"):
        _require(forbidden not in repository.lower(), f"forbidden durable repository capability: {forbidden}")


def validate_documents() -> None:
    document = (ROOT / "docs/v0.1/09-durable-jobs-checkpoints-and-outbox.md").read_text(encoding="utf-8")
    for marker in (
        "NEX-P1-05",
        "وضعیت: **Frozen**",
        "20261025_0002",
        "FOR UPDATE SKIP LOCKED",
        "at-least-once",
        "c89df00ca7c70744ee655b94811b41ec73fc367a",
        "40286578346",
        "NEX-P1-06",
    ):
        _require(marker in document, f"document marker missing: {marker}")
    adr = (ROOT / "docs/adr/0019-postgresql-durable-work-coordination.md").read_text(encoding="utf-8")
    for marker in ("Status: Frozen by NEX-P1-05", "## Decision", "## Consequences"):
        _require(marker in adr, f"ADR marker missing: {marker}")


def validate_freeze_record(record: dict[str, Any], contract: dict[str, Any]) -> None:
    _require(record.get("schema_version") == "nexora-durable-jobs-outbox-freeze-v1", "invalid freeze schema")
    _require(record.get("decision_id") == "NEX-P1-05", "invalid freeze decision")
    _require(record.get("repository") == "amirhosseinhamidian/nexora", "invalid freeze repository")
    candidate_sha = record.get("candidate_commit_sha")
    _require(candidate_sha == "c89df00ca7c70744ee655b94811b41ec73fc367a", "candidate SHA drift")
    _require(
        record.get("candidate_commit_message") == "feat(nexora): implement P1-05 durable jobs and outbox",
        "candidate commit message drift",
    )

    actions = record.get("github_actions")
    _validate_workflow(
        actions,
        label="durable jobs and outbox",
        run_id=40286578346,
        expected_jobs={
            "durable_contract": (121451549870, "durable-contract"),
            "backend": (121451549919, "backend"),
            "postgresql_17": (121451549706, "postgresql-17"),
        },
        candidate_sha=candidate_sha,
    )
    _require(actions.get("head_branch") == "feature/v0.1-foundation", "invalid GitHub Actions branch")
    required_markers = {
        "durable_contract": (
            "p1_04_prerequisite_passed",
            "durable_work_verifier_passed",
            "repository_contract_tests_passed",
        ),
        "backend": (
            "locked_dependencies_installed",
            "format_passed",
            "lint_passed",
            "typecheck_passed",
            "non_integration_tests_passed",
        ),
        "postgresql_17": (
            "private_dsn_fixture_created",
            "upgrade_head_passed",
            "durable_integration_tests_passed",
            "downgrade_base_passed",
            "rebuild_head_passed",
            "migration_drift_check_passed",
        ),
    }
    for job_name, markers in required_markers.items():
        for marker in markers:
            _require(actions["jobs"][job_name].get(marker) is True, f"{job_name} did not confirm {marker}")

    regression = record.get("regression_workflows")
    _require(isinstance(regression, dict), "regression workflow evidence must be an object")
    expected_regression = {
        "application_composition": (
            40286578173,
            {
                "backend": (121451548737, "backend"),
                "composition_contract": (121451549140, "composition-contract"),
            },
        ),
        "runtime_foundation": (
            40286578180,
            {
                "backend": (121451548455, "backend"),
                "foundation_contract": (121451548703, "foundation-contract"),
                "web": (121451548793, "web"),
            },
        ),
        "trd_bot_adapter": (
            40286578257,
            {
                "adapter_contract": (121451548734, "adapter-contract"),
                "backend": (121451549117, "backend"),
            },
        ),
        "postgresql_schema": (
            40286578330,
            {
                "backend": (121451549057, "backend"),
                "database_contract": (121451549221, "database-contract"),
                "postgresql_17": (121451549246, "postgresql-17"),
            },
        ),
    }
    _require(set(regression) == set(expected_regression), "regression workflow inventory mismatch")
    for label, (run_id, jobs) in expected_regression.items():
        _validate_workflow(
            regression[label],
            label=label,
            run_id=run_id,
            expected_jobs=jobs,
            candidate_sha=candidate_sha,
        )

    contract_evidence = record.get("durable_jobs_outbox_contract")
    _require(isinstance(contract_evidence, dict), "durable contract evidence must be an object")
    _require(contract_evidence.get("schema_version") == contract.get("schema_version"), "contract schema mismatch")
    _require(contract_evidence.get("checksum") == canonical_checksum(contract), "contract checksum mismatch")
    prerequisite = record.get("trd_bot_adapter_prerequisite")
    _require(isinstance(prerequisite, dict), "P1-04 freeze prerequisite must be an object")
    _require(prerequisite.get("decision_id") == "NEX-P1-04", "invalid P1-04 freeze prerequisite")
    _require(prerequisite.get("frozen") is True, "P1-04 freeze prerequisite is not frozen")
    p1_04_record = _json(ROOT / "artifacts/p1-04/trd-bot-adapter-freeze.json")
    _require(
        prerequisite.get("freeze_record_checksum") == canonical_checksum(p1_04_record),
        "P1-04 freeze record checksum mismatch",
    )
    _require(record.get("recorded_on") == "2026-10-26", "invalid freeze record date")
    _require(record.get("frozen") is True, "P1-05 is not frozen")
    _require(record.get("durable_jobs_outbox_complete") is True, "P1-05 stage is incomplete")
    _require(record.get("at_least_once_delivery") is True, "at-least-once delivery is not recorded")
    for key in ("exactly_once_delivery_claimed", "external_provider_smoke_claimed", "live_execution_capability"):
        _require(record.get(key) is False, f"freeze record cannot enable {key}")
    _require(record.get("next_allowed_stage") == "NEX-P1-06", "invalid post-freeze next stage")


def main() -> int:
    validate_frozen_trd_bot_adapter()
    contract = load_contract()
    validate_contract(contract)
    validate_files()
    validate_documents()
    freeze_record = load_freeze_record()
    validate_freeze_record(freeze_record, contract)
    print(f"schema_version={contract['schema_version']}")
    print(f"decision_id={contract['decision_id']}")
    print(f"contract_checksum={canonical_checksum(contract)}")
    print(f"candidate_commit_sha={freeze_record['candidate_commit_sha']}")
    print("NEX_P1_04_PREREQUISITE=PASS")
    print("NEX_P1_05_DURABLE_JOBS_OUTBOX=PASS")
    print("NEX_P1_05_FREEZE=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
