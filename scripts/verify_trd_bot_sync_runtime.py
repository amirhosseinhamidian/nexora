#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "contracts/nexora-v0.1-trd-bot-sync-runtime.json"
P1_08_FREEZE_PATH = ROOT / "artifacts/p1-08/audit-observability-freeze.json"
CONTRACT_CHECKSUM = "764142b08f398d53fed8d2ef75bdac90874d9bb03bc28567adf903004a1ab12f"
P1_08_FREEZE_CHECKSUM = "95ad753ff9e079c8479aba34b71782c2c992f841ec187866a2ccda5791f970ec"
P1_08_FREEZE_COMMIT = "6ba0ab6d86773aa7aaf4f488a6fd59c6d61cef0e"


class TrdBotSyncRuntimeContractError(ValueError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise TrdBotSyncRuntimeContractError(message)


def _json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    _require(isinstance(payload, dict), f"{path.name} must contain an object")
    return payload


def canonical_checksum(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def load_contract(path: Path = CONTRACT_PATH) -> dict[str, Any]:
    return _json(path)


def validate_frozen_p1_08() -> None:
    path = ROOT / "scripts/verify_audit_observability.py"
    spec = importlib.util.spec_from_file_location("verify_audit_observability", path)
    if spec is None or spec.loader is None:
        raise TrdBotSyncRuntimeContractError("unable to load frozen P1-08 verifier")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.validate_frozen_p1_07()
    contract = module.load_contract()
    module.validate_contract(contract)
    module.validate_files_and_runtime_markers()
    module.validate_freeze_record(module.load_freeze_record(), contract)


def validate_contract(contract: dict[str, Any]) -> None:
    _require(contract.get("schema_version") == "nexora-trd-bot-sync-runtime-v1", "invalid schema")
    _require(contract.get("decision_id") == "NEX-P1-09", "invalid decision ID")
    _require(contract.get("decision_date") == "2026-10-27", "invalid decision date")
    _require(contract.get("status") == "candidate", "P1-09 must remain candidate")
    prerequisite = contract.get("p1_08_prerequisite")
    _require(isinstance(prerequisite, dict), "P1-08 prerequisite must be an object")
    _require(prerequisite.get("decision_id") == "NEX-P1-08", "P1-08 prerequisite drift")
    _require(prerequisite.get("frozen") is True, "P1-08 prerequisite is not frozen")
    _require(prerequisite.get("freeze_commit_sha") == P1_08_FREEZE_COMMIT, "P1-08 commit drift")
    _require(prerequisite.get("freeze_record_checksum") == P1_08_FREEZE_CHECKSUM, "P1-08 checksum drift")
    _require(canonical_checksum(_json(P1_08_FREEZE_PATH)) == P1_08_FREEZE_CHECKSUM, "P1-08 record drift")
    _require(contract.get("closes_gaps") == ["NEX-P1-GAP-005"], "P1-09 gap ownership drift")

    delivery = contract.get("delivery")
    _require(isinstance(delivery, dict), "delivery must be an object")
    _require(delivery.get("migration_revision") == "20261027_0005", "migration revision drift")
    _require(
        delivery.get("registered_job_types") == ["trd_bot.event_sync", "trd_bot.snapshot_sync"],
        "registered job inventory drift",
    )
    _require(delivery.get("private_worker_cli_registration") is True, "worker registration is required")
    _require(delivery.get("bounded_page_size") == 500, "page bound drift")
    _require(delivery.get("event_delivery") == "at_least_once", "delivery semantics drift")
    _require(delivery.get("external_provider_smoke_claimed") is False, "external smoke cannot be claimed")

    ingestion = contract.get("event_ingestion")
    _require(isinstance(ingestion, dict), "event ingestion must be an object")
    required_ingestion = {
        "capability_negotiation_per_claim",
        "strict_envelope_validation",
        "owner_event_id_deduplication",
        "replay_content_conflict_fails_closed",
        "source_evidence_append_only",
        "checkpoint_compare_and_swap",
        "continuation_job_deterministic",
    }
    for key in required_ingestion:
        _require(ingestion.get(key) is True, f"event ingestion requires {key}")
    _require(
        ingestion.get("immutable_receipt_statuses") == ["applied", "quarantined"],
        "receipt states drift",
    )
    _require(
        ingestion.get("unknown_payload_schema_behavior") == "quarantine_and_advance_cursor",
        "unknown schema behavior drift",
    )

    transaction = contract.get("transaction_boundary")
    _require(isinstance(transaction, dict), "transaction boundary must be an object")
    for key in (
        "job_lease_validation",
        "receipt_evidence_checkpoint_outbox_and_continuation_atomic",
        "lost_lease_fails_closed",
    ):
        _require(transaction.get(key) is True, f"transaction boundary requires {key}")
    _require(transaction.get("raw_provider_error_persisted") is False, "provider errors must be bounded")

    resync = contract.get("full_resync")
    _require(isinstance(resync, dict), "full resync must be an object")
    _require(len(resync.get("resource_inventory", [])) == 10, "full resync resource inventory drift")
    for key in (
        "snapshot_generation_isolated",
        "snapshot_resources_complete_before_event_resume",
        "snapshot_evidence_versioned",
        "event_stream_resumed_after_snapshot_completion",
    ):
        _require(resync.get(key) is True, f"full resync requires {key}")
    _require(
        resync.get("cursor_expired_behavior") == "reset_event_checkpoint_and_enqueue_ordered_resource_snapshot_chain",
        "cursor expiry behavior drift",
    )

    worker = contract.get("worker_runtime")
    _require(isinstance(worker, dict), "worker runtime must be an object")
    _require(worker.get("empty_registry_claims_work") is False, "empty registry cannot claim")
    for key in (
        "registered_registry_explicit",
        "single_bounded_cycle_cli",
        "stable_worker_id_required",
        "initial_sync_requires_explicit_owner",
        "restart_and_reclaim_inherited_from_p1_05",
        "aggregate_observability_inherited_from_p1_08",
    ):
        _require(worker.get(key) is True, f"worker runtime requires {key}")

    security = contract.get("security_boundary")
    _require(isinstance(security, dict) and security, "security boundary must be an object")
    for capability, enabled in security.items():
        _require(enabled is False, f"forbidden sync capability enabled: {capability}")

    transition = contract.get("transition")
    _require(isinstance(transition, dict), "transition must be an object")
    _require(transition.get("ready_for_freeze") is True, "P1-09 is not ready for freeze")
    _require(transition.get("next_allowed_stage") == "NEX-P1-09-FREEZE", "next stage drift")
    _require(transition.get("post_freeze_stage") == "NEX-P1-10", "post-freeze stage drift")
    _require(canonical_checksum(contract) == CONTRACT_CHECKSUM, "sync runtime contract drift")


def validate_files_and_runtime_markers() -> None:
    required = {
        "apps/server/src/nexora/trd_bot_sync.py": (
            "class TrdBotSyncHandlers",
            "UNSUPPORTED_PAYLOAD_SCHEMA",
            "trd_bot.sync.full_resync.required.v1",
        ),
        "apps/server/src/nexora/adapters/postgresql/durable.py": (
            "class SyncReceiptWrite",
            "_append_sync_receipt",
            "_append_source_evidence",
        ),
        "apps/server/src/nexora/adapters/postgresql/models.py": ("class TrdBotSyncReceipt",),
        "apps/server/src/nexora/worker.py": ("TrdBotSyncHandlers", "--enqueue-initial-sync", "--once"),
        "alembic/versions/20261027_0005_trd_bot_sync_runtime.py": (
            'revision: str = "20261027_0005"',
            'down_revision: str | None = "20261026_0004"',
            "trd_bot_sync_receipts_immutable",
        ),
        "apps/server/tests/test_trd_bot_sync.py": ("test_expired_cursor_resets_checkpoint",),
        "apps/server/tests/test_trd_bot_sync_integration.py": (
            "test_sync_receipt_evidence_checkpoint_and_job_complete_atomically",
        ),
        "docs/adr/0023-durable-trd-bot-sync-runtime.md": ("Status: Candidate for NEX-P1-09",),
        "docs/v0.1/14-trd-bot-sync-runtime.md": ("NEX-P1-GAP-005", "NEX-P1-10"),
        ".github/workflows/trd-bot-sync-runtime.yml": ("TRD Bot sync runtime",),
    }
    for relative, markers in required.items():
        path = ROOT / relative
        _require(path.is_file(), f"missing P1-09 file: {relative}")
        content = path.read_text(encoding="utf-8")
        for marker in markers:
            _require(marker in content, f"missing P1-09 marker in {relative}: {marker}")


def main() -> int:
    validate_frozen_p1_08()
    contract = load_contract()
    validate_contract(contract)
    validate_files_and_runtime_markers()
    print(f"schema_version={contract['schema_version']}")
    print(f"decision_id={contract['decision_id']}")
    print(f"contract_checksum={canonical_checksum(contract)}")
    print("NEX_P1_08_PREREQUISITE=PASS")
    print("NEX_P1_09_TRD_BOT_SYNC_RUNTIME=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
