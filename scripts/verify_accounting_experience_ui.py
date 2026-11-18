#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "contracts/nexora-v0.1-accounting-experience-ui.json"
PREREQUISITE_PATH = ROOT / "artifacts/p4-05/portfolio-analytics-ui-freeze.json"
FREEZE_PATH = ROOT / "artifacts/p4-06/accounting-experience-ui-freeze.json"
CONTRACT_CHECKSUM = "4c147ce8ca92c788946d43348c14b0d82bb61dc80f24da59aa2a45b4d0b4cd14"
PREREQUISITE_CHECKSUM = "2ea7cb5dfda189daa7241a164005dd68d8e2f1f6a2056089239e6d61a0792c1f"
FREEZE_CHECKSUM = "5892cbd085c9f81f26a38b41e02d9a1c9a0ec852aad0fa433c3c77b008c6d67f"
CANDIDATE_SHA = "3f1e51f51ee4035288cf686885a28a7fa1d342ac"


class AccountingExperienceUiContractError(ValueError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AccountingExperienceUiContractError(message)


def load_contract(path: Path = CONTRACT_PATH) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    _require(isinstance(value, dict), f"{path.name} must contain an object")
    return value


def canonical_checksum(document: dict[str, Any]) -> str:
    payload = json.dumps(document, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()


def validate_prerequisite() -> None:
    record = load_contract(PREREQUISITE_PATH)
    _require(canonical_checksum(record) == PREREQUISITE_CHECKSUM, "P4-05 Freeze checksum drift")
    _require(record.get("frozen") is True, "P4-05 is not frozen")
    _require(record.get("next_allowed_stage") == "NEX-P4-06", "P4-06 is not open")


def validate_contract(contract: dict[str, Any]) -> None:
    _require(contract.get("schema_version") == "nexora-accounting-experience-ui-v1", "schema drift")
    _require(contract.get("decision_id") == "NEX-P4-06" and contract.get("status") == "candidate", "decision drift")
    _require(
        contract.get("p4_05_prerequisite")
        == {
            "freeze_commit_sha": "437a635077ef4d1e5d219f9b7cb1f42e3ce85618",
            "freeze_record_path": PREREQUISITE_PATH.relative_to(ROOT).as_posix(),
            "freeze_record_checksum": PREREQUISITE_CHECKSUM,
            "successful_ci_run_id": 44404355235,
        },
        "P4-05 prerequisite drift",
    )
    safety = contract.get("safety", {})
    _require(
        safety.get("recent_passkey_required") == ["publication", "reconciliation_decision"],
        "recent passkey requirements drift",
    )
    _require(
        safety.get("reconciliation_uses_expected_row_version") is True,
        "reconciliation must use the expected row version",
    )
    _require(
        contract.get("transition") == {"next_allowed_stage": "NEX-P4-06-FREEZE", "post_freeze_stage": "NEX-P4-07"},
        "stage transition drift",
    )
    _require(canonical_checksum(contract) == CONTRACT_CHECKSUM, "P4-06 contract checksum drift")


def validate_freeze_record(record: dict[str, Any], contract: dict[str, Any]) -> None:
    _require(record.get("schema_version") == "nexora-accounting-experience-ui-freeze-v1", "Freeze schema drift")
    _require(record.get("decision_id") == contract["decision_id"], "Freeze decision drift")
    _require(record.get("candidate_commit_sha") == CANDIDATE_SHA, "P4-06 candidate SHA drift")
    _require(
        record.get("candidate_predecessor_sha") == contract["p4_05_prerequisite"]["freeze_commit_sha"],
        "candidate is not based on the P4-05 Freeze",
    )
    _require(record.get("p4_05_freeze_canonical_checksum") == PREREQUISITE_CHECKSUM, "P4-05 Freeze drift")
    _require(
        record.get("accounting_experience_ui_contract")
        == {"path": CONTRACT_PATH.relative_to(ROOT).as_posix(), "checksum": canonical_checksum(contract)},
        "Freeze contract evidence drift",
    )

    workflow = record.get("github_actions")
    _require(isinstance(workflow, dict), "GitHub Actions evidence must be an object")
    _require(workflow.get("workflow_path") == ".github/workflows/accounting-experience-ui.yml", "CI workflow drift")
    _require(workflow.get("head_sha") == CANDIDATE_SHA, "CI head SHA drift")
    _require(workflow.get("event") == "push" and workflow.get("conclusion") == "success", "CI push did not succeed")
    jobs = workflow.get("jobs")
    _require(isinstance(jobs, dict), "CI jobs must be an object")
    _require(set(jobs) == {"accounting-experience-contract", "accounting-experience-web"}, "CI job inventory drift")
    for name, job in jobs.items():
        _require(isinstance(job, dict) and job.get("conclusion") == "success", f"CI job did not succeed: {name}")

    _require(record.get("frozen") is True, "P4-06 is not frozen")
    _require(record.get("next_allowed_stage") == contract["transition"]["post_freeze_stage"], "post-Freeze stage drift")
    _require(record.get("production_readiness_claimed") is False, "Freeze production claim")
    _require(canonical_checksum(record) == FREEZE_CHECKSUM, "P4-06 Freeze checksum drift")


def validate_runtime_markers(contract: dict[str, Any]) -> None:
    api = load_contract(ROOT / "contracts/runtime/v1/openapi.json")["paths"]
    for method, key in (("get", "read_operations"), ("post", "write_operations")):
        for path, operation in contract[key].items():
            _require(api.get(path, {}).get(method, {}).get("operationId") == operation, f"operation drift: {path}")

    web = ROOT / "apps/web/src"
    routes = web / "app/[locale]/(workspace)/transactions"
    components = web / "components"
    client = web / "lib/portfolio-accounting.ts"
    sections = re.search(r"accountingViews\s*=\s*\[([^\]]+)\]", client.read_text(encoding="utf-8"))
    _require(
        sections is not None
        and json.loads(f"[{sections.group(1).strip().removesuffix(',')}]") == list(contract["routes"]),
        "accounting view inventory drift",
    )
    for path, markers in (
        (routes / "page.tsx", ('view="journal"', "searchParams")),
        (routes / "[view]/page.tsx", ("accountingViews.find", "notFound()", 'section="transactions"')),
        (
            client,
            (
                'view === "journal" || view === "holdings" || view === "lots"',
                "maxImportBytes = 1_048_576",
                "expected_row_version: item.row_version",
                "signalSessionExpiry: false",
            ),
        ),
        (components / "transactions-workspace.tsx", ("<Link", "aria-current=", "window.history.replaceState")),
        (
            components / "accounting-imports.tsx",
            (
                "<Pagination",
                "await file.arrayBuffer()",
                "new TextEncoder().encode(payload).byteLength",
                "await onDryRun(",
            ),
        ),
        (components / "portfolio-operations.tsx", ("<ConfirmationDialog", "<ToastRegion", "onRefreshSession")),
        (
            components / "authenticated-shell.tsx",
            ("/auth/reauthentication/options", "/auth/reauthentication/complete", "verified.recently_reauthenticated"),
        ),
    ):
        source = path.read_text(encoding="utf-8")
        for marker in markers:
            _require(marker in source, f"P4-06 runtime marker missing from {path.name}: {marker}")

    for locale in ("en", "fa"):
        copy = load_contract(ROOT / f"apps/web/messages/{locale}.json")["portfolioOperations"]
        _require(set(contract["routes"]) <= copy["tabs"].keys(), f"{locale} accounting navigation copy drift")


def main() -> int:
    contract = load_contract()
    validate_prerequisite()
    validate_contract(contract)
    validate_runtime_markers(contract)
    validate_freeze_record(load_contract(FREEZE_PATH), contract)
    print(f"decision_id={contract['decision_id']}")
    print(f"contract_checksum={CONTRACT_CHECKSUM}")
    print("NEX_P4_05_PREREQUISITE=PASS")
    print("NEX_P4_06_ACCOUNTING_EXPERIENCE_UI_CANDIDATE=PASS")
    print(f"candidate_commit_sha={CANDIDATE_SHA}")
    print(f"freeze_checksum={FREEZE_CHECKSUM}")
    print("NEX_P4_06_FREEZE=PASS")
    print("NEX_P4_07=OPEN")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
