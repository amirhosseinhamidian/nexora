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
FREEZE_PATH = ROOT / "artifacts/p1-09/trd-bot-sync-runtime-freeze.json"
CONTRACT_CHECKSUM = "764142b08f398d53fed8d2ef75bdac90874d9bb03bc28567adf903004a1ab12f"
P1_08_FREEZE_CHECKSUM = "95ad753ff9e079c8479aba34b71782c2c992f841ec187866a2ccda5791f970ec"
P1_08_FREEZE_COMMIT = "6ba0ab6d86773aa7aaf4f488a6fd59c6d61cef0e"
CANDIDATE_SHA = "53588b3c53a8244f59f1798a06efbe084e7516d5"
CANDIDATE_MESSAGE = "feat(nexora): implement P1-09 TRD Bot sync runtime"
CANDIDATE_PREDECESSOR = "6ba0ab6d86773aa7aaf4f488a6fd59c6d61cef0e"


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
        "docs/adr/0023-durable-trd-bot-sync-runtime.md": ("Status: Frozen by NEX-P1-09",),
        "docs/v0.1/14-trd-bot-sync-runtime.md": (
            "NEX-P1-GAP-005",
            CANDIDATE_SHA,
            "40464364305",
            "NEX-P1-10",
        ),
        ".github/workflows/trd-bot-sync-runtime.yml": ("TRD Bot sync runtime",),
        "artifacts/p1-09/trd-bot-sync-runtime-freeze.json": (CANDIDATE_SHA,),
    }
    for relative, markers in required.items():
        path = ROOT / relative
        _require(path.is_file(), f"missing P1-09 file: {relative}")
        content = path.read_text(encoding="utf-8")
        for marker in markers:
            _require(marker in content, f"missing P1-09 marker in {relative}: {marker}")


def validate_freeze_record(record: dict[str, Any], contract: dict[str, Any]) -> None:
    _require(record.get("schema_version") == "nexora-trd-bot-sync-runtime-freeze-v1", "invalid freeze schema")
    _require(record.get("decision_id") == "NEX-P1-09", "invalid freeze decision ID")
    _require(record.get("repository") == "amirhosseinhamidian/nexora", "freeze repository drift")
    _require(record.get("candidate_commit_sha") == CANDIDATE_SHA, "candidate SHA drift")
    _require(record.get("candidate_commit_message") == CANDIDATE_MESSAGE, "candidate commit message drift")
    _require(record.get("candidate_predecessor_sha") == CANDIDATE_PREDECESSOR, "candidate predecessor drift")

    primary = record.get("github_actions")
    _validate_workflow(
        primary,
        label="TRD Bot sync runtime",
        run_id=40464364305,
        expected_jobs={
            "sync_contract": (122056134001, "sync-contract"),
            "backend": (122056134449, "backend"),
            "postgresql_17": (122056134474, "postgresql-17"),
        },
    )
    _require(primary.get("head_branch") == "feature/v0.1-foundation", "primary workflow branch drift")
    required_markers = {
        "sync_contract": (
            "locked_dependencies_installed",
            "p1_08_freeze_prerequisite_passed",
            "sync_runtime_verifier_passed",
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
            "sync_atomicity_integration_passed",
            "downgrade_base_passed",
            "rebuild_head_passed",
            "migration_drift_check_passed",
        ),
    }
    for job_name, markers in required_markers.items():
        for marker in markers:
            _require(primary["jobs"][job_name].get(marker) is True, f"{job_name} did not confirm {marker}")

    regression = record.get("regression_workflows")
    _require(isinstance(regression, dict), "regression workflow evidence must be an object")
    expected_regression = {
        "contracts": (
            40464364227,
            {
                "scope_contract": (122056134061, "scope-contract"),
                "phase_zero_acceptance": (122056134211, "phase-zero-acceptance"),
                "security_boundary": (122056134361, "security-boundary"),
                "integration_contract": (122056134415, "integration-contract"),
                "technical_baseline": (122056134579, "technical-baseline"),
            },
        ),
        "trd_bot_adapter": (
            40464364238,
            {
                "backend": (122056134207, "backend"),
                "adapter_contract": (122056134503, "adapter-contract"),
            },
        ),
        "application_composition": (
            40464364282,
            {
                "backend": (122056134282, "backend"),
                "composition_contract": (122056134528, "composition-contract"),
            },
        ),
        "single_owner_identity_runtime": (
            40464364229,
            {
                "identity_contract": (122056134070, "identity-contract"),
                "postgresql_17": (122056134388, "postgresql-17"),
                "backend": (122056134407, "backend"),
                "private_topology": (122056134425, "private-topology"),
            },
        ),
        "postgresql_schema": (
            40464364236,
            {
                "database_contract": (122056133909, "database-contract"),
                "backend": (122056134161, "backend"),
                "postgresql_17": (122056134276, "postgresql-17"),
            },
        ),
        "audit_observability": (
            40464364242,
            {
                "observability_contract": (122056133879, "observability-contract"),
                "backend": (122056134154, "backend"),
                "postgresql_17": (122056134245, "postgresql-17"),
            },
        ),
        "phase_one_readiness": (
            40464364266,
            {
                "backend": (122056134192, "backend"),
                "readiness_contract": (122056134284, "readiness-contract"),
                "web": (122056134352, "web"),
            },
        ),
        "runtime_foundation": (
            40464364307,
            {
                "web": (122056134026, "web"),
                "foundation_contract": (122056134319, "foundation-contract"),
                "backend": (122056134488, "backend"),
            },
        ),
        "runtime_api_auth": (
            40464364244,
            {
                "runtime_contract": (122056134143, "runtime-contract"),
                "backend": (122056134267, "backend"),
                "cross_language_contract": (122056134299, "cross-language-contract"),
                "postgresql_17": (122056134354, "postgresql-17"),
            },
        ),
        "durable_jobs_outbox": (
            40464364263,
            {
                "postgresql_17": (122056133979, "postgresql-17"),
                "backend": (122056134372, "backend"),
                "durable_contract": (122056134410, "durable-contract"),
            },
        ),
    }
    _require(set(regression) == set(expected_regression), "regression workflow inventory mismatch")
    for label, (run_id, jobs) in expected_regression.items():
        _validate_workflow(regression[label], label=label, run_id=run_id, expected_jobs=jobs)

    evidence = record.get("trd_bot_sync_runtime_contract")
    _require(isinstance(evidence, dict), "sync runtime contract evidence must be an object")
    _require(evidence.get("schema_version") == contract.get("schema_version"), "contract schema mismatch")
    _require(evidence.get("path") == "contracts/nexora-v0.1-trd-bot-sync-runtime.json", "contract path drift")
    _require(evidence.get("checksum") == CONTRACT_CHECKSUM, "recorded contract checksum drift")
    _require(evidence.get("checksum") == canonical_checksum(contract), "contract checksum mismatch")

    prerequisite = record.get("p1_08_prerequisite")
    _require(isinstance(prerequisite, dict), "P1-08 prerequisite must be an object")
    _require(prerequisite.get("decision_id") == "NEX-P1-08", "P1-08 prerequisite decision drift")
    _require(prerequisite.get("frozen") is True, "P1-08 prerequisite is not frozen")
    _require(prerequisite.get("freeze_commit_sha") == P1_08_FREEZE_COMMIT, "P1-08 freeze commit drift")
    _require(
        prerequisite.get("freeze_record_path") == "artifacts/p1-08/audit-observability-freeze.json", "P1-08 path drift"
    )
    _require(
        prerequisite.get("freeze_record_checksum")
        == canonical_checksum(_json(P1_08_FREEZE_PATH))
        == P1_08_FREEZE_CHECKSUM,
        "P1-08 freeze checksum mismatch",
    )

    _require(record.get("recorded_on") == "2026-10-27", "invalid freeze record date")
    _require(record.get("frozen") is True, "P1-09 is not frozen")
    _require(record.get("closed_gaps") == ["NEX-P1-GAP-005"], "frozen gap inventory drift")
    for key in (
        "production_readiness_claimed",
        "external_provider_smoke_claimed",
        "direct_trd_bot_database_access",
        "exactly_once_delivery_claimed",
        "public_internet_profile",
        "live_execution_capability",
        "exchange_credentials",
        "wallet_capability",
        "autonomous_ai_execution",
    ):
        _require(record.get(key) is False, f"freeze record cannot enable {key}")
    _require(record.get("next_allowed_stage") == "NEX-P1-10", "post-freeze stage drift")


def main() -> int:
    validate_frozen_p1_08()
    contract = load_contract()
    validate_contract(contract)
    validate_files_and_runtime_markers()
    validate_freeze_record(load_freeze_record(), contract)
    print(f"schema_version={contract['schema_version']}")
    print(f"decision_id={contract['decision_id']}")
    print(f"contract_checksum={canonical_checksum(contract)}")
    print("NEX_P1_08_PREREQUISITE=PASS")
    print("NEX_P1_09_TRD_BOT_SYNC_RUNTIME=PASS")
    print(f"candidate_commit_sha={CANDIDATE_SHA}")
    print("NEX_P1_09_FREEZE=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
