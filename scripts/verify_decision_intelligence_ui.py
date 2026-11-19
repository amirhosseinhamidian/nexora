#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "contracts/nexora-v0.1-decision-intelligence-ui.json"
PREREQUISITE_PATH = ROOT / "artifacts/p4-06/accounting-experience-ui-freeze.json"
PREREQUISITE_CHECKSUM = "5892cbd085c9f81f26a38b41e02d9a1c9a0ec852aad0fa433c3c77b008c6d67f"
CONTRACT_CHECKSUM = "95e952e82b3b493b7e5a866e41fc24e5ecb434d864dee3d583eb1b9151f582d7"


class DecisionIntelligenceUiContractError(ValueError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise DecisionIntelligenceUiContractError(message)


def load_contract(path: Path = CONTRACT_PATH) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    _require(isinstance(value, dict), f"{path.name} must contain an object")
    return value


def canonical_checksum(document: dict[str, Any]) -> str:
    encoded = json.dumps(document, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode()
    return hashlib.sha256(encoded).hexdigest()


def validate_prerequisite() -> None:
    record = load_contract(PREREQUISITE_PATH)
    _require(canonical_checksum(record) == PREREQUISITE_CHECKSUM, "P4-06 Freeze checksum drift")
    _require(record.get("frozen") is True, "P4-06 is not frozen")
    _require(record.get("next_allowed_stage") == "NEX-P4-07", "P4-07 is not open")


def validate_contract(contract: dict[str, Any]) -> None:
    _require(contract.get("schema_version") == "nexora-decision-intelligence-ui-v1", "schema drift")
    _require(contract.get("decision_id") == "NEX-P4-07" and contract.get("status") == "candidate", "decision drift")
    _require(
        contract.get("p4_06_prerequisite")
        == {
            "freeze_commit_sha": "3866c0b01b2a97f3987f86d5bec3f75e619d086b",
            "freeze_record_path": PREREQUISITE_PATH.relative_to(ROOT).as_posix(),
            "freeze_record_checksum": PREREQUISITE_CHECKSUM,
            "successful_ci_run_id": 44411490611,
        },
        "P4-06 prerequisite drift",
    )
    boundary = contract.get("boundary", {})
    _require(boundary.get("execution_authorization") is False, "the UI cannot grant execution authorization")
    _require(boundary.get("review_requires_confirmation") is True, "review confirmation is required")
    _require(
        contract.get("transition") == {"next_allowed_stage": "NEX-P4-07-FREEZE", "post_freeze_stage": "NEX-P4-08"},
        "stage transition drift",
    )
    _require(canonical_checksum(contract) == CONTRACT_CHECKSUM, "P4-07 contract checksum drift")


def validate_runtime_markers(contract: dict[str, Any]) -> None:
    api = load_contract(ROOT / "contracts/runtime/v1/openapi.json")["paths"]
    for method, key in (("get", "read_operations"), ("post", "write_operations")):
        for path, operation in contract[key].items():
            _require(api.get(path, {}).get(method, {}).get("operationId") == operation, f"operation drift: {path}")

    web = ROOT / "apps/web/src"
    components = web / "components"
    routes = web / "app/[locale]/(workspace)/decisions"
    client = web / "lib/decision-intelligence.ts"
    source = client.read_text(encoding="utf-8")
    panels = re.search(r"decisionPanels\s*=\s*\[([^\]]+)\]", source)
    _require(
        panels is not None
        and json.loads(f"[{panels.group(1).strip().removesuffix(',')}]") == contract["record_panels"],
        "decision section inventory drift",
    )
    _require(source.count('method: "POST"') == 1, "only a human review may write")
    for path, markers in (
        (routes / "page.tsx", ('section="decisions"',)),
        (
            routes / "[kind]/[resourceId]/[[...panel]]/page.tsx",
            ('kind !== "records"', 'kind !== "candidates"', "notFound()", 'section="decisionRecord"'),
        ),
        (
            client,
            ("response?.provider.generation", "Idempotency-Key", "/risk-gates/", "/portfolio-impacts/", "/reviews"),
        ),
        (components / "decision-record-workspace.tsx", ("aria-current=", "decisionHref", "controller.abort()")),
        (components / "decision-impact.tsx", ("<ComparisonBlock", "analysis.scenarios", "<ChartContainer", "<Table")),
        (
            components / "decision-review.tsx",
            (
                "<ConfirmationDialog",
                "<ToastRegion",
                "expected_version:",
                "source_evidence_checksum:",
                "supersedes_review_id:",
            ),
        ),
    ):
        content = path.read_text(encoding="utf-8")
        for marker in markers:
            _require(marker in content, f"P4-07 runtime marker missing from {path.name}: {marker}")

    review = (components / "decision-review.tsx").read_text(encoding="utf-8")
    reasons = set(re.findall(r'"(owner\.(?:accept|reject|defer)\.[a-z_]+)"', review))
    _require(bool(reasons), "review reasons are missing")
    for locale in contract["locales"]:
        copy = load_contract(ROOT / f"apps/web/messages/{locale}.json")["decisionPages"]
        _require(set(copy["panels"]) == set(contract["record_panels"]), f"{locale} page labels drift")
        _require(set(copy["reasons"]) == reasons, f"{locale} review reasons drift")


def main() -> int:
    contract = load_contract()
    validate_prerequisite()
    validate_contract(contract)
    validate_runtime_markers(contract)
    print(f"decision_id={contract['decision_id']}")
    print(f"contract_checksum={CONTRACT_CHECKSUM}")
    print("NEX_P4_06_PREREQUISITE=PASS")
    print("NEX_P4_07_DECISION_INTELLIGENCE_UI_CANDIDATE=PASS")
    print("NEX_P4_07_FREEZE=PENDING_SAME_SHA_CI")
    print("NEX_P4_08=BLOCKED_PENDING_P4_07_FREEZE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
