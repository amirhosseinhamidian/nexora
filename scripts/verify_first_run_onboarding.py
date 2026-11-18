#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "contracts/nexora-v0.1-first-run-onboarding.json"
FREEZE_PATH = ROOT / "artifacts/p4-02/platform-shell-freeze.json"
CONTRACT_CHECKSUM = "b32b6772259881401160ce5e436453c1a149dff61c4afccb8bc72f15b597f597"
P4_02_FREEZE_CHECKSUM = "bb5885b69dc6526ee22adde1f7ccdf0e1a882e4a6567d2cb380894a59317221d"
P4_02_FREEZE_SHA = "077e2abde51367235bd425421ac1f24f2f7ed142"
P4_02_FREEZE_CI_RUN_ID = 44324072191


class FirstRunOnboardingContractError(ValueError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise FirstRunOnboardingContractError(message)


def load_contract(path: Path = CONTRACT_PATH) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    _require(isinstance(value, dict), f"{path.name} must contain an object")
    return value


def canonical_checksum(document: dict[str, Any]) -> str:
    payload = json.dumps(document, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()


def validate_prerequisite() -> None:
    freeze = load_contract(FREEZE_PATH)
    _require(canonical_checksum(freeze) == P4_02_FREEZE_CHECKSUM, "P4-02 Freeze checksum drift")
    _require(freeze.get("frozen") is True, "P4-02 is not frozen")
    _require(freeze.get("next_allowed_stage") == "NEX-P4-03", "P4-03 is not open")


def validate_contract(contract: dict[str, Any]) -> None:
    _require(contract.get("schema_version") == "nexora-first-run-onboarding-v1", "schema drift")
    _require(contract.get("decision_id") == "NEX-P4-03", "decision drift")
    _require(contract.get("status") == "candidate", "status drift")
    _require(
        contract.get("p4_02_prerequisite")
        == {
            "freeze_commit_sha": P4_02_FREEZE_SHA,
            "freeze_record_path": FREEZE_PATH.relative_to(ROOT).as_posix(),
            "freeze_record_checksum": P4_02_FREEZE_CHECKSUM,
            "successful_ci_run_id": P4_02_FREEZE_CI_RUN_ID,
        },
        "P4-02 prerequisite drift",
    )
    _require(contract.get("steps") == ["base_asset", "portfolio", "optional_account", "review"], "setup step drift")
    _require(contract.get("confirmation_required_before_writes") is True, "confirmation required before writes")
    _require(
        contract.get("transition") == {"next_allowed_stage": "NEX-P4-03-FREEZE", "post_freeze_stage": "NEX-P4-04"},
        "stage transition drift",
    )
    _require(canonical_checksum(contract) == CONTRACT_CHECKSUM, "P4-03 contract checksum drift")


def validate_runtime_markers(contract: dict[str, Any]) -> None:
    web = ROOT / "apps/web/src"
    route = web / "app/[locale]/(workspace)/onboarding/page.tsx"
    source = (web / "lib/first-run-onboarding.ts").read_text(encoding="utf-8")
    ui = (web / "components/first-run-onboarding.tsx").read_text(encoding="utf-8")
    session = (web / "components/authenticated-shell.tsx").read_text(encoding="utf-8")
    api = load_contract(ROOT / "contracts/runtime/v1/openapi.json")["paths"]
    _require('section="onboarding"' in route.read_text(encoding="utf-8"), "authenticated route drift")
    _require("<ConfirmationDialog" in ui, "setup confirmation missing")
    _require("resume=onboarding" in session, "session recovery link missing")
    for marker in ("sessionStorage", "createOrRecover", "signal.throwIfAborted()", "canResumePortfolio"):
        _require(marker in source, f"setup recovery marker missing: {marker}")
    for endpoint in contract["registry_endpoints"]:
        methods = api.get(endpoint.removeprefix("/api"), {})
        _require(endpoint in source and {"get", "post"}.issubset(methods), f"setup endpoint drift: {endpoint}")
    _require("external_reference" not in source, "onboarding collects an external account reference")


def main() -> int:
    contract = load_contract()
    validate_prerequisite()
    validate_contract(contract)
    validate_runtime_markers(contract)
    print(f"decision_id={contract['decision_id']}")
    print(f"contract_checksum={CONTRACT_CHECKSUM}")
    print("NEX_P4_03_FIRST_RUN_ONBOARDING_CANDIDATE=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
