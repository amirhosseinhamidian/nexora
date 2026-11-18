#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "contracts/nexora-v0.1-platform-shell.json"
ROADMAP_PATH = ROOT / "contracts/nexora-v0.1-phase-four-product-experience-roadmap.json"
P4_01_FREEZE_PATH = ROOT / "artifacts/p4-01/ui-foundation-freeze.json"
FREEZE_PATH = ROOT / "artifacts/p4-02/platform-shell-freeze.json"
CONTRACT_CHECKSUM = "542ca782b3659c5d06fa3ddff97969a6e075721dd9f0ef84513f0a0951fdc822"
FREEZE_CHECKSUM = "bb5885b69dc6526ee22adde1f7ccdf0e1a882e4a6567d2cb380894a59317221d"
P4_02_CANDIDATE_SHA = "cd3dd588c830707860fa872e09f1ec122cc4eb03"
P4_01_FREEZE_CHECKSUM = "5c335ffbd731d9cea0df1e2cf1bfecfdf17b575531cb218f41b091a0ae22905d"
P4_01_FREEZE_SHA = "a89a4cbeab3a6b4846638ca47d2e5a051c6e16d7"
P4_01_FREEZE_CI_RUN_ID = 44319372484


class PlatformShellContractError(ValueError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise PlatformShellContractError(message)


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
    freeze = load_contract(P4_01_FREEZE_PATH)
    _require(canonical_checksum(freeze) == P4_01_FREEZE_CHECKSUM, "P4-01 Freeze checksum drift")
    _require(freeze.get("frozen") is True, "P4-01 is not frozen")
    _require(freeze.get("next_allowed_stage") == "NEX-P4-02", "P4-02 is not open")


def validate_contract(contract: dict[str, Any]) -> None:
    _require(contract.get("schema_version") == "nexora-platform-shell-v1", "schema drift")
    _require(contract.get("decision_id") == "NEX-P4-02", "decision drift")
    _require(contract.get("status") == "candidate", "status drift")
    _require(
        contract.get("p4_01_prerequisite")
        == {
            "freeze_commit_sha": P4_01_FREEZE_SHA,
            "freeze_record_path": P4_01_FREEZE_PATH.relative_to(ROOT).as_posix(),
            "freeze_record_checksum": P4_01_FREEZE_CHECKSUM,
            "successful_ci_run_id": P4_01_FREEZE_CI_RUN_ID,
        },
        "P4-01 prerequisite drift",
    )
    _require(contract.get("routes") == load_contract(ROADMAP_PATH)["target_routes"], "workspace route drift")
    _require(contract.get("locale_root_redirect") == "/{locale}/overview", "locale root redirect drift")
    _require(
        contract.get("public_entry_routes") == ["/{locale}/login", "/{locale}/bootstrap"],
        "public entry route drift",
    )
    _require(
        contract.get("navigation", {}).get("desktop_sidebar_edge") == {"fa": "right", "en": "left"},
        "desktop sidebar direction drift",
    )
    _require(
        contract.get("transition")
        == {
            "next_allowed_stage": "NEX-P4-02-FREEZE",
            "post_freeze_stage": "NEX-P4-03",
            "production_readiness_claimed": False,
        },
        "stage transition drift",
    )
    _require(canonical_checksum(contract) == CONTRACT_CHECKSUM, "P4-02 contract checksum drift")


def validate_freeze_record(record: dict[str, Any], contract: dict[str, Any]) -> None:
    _require(record.get("schema_version") == "nexora-platform-shell-freeze-v1", "invalid Freeze schema")
    _require(record.get("decision_id") == contract.get("decision_id") == "NEX-P4-02", "Freeze decision drift")
    _require(record.get("candidate_commit_sha") == P4_02_CANDIDATE_SHA, "P4-02 candidate SHA drift")
    _require(record.get("candidate_predecessor_sha") == P4_01_FREEZE_SHA, "P4-02 candidate predecessor drift")
    _require(record.get("p4_01_freeze_canonical_checksum") == P4_01_FREEZE_CHECKSUM, "P4-01 Freeze drift")
    _require(
        record.get("platform_shell_contract")
        == {"path": CONTRACT_PATH.relative_to(ROOT).as_posix(), "checksum": canonical_checksum(contract)},
        "Freeze contract evidence drift",
    )

    workflow = record.get("github_actions")
    _require(isinstance(workflow, dict), "GitHub Actions evidence must be an object")
    _require(workflow.get("head_sha") == P4_02_CANDIDATE_SHA, "CI head SHA drift")
    _require(workflow.get("conclusion") == "success", "CI did not succeed")
    jobs = workflow.get("jobs")
    _require(isinstance(jobs, dict), "CI jobs must be an object")
    _require(set(jobs) == {"platform-shell-contract", "platform-shell-web"}, "CI job inventory drift")
    for name, job in jobs.items():
        _require(isinstance(job, dict) and job.get("conclusion") == "success", f"CI job did not succeed: {name}")

    _require(record.get("frozen") is True, "P4-02 is not frozen")
    _require(record.get("next_allowed_stage") == contract["transition"]["post_freeze_stage"], "post-Freeze stage drift")
    _require(record.get("production_readiness_claimed") is False, "Freeze production claim")
    _require(canonical_checksum(record) == FREEZE_CHECKSUM, "P4-02 Freeze checksum drift")


def validate_runtime_markers(contract: dict[str, Any]) -> None:
    locale_root = ROOT / "apps/web/src/app/[locale]"
    workspace = locale_root / "(workspace)"
    layout = (workspace / "layout.tsx").read_text(encoding="utf-8")
    shell = (ROOT / "apps/web/src/components/authenticated-shell.tsx").read_text(encoding="utf-8")
    navigation = (ROOT / "apps/web/src/components/workspace-navigation.tsx").read_text(encoding="utf-8")
    _require("<AuthenticatedShell" in layout, "workspace layout must enforce session recovery")
    _require(
        "redirect(`/${locale}/overview`)" in (locale_root / "page.tsx").read_text(encoding="utf-8"),
        "locale root must redirect to Overview",
    )
    for route in contract["public_entry_routes"]:
        entry = route.removeprefix("/{locale}/")
        _require((locale_root / entry / "page.tsx").is_file(), f"public entry route missing: {entry}")
    for route in contract["routes"]:
        segment = route.removeprefix("/{locale}/")
        source = workspace / segment.replace("{portfolio_id}", "[portfolioId]") / "page.tsx"
        _require("<WorkspaceView" in source.read_text(encoding="utf-8"), f"workspace route missing: {route}")
        _require(f'segment: "{segment.split("/")[0]}"' in navigation, f"navigation missing: {route}")
    for marker in ("SESSION_EXPIRED_EVENT", '"/api/v1/auth/session"', "<Drawer", "<WorkspaceContext.Provider"):
        _require(marker in shell, f"workspace shell marker missing: {marker}")


def main() -> int:
    contract = load_contract()
    validate_prerequisite()
    validate_contract(contract)
    validate_runtime_markers(contract)
    validate_freeze_record(load_freeze_record(), contract)
    print(f"decision_id={contract['decision_id']}")
    print(f"contract_checksum={CONTRACT_CHECKSUM}")
    print("NEX_P4_02_PLATFORM_SHELL_CANDIDATE=PASS")
    print(f"candidate_commit_sha={P4_02_CANDIDATE_SHA}")
    print(f"freeze_checksum={FREEZE_CHECKSUM}")
    print("NEX_P4_02_FREEZE=PASS")
    print("NEX_P4_03=OPEN")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
