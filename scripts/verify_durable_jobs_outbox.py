#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "contracts/nexora-v0.1-durable-jobs-outbox.json"


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


def canonical_checksum(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


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
    for marker in ("NEX-P1-05", "20261025_0002", "FOR UPDATE SKIP LOCKED", "at-least-once", "NEX-P1-06"):
        _require(marker in document, f"document marker missing: {marker}")
    adr = (ROOT / "docs/adr/0019-postgresql-durable-work-coordination.md").read_text(encoding="utf-8")
    for marker in ("Status: Candidate for NEX-P1-05", "## Decision", "## Consequences"):
        _require(marker in adr, f"ADR marker missing: {marker}")


def main() -> int:
    validate_frozen_trd_bot_adapter()
    contract = load_contract()
    validate_contract(contract)
    validate_files()
    validate_documents()
    print(f"schema_version={contract['schema_version']}")
    print(f"decision_id={contract['decision_id']}")
    print(f"contract_checksum={canonical_checksum(contract)}")
    print("NEX_P1_04_PREREQUISITE=PASS")
    print("NEX_P1_05_DURABLE_JOBS_OUTBOX=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
