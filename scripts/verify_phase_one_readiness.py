#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "contracts/nexora-v0.1-phase-one-readiness.json"

EXPECTED_STAGE_STATUS = {
    "P1-01": "complete",
    "P1-02": "partial",
    "P1-03": "complete",
    "P1-04": "partial",
    "P1-05": "complete",
    "P1-06": "partial",
    "P1-07": "partial",
    "P1-08": "partial",
    "P1-09": "missing",
    "P1-10": "partial",
    "P1-11": "partial",
    "P1-12": "missing",
}
EXPECTED_GAP_OWNERS = {
    "NEX-P1-GAP-001": "NEX-P1-07",
    "NEX-P1-GAP-002": "NEX-P1-07",
    "NEX-P1-GAP-003": "NEX-P1-07",
    "NEX-P1-GAP-004": "NEX-P1-08",
    "NEX-P1-GAP-005": "NEX-P1-09",
    "NEX-P1-GAP-006": "NEX-P1-10",
    "NEX-P1-GAP-007": "NEX-P1-11",
    "NEX-P1-GAP-008": "NEX-P1-12",
    "NEX-P1-GAP-009": "NEX-P1-13",
}


class PhaseOneReadinessError(ValueError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise PhaseOneReadinessError(message)


def _json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    _require(isinstance(payload, dict), f"{path.name} must contain an object")
    return payload


def canonical_checksum(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def load_contract(path: Path = CONTRACT_PATH) -> dict[str, Any]:
    return _json(path)


def validate_frozen_p1_06() -> None:
    path = ROOT / "scripts/verify_single_owner_identity_runtime.py"
    spec = importlib.util.spec_from_file_location("verify_single_owner_identity_runtime", path)
    if spec is None or spec.loader is None:
        raise PhaseOneReadinessError("unable to load frozen P1-06 verifier")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.validate_frozen_durable_jobs()
    contract = module.load_contract()
    module.validate_contract(contract)
    module.validate_files()
    module.validate_documents()
    module.validate_freeze_record(module.load_freeze_record(), contract)


def validate_contract(contract: dict[str, Any]) -> None:
    _require(contract.get("schema_version") == "nexora-phase-one-readiness-v1", "invalid schema")
    _require(contract.get("decision_id") == "NEX-P1-ACCEPTANCE", "invalid decision ID")
    _require(contract.get("decision_date") == "2026-10-26", "invalid decision date")
    _require(contract.get("status") == "candidate", "readiness decision must remain candidate")

    prerequisite = contract.get("p1_06_prerequisite")
    _require(isinstance(prerequisite, dict), "P1-06 prerequisite must be an object")
    _require(prerequisite.get("decision_id") == "NEX-P1-06", "invalid P1-06 prerequisite")
    _require(prerequisite.get("frozen") is True, "P1-06 prerequisite is not frozen")
    _require(
        prerequisite.get("freeze_commit_sha") == "ce0c1504a520236fa7660749f13eabf475c82db9",
        "P1-06 freeze SHA drift",
    )
    freeze = _json(ROOT / prerequisite["freeze_record_path"])
    _require(canonical_checksum(freeze) == prerequisite.get("freeze_record_checksum"), "P1-06 checksum drift")

    assessment = contract.get("assessment")
    _require(isinstance(assessment, dict), "assessment must be an object")
    _require(assessment.get("original_roadmap_stage_count") == 12, "original roadmap size drift")
    _require(assessment.get("frozen_delivery_milestone_count") == 6, "frozen milestone count drift")
    for key in ("phase_one_ready", "production_readiness_claimed"):
        _require(assessment.get(key) is False, f"readiness assessment requires false: {key}")
    for key in ("final_acceptance_deferred", "roadmap_reconciliation_required"):
        _require(assessment.get(key) is True, f"readiness assessment requires true: {key}")

    matrix = contract.get("stage_matrix")
    _require(isinstance(matrix, list) and len(matrix) == 12, "stage matrix must contain twelve stages")
    _require([entry.get("stage") for entry in matrix] == list(EXPECTED_STAGE_STATUS), "stage matrix order drift")
    for entry in matrix:
        stage = entry.get("stage")
        _require(entry.get("status") == EXPECTED_STAGE_STATUS[stage], f"stage status drift: {stage}")
        _require(isinstance(entry.get("actual_delivery"), str), f"stage delivery missing: {stage}")

    gaps = contract.get("gaps")
    _require(isinstance(gaps, list) and len(gaps) == 9, "exactly nine blocking gaps are required")
    gap_ids = [gap.get("gap_id") for gap in gaps]
    _require(gap_ids == list(EXPECTED_GAP_OWNERS), "gap inventory or order drift")
    for gap in gaps:
        gap_id = gap["gap_id"]
        _require(gap.get("owner_stage") == EXPECTED_GAP_OWNERS[gap_id], f"gap owner drift: {gap_id}")
        _require(gap.get("blocking") is True, f"gap cannot become non-blocking: {gap_id}")
        _require(isinstance(gap.get("capability"), str), f"gap capability missing: {gap_id}")

    roadmap = contract.get("revised_roadmap")
    _require(isinstance(roadmap, list) and len(roadmap) == 7, "revised roadmap must contain seven stages")
    _require(
        [entry.get("stage") for entry in roadmap] == [f"NEX-P1-{number:02d}" for number in range(7, 14)],
        "revised roadmap order drift",
    )
    closed_gaps: list[str] = []
    for entry in roadmap:
        closes = entry.get("closes")
        _require(isinstance(closes, list) and closes, f"roadmap stage has no owned gaps: {entry.get('stage')}")
        for gap_id in closes:
            _require(EXPECTED_GAP_OWNERS.get(gap_id) == entry.get("stage"), f"roadmap gap owner mismatch: {gap_id}")
            closed_gaps.append(gap_id)
    _require(closed_gaps == list(EXPECTED_GAP_OWNERS), "revised roadmap does not cover every gap exactly once")

    security = contract.get("security_boundary")
    _require(isinstance(security, dict) and len(security) == 6, "security boundary inventory drift")
    for key, value in security.items():
        _require(value is False, f"forbidden capability enabled: {key}")

    transition = contract.get("transition")
    _require(isinstance(transition, dict), "transition must be an object")
    _require(transition.get("ready_for_freeze") is True, "reconciliation is not ready for freeze")
    _require(
        transition.get("next_allowed_stage") == "NEX-P1-ACCEPTANCE-FREEZE",
        "next stage must freeze the reconciliation decision",
    )
    _require(transition.get("post_freeze_stage") == "NEX-P1-07", "post-freeze stage drift")


def validate_files() -> None:
    required = (
        "contracts/nexora-v0.1-phase-one-readiness.json",
        "docs/v0.1/11-phase-one-roadmap-reconciliation.md",
        "scripts/verify_phase_one_readiness.py",
        "tests/test_phase_one_readiness.py",
        ".github/workflows/phase-one-readiness.yml",
    )
    for relative in required:
        _require((ROOT / relative).is_file(), f"missing readiness file: {relative}")


def validate_documents() -> None:
    document = (ROOT / "docs/v0.1/11-phase-one-roadmap-reconciliation.md").read_text(encoding="utf-8")
    for marker in (
        "NEX-P1-ACCEPTANCE",
        "پذیرش نهایی عمداً Deferred است",
        "ce0c1504a520236fa7660749f13eabf475c82db9",
        "phase_one_ready=false",
        "NEX-P1-07",
        "NEX-P1-13",
        "NEX-P1-ACCEPTANCE-FREEZE",
    ):
        _require(marker in document, f"readiness document marker missing: {marker}")


def main() -> int:
    validate_frozen_p1_06()
    contract = load_contract()
    validate_contract(contract)
    validate_files()
    validate_documents()
    print(f"schema_version={contract['schema_version']}")
    print(f"decision_id={contract['decision_id']}")
    print(f"contract_checksum={canonical_checksum(contract)}")
    print("phase_one_ready=false")
    print("final_acceptance_deferred=true")
    print("NEX_P1_06_PREREQUISITE=PASS")
    print("NEX_P1_ACCEPTANCE_RECONCILIATION=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
