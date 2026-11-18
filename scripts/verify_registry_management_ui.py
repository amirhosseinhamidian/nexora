#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "contracts/nexora-v0.1-registry-management-ui.json"
P4_03_FREEZE_PATH = ROOT / "artifacts/p4-03/first-run-onboarding-freeze.json"
FREEZE_PATH = ROOT / "artifacts/p4-04/registry-management-ui-freeze.json"
CONTRACT_CHECKSUM = "d4dfa5b51e293aaf23c82c120be1054282bfbff0afbe30bb0f8d48e4282fb848"
FREEZE_CHECKSUM = "fde080e0d1ac0a260ad1214340c46fee9c9fd7f9453122e485ce36d662394ef9"
P4_03_FREEZE_CHECKSUM = "c2bda9d47b9e6d69eacd268b5449fa77e70cefc8ef8f62647db48fd3b55078bf"
P4_03_FREEZE_SHA = "5742c742c2b713cd54590bffe0c630de01969dc7"
P4_03_FREEZE_CI_RUN_ID = 44389551521
P4_04_CANDIDATE_SHA = "3414507938c41acad1ab66b12f649c22f58e13ce"


class RegistryManagementUiContractError(ValueError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise RegistryManagementUiContractError(message)


def load_contract(path: Path = CONTRACT_PATH) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    _require(isinstance(value, dict), f"{path.name} must contain an object")
    return value


def canonical_checksum(document: dict[str, Any]) -> str:
    payload = json.dumps(document, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()


def load_freeze_record(path: Path = FREEZE_PATH) -> dict[str, Any]:
    return load_contract(path)


def validate_prerequisite() -> None:
    freeze = load_contract(P4_03_FREEZE_PATH)
    _require(canonical_checksum(freeze) == P4_03_FREEZE_CHECKSUM, "P4-03 Freeze checksum drift")
    _require(freeze.get("frozen") is True, "P4-03 is not frozen")
    _require(freeze.get("next_allowed_stage") == "NEX-P4-04", "P4-04 is not open")


def validate_contract(contract: dict[str, Any]) -> None:
    _require(contract.get("schema_version") == "nexora-registry-management-ui-v1", "schema drift")
    _require(contract.get("decision_id") == "NEX-P4-04", "decision drift")
    _require(contract.get("status") == "candidate", "status drift")
    _require(
        contract.get("p4_03_prerequisite")
        == {
            "freeze_commit_sha": P4_03_FREEZE_SHA,
            "freeze_record_path": P4_03_FREEZE_PATH.relative_to(ROOT).as_posix(),
            "freeze_record_checksum": P4_03_FREEZE_CHECKSUM,
            "successful_ci_run_id": P4_03_FREEZE_CI_RUN_ID,
        },
        "P4-03 prerequisite drift",
    )
    _require(
        contract.get("lifecycle")
        == {
            "confirmation_required": True,
            "requires_expected_row_version": True,
            "refresh_after_conflict": True,
            "history_retained": True,
        },
        "lifecycle safeguards drift",
    )
    _require(
        contract.get("boundary", {}).get("rename_or_general_update") is False,
        "rename and general updates require a separate contract",
    )
    _require(
        contract.get("transition") == {"next_allowed_stage": "NEX-P4-04-FREEZE", "post_freeze_stage": "NEX-P4-05"},
        "stage transition drift",
    )
    _require(canonical_checksum(contract) == CONTRACT_CHECKSUM, "P4-04 contract checksum drift")


def validate_freeze_record(record: dict[str, Any], contract: dict[str, Any]) -> None:
    _require(record.get("schema_version") == "nexora-registry-management-ui-freeze-v1", "invalid Freeze schema")
    _require(record.get("decision_id") == contract.get("decision_id") == "NEX-P4-04", "Freeze decision drift")
    _require(record.get("candidate_commit_sha") == P4_04_CANDIDATE_SHA, "P4-04 candidate SHA drift")
    _require(record.get("candidate_predecessor_sha") == P4_03_FREEZE_SHA, "candidate is not based on the P4-03 Freeze")
    _require(record.get("p4_03_freeze_canonical_checksum") == P4_03_FREEZE_CHECKSUM, "P4-03 Freeze drift")
    _require(
        record.get("registry_management_ui_contract")
        == {"path": CONTRACT_PATH.relative_to(ROOT).as_posix(), "checksum": canonical_checksum(contract)},
        "Freeze contract evidence drift",
    )

    workflow = record.get("github_actions")
    _require(isinstance(workflow, dict), "GitHub Actions evidence must be an object")
    _require(workflow.get("workflow_path") == ".github/workflows/registry-management-ui.yml", "CI workflow drift")
    _require(workflow.get("head_sha") == P4_04_CANDIDATE_SHA, "CI head SHA drift")
    _require(workflow.get("conclusion") == "success", "CI did not succeed")
    jobs = workflow.get("jobs")
    _require(isinstance(jobs, dict), "CI jobs must be an object")
    _require(set(jobs) == {"registry-management-contract", "registry-management-web"}, "CI job inventory drift")
    for name, job in jobs.items():
        _require(isinstance(job, dict) and job.get("conclusion") == "success", f"CI job did not succeed: {name}")

    _require(record.get("frozen") is True, "P4-04 is not frozen")
    _require(record.get("next_allowed_stage") == contract["transition"]["post_freeze_stage"], "post-Freeze stage drift")
    _require(record.get("production_readiness_claimed") is False, "Freeze production claim")
    _require(canonical_checksum(record) == FREEZE_CHECKSUM, "P4-04 Freeze checksum drift")


def validate_runtime_markers(contract: dict[str, Any]) -> None:
    web = ROOT / "apps/web/src"
    navigation = (web / "components/workspace-navigation.tsx").read_text(encoding="utf-8")
    workspace = (web / "components/workspace-view.tsx").read_text(encoding="utf-8")
    registry = (web / "lib/portfolio-registry.ts").read_text(encoding="utf-8")
    management = (web / "components/registry-management.tsx").read_text(encoding="utf-8")
    api = load_contract(ROOT / "contracts/runtime/v1/openapi.json")["paths"]

    for route in contract["routes"]:
        segment = route.removeprefix("/{locale}/")
        source = web / f"app/[locale]/(workspace)/{segment}/page.tsx"
        _require(f'section="{segment}"' in source.read_text(encoding="utf-8"), f"registry route drift: {route}")
        _require(f'segment: "{segment}"' in navigation, f"registry navigation missing: {route}")
    _require("<RegistryManagement" in workspace, "registry pages are not composed in the owner workspace")
    for path, methods in contract["registry_operations"].items():
        _require(
            all(
                api.get(path, {}).get(method, {}).get("operationId") == operation
                for method, operation in methods.items()
            ),
            f"registry API operation drift: {path}",
        )
    for marker in ('"deactivate"', '"archive"', '"close"', "/identifiers", "expected_row_version: record.row_version"):
        _require(marker in registry, f"registry write marker missing: {marker}")
    for marker in ("<ConfirmationDialog", "changeRegistryLifecycle", "statusCode === 409", "refresh()", "/onboarding"):
        _require(marker in management, f"registry interface marker missing: {marker}")


def main() -> int:
    contract = load_contract()
    validate_prerequisite()
    validate_contract(contract)
    validate_runtime_markers(contract)
    validate_freeze_record(load_freeze_record(), contract)
    print(f"decision_id={contract['decision_id']}")
    print(f"contract_checksum={CONTRACT_CHECKSUM}")
    print("NEX_P4_03_PREREQUISITE=PASS")
    print("NEX_P4_04_REGISTRY_MANAGEMENT_UI_CANDIDATE=PASS")
    print(f"candidate_commit_sha={P4_04_CANDIDATE_SHA}")
    print(f"freeze_checksum={FREEZE_CHECKSUM}")
    print("NEX_P4_04_FREEZE=PASS")
    print("NEX_P4_05=OPEN")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
