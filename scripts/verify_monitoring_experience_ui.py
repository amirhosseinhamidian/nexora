#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "contracts/nexora-v0.1-monitoring-experience-ui.json"
PREREQUISITE_PATH = ROOT / "artifacts/p4-07/decision-intelligence-ui-freeze.json"
FREEZE_PATH = ROOT / "artifacts/p4-08/monitoring-experience-ui-freeze.json"
PREREQUISITE_CHECKSUM = "77d48a9e5ec278bcb6fe122993ddb90b0f517b1fee98be267fbad0c0d76618be"
CONTRACT_CHECKSUM = "6f4e10dc45962fd413654bece79c5c6be247b79f02a4ebd435e5967df3592f89"
FREEZE_CHECKSUM = "225a153858bfd377d9bd6f6691770d7e4eedb7be2e7634ea68ca9790a6b4ef92"
CANDIDATE_SHA = "c2f521bfaca55ec3abe013614ac7a1fadbff0b47"


class MonitoringExperienceUiContractError(ValueError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise MonitoringExperienceUiContractError(message)


def load_contract(path: Path = CONTRACT_PATH) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    _require(isinstance(value, dict), f"{path.name} must contain an object")
    return value


def canonical_checksum(document: dict[str, Any]) -> str:
    encoded = json.dumps(document, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode()
    return hashlib.sha256(encoded).hexdigest()


def validate_prerequisite() -> None:
    record = load_contract(PREREQUISITE_PATH)
    _require(canonical_checksum(record) == PREREQUISITE_CHECKSUM, "P4-07 Freeze checksum drift")
    _require(record.get("frozen") is True, "P4-07 is not frozen")
    _require(record.get("next_allowed_stage") == "NEX-P4-08", "P4-08 is not open")


def validate_contract(contract: dict[str, Any]) -> None:
    _require(contract.get("schema_version") == "nexora-monitoring-experience-ui-v1", "schema drift")
    _require(contract.get("decision_id") == "NEX-P4-08" and contract.get("status") == "candidate", "decision drift")
    _require(
        contract.get("p4_07_prerequisite")
        == {
            "freeze_commit_sha": "567fdc1f12b64ce5549e692a0c1082f1c5afe00f",
            "freeze_record_path": PREREQUISITE_PATH.relative_to(ROOT).as_posix(),
            "freeze_record_checksum": PREREQUISITE_CHECKSUM,
            "successful_ci_run_id": 44478313009,
        },
        "P4-07 prerequisite drift",
    )
    boundary = contract.get("boundary", {})
    _require(boundary.get("notification_delivery_enabled") is False, "external notification delivery is deferred")
    _require(boundary.get("journal_corrections_append_with_original_entry_id") is True, "correction lineage required")
    _require(
        contract.get("transition") == {"next_allowed_stage": "NEX-P4-08-FREEZE", "post_freeze_stage": "NEX-P4-09"},
        "stage transition drift",
    )
    _require(canonical_checksum(contract) == CONTRACT_CHECKSUM, "P4-08 contract checksum drift")


def validate_freeze_record(record: dict[str, Any], contract: dict[str, Any]) -> None:
    _require(record.get("schema_version") == "nexora-monitoring-experience-ui-freeze-v1", "Freeze schema drift")
    _require(record.get("decision_id") == contract["decision_id"], "Freeze decision drift")
    _require(record.get("candidate_commit_sha") == CANDIDATE_SHA, "P4-08 candidate SHA drift")
    _require(
        record.get("candidate_predecessor_sha") == contract["p4_07_prerequisite"]["freeze_commit_sha"],
        "candidate is not based on the P4-07 Freeze",
    )
    _require(record.get("p4_07_freeze_canonical_checksum") == PREREQUISITE_CHECKSUM, "P4-07 Freeze drift")
    _require(
        record.get("monitoring_experience_ui_contract")
        == {"path": CONTRACT_PATH.relative_to(ROOT).as_posix(), "checksum": canonical_checksum(contract)},
        "Freeze contract evidence drift",
    )

    workflow = record.get("github_actions")
    _require(isinstance(workflow, dict), "GitHub Actions evidence must be an object")
    _require(workflow.get("workflow_path") == ".github/workflows/monitoring-experience-ui.yml", "CI workflow drift")
    _require(workflow.get("head_sha") == CANDIDATE_SHA, "CI head SHA drift")
    _require(workflow.get("event") == "push" and workflow.get("conclusion") == "success", "CI push did not succeed")
    jobs = workflow.get("jobs")
    _require(isinstance(jobs, dict), "CI jobs must be an object")
    _require(set(jobs) == {"monitoring-experience-contract", "monitoring-experience-web"}, "CI job inventory drift")
    for name, job in jobs.items():
        _require(isinstance(job, dict) and job.get("conclusion") == "success", f"CI job did not succeed: {name}")

    _require(record.get("frozen") is True, "P4-08 is not frozen")
    _require(record.get("next_allowed_stage") == contract["transition"]["post_freeze_stage"], "post-Freeze stage drift")
    _require(record.get("production_readiness_claimed") is False, "Freeze production claim")
    _require(canonical_checksum(record) == FREEZE_CHECKSUM, "P4-08 Freeze checksum drift")


def validate_runtime_markers(contract: dict[str, Any]) -> None:
    api = load_contract(ROOT / "contracts/runtime/v1/openapi.json")["paths"]
    for method, key in (("get", "read_operations"), ("post", "write_operations")):
        for path, operation in contract[key].items():
            _require(api.get(path, {}).get(method, {}).get("operationId") == operation, f"operation drift: {path}")

    web = ROOT / "apps/web/src"
    components = web / "components"
    routes = web / "app/[locale]/(workspace)"
    for section, route in contract["routes"].items():
        path = routes / route.removeprefix("/{locale}/") / "page.tsx"
        source = path.read_text(encoding="utf-8")
        _require(f'section="{section}"' in source, f"monitoring route drift: {route}")
        for query in contract["route_context"][section]:
            _require(f"monitoringId({query})" in source, f"route context missing for {section}: {query}")

    for path, markers in (
        (
            web / "lib/monitoring.ts",
            (
                "visibleAlerts",
                *contract["alert_presentation"]["decision_reference_fields"],
                *contract["alert_presentation"]["preferences"],
            ),
        ),
        (components / "monitoring-navigation.tsx", ("aria-current=", "alertsHref", "watchlistsHref")),
        (
            components / "alert-inbox.tsx",
            (
                "<ConfirmationDialog",
                "expected_version:",
                "source_evidence_checksum:",
                "Idempotency-Key",
                "visibleAlerts",
            ),
        ),
        (
            components / "alert-record-card.tsx",
            ("alertDecisionId", "journalHref", ".toSorted((a, b) => b.state_version"),
        ),
        (
            components / "watchlist-panel.tsx",
            ("alertsHref", "initialWatchlistId", "expected_version:", "Idempotency-Key"),
        ),
        (components / "decision-record-workspace.tsx", ("journalHref(locale, record.decisionId)", "viewLinkedAlerts")),
        (
            components / "outcome-journal-panel.tsx",
            ("<ConfirmationDialog", "supersedes_entry_id:", "source_lineage:", "Idempotency-Key", "readOnly"),
        ),
    ):
        source = path.read_text(encoding="utf-8")
        for marker in markers:
            _require(marker in source, f"P4-08 runtime marker missing from {path.name}: {marker}")

    english = load_contract(ROOT / "apps/web/messages/en.json")["monitoring"]
    persian = load_contract(ROOT / "apps/web/messages/fa.json")["monitoring"]
    _require(bool(english) and english.keys() == persian.keys(), "monitoring translations drift")


def main() -> int:
    contract = load_contract()
    validate_prerequisite()
    validate_contract(contract)
    validate_runtime_markers(contract)
    validate_freeze_record(load_contract(FREEZE_PATH), contract)
    print(f"decision_id={contract['decision_id']}")
    print(f"contract_checksum={CONTRACT_CHECKSUM}")
    print("NEX_P4_07_PREREQUISITE=PASS")
    print("NEX_P4_08_MONITORING_EXPERIENCE_UI_CANDIDATE=PASS")
    print(f"candidate_commit_sha={CANDIDATE_SHA}")
    print(f"freeze_checksum={FREEZE_CHECKSUM}")
    print("NEX_P4_08_FREEZE=PASS")
    print("NEX_P4_09=OPEN")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
