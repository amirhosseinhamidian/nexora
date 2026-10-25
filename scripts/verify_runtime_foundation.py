#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import importlib.util
import json
import tomllib
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "contracts/nexora-v0.1-runtime-foundation.json"
FREEZE_PATH = ROOT / "artifacts/p1-01/runtime-foundation-freeze.json"


class RuntimeFoundationError(ValueError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeFoundationError(message)


def _json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    _require(isinstance(payload, dict), f"{path.name} must contain an object")
    return payload


def load_contract(path: Path = CONTRACT_PATH) -> dict[str, Any]:
    return _json(path)


def load_freeze_record(path: Path = FREEZE_PATH) -> dict[str, Any]:
    return _json(path)


def canonical_checksum(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def validate_frozen_phase_zero() -> None:
    path = ROOT / "scripts/verify_phase_zero_acceptance.py"
    spec = importlib.util.spec_from_file_location("verify_phase_zero_acceptance", path)
    if spec is None or spec.loader is None:
        raise RuntimeFoundationError("unable to load frozen P0-05 verifier")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.validate_frozen_security_boundary()
    contract = module.load_contract()
    matrix = module.load_matrix()
    module.validate_contract(contract)
    module.validate_matrix(matrix, contract)
    module.validate_documents()
    module.validate_freeze_record(module.load_freeze_record(), contract, matrix)


def validate_contract(contract: dict[str, Any]) -> None:
    _require(contract.get("schema_version") == "nexora-runtime-foundation-v1", "invalid schema")
    _require(contract.get("decision_id") == "NEX-P1-01", "invalid decision ID")
    _require(contract.get("status") == "candidate", "P1-01 must remain candidate")
    prerequisite = contract.get("phase_zero_prerequisite", {})
    _require(prerequisite.get("frozen") is True, "Phase 0 prerequisite is not frozen")
    _require(prerequisite.get("runtime_bootstrap_authorized") is True, "runtime bootstrap is not authorized")
    freeze = _json(ROOT / prerequisite["freeze_record_path"])
    _require(canonical_checksum(freeze) == prerequisite.get("freeze_record_checksum"), "Phase 0 checksum drift")

    delivery = contract.get("delivery", {})
    _require(delivery.get("runtime_scaffold_delivered") is True, "runtime scaffold is missing")
    for key in (
        "production_readiness_claimed",
        "database_runtime_delivered",
        "authentication_runtime_delivered",
        "trd_bot_runtime_integration_delivered",
        "durable_worker_delivered",
    ):
        _require(delivery.get(key) is False, f"P1-01 cannot claim {key}")

    _require(
        contract.get("toolchain")
        == {
            "python": "3.13.16",
            "uv": "0.13.4",
            "node": "24.22.1",
            "pnpm": "10.34.8",
        },
        "toolchain drift",
    )
    web = contract.get("web_runtime", {})
    _require(web.get("static_locales") == ["fa", "en"], "locale inventory drift")
    _require(web.get("default_locale") == "fa", "Persian must be default")
    design = contract.get("design_foundation", {})
    _require(design.get("themes") == ["light", "dark", "system"], "theme inventory drift")
    _require(design["locales"]["fa"]["direction"] == "rtl", "Persian must be RTL")
    _require(design["locales"]["en"]["direction"] == "ltr", "English must be LTR")
    _require(design.get("reduced_motion_supported") is True, "reduced motion is required")
    _require(design.get("visible_keyboard_focus") is True, "keyboard focus is required")
    security = contract.get("security_boundary", {})
    for key, value in security.items():
        _require(value is False, f"forbidden capability enabled: {key}")
    _require(len(security) == 7, "security inventory drift")
    debt = contract.get("resolved_debt", {})
    _require(debt.get("id") == "NEX-DEBT-P0-02-001" and debt.get("closed") is True, "dependency debt is open")
    transition = contract.get("transition", {})
    _require(transition.get("next_allowed_stage") == "NEX-P1-01-FREEZE", "next stage must be freeze")
    _require(transition.get("post_freeze_stage") == "NEX-P1-02", "post-freeze stage drift")


def _leaf_paths(payload: Any, prefix: str = "") -> set[str]:
    if not isinstance(payload, dict):
        return {prefix}
    result: set[str] = set()
    for key, value in payload.items():
        path = f"{prefix}.{key}" if prefix else key
        result.update(_leaf_paths(value, path))
    return result


def validate_files(contract: dict[str, Any]) -> None:
    required = [
        "uv.lock",
        "pnpm-lock.yaml",
        "apps/server/src/nexora/api.py",
        "apps/server/src/nexora/worker.py",
        "apps/web/src/app/[locale]/layout.tsx",
        "apps/web/src/app/[locale]/page.tsx",
        "packages/ui/src/tokens.css",
        ".github/workflows/runtime-foundation.yml",
    ]
    for relative in required:
        _require((ROOT / relative).is_file(), f"missing runtime file: {relative}")

    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    _require(pyproject["project"]["requires-python"] == ">=3.13,<3.14", "Python range drift")
    for requirement in pyproject["project"]["dependencies"] + pyproject["dependency-groups"]["dev"]:
        _require("==" in requirement, f"non-exact Python dependency: {requirement}")
    root_package = _json(ROOT / "package.json")
    _require(root_package["packageManager"] == "pnpm@10.34.8", "pnpm pin drift")
    web_package = _json(ROOT / "apps/web/package.json")
    for version in [*web_package["dependencies"].values(), *web_package["devDependencies"].values()]:
        _require(
            version == "workspace:*" or not version.startswith(("^", "~", ">", "<")),
            "web dependency is not exact",
        )

    fa = contract["design_foundation"]["locales"]["fa"]
    font_path = ROOT / fa["font_path"]
    _require(font_path.is_file(), "Vazirmatn font is missing")
    _require(hashlib.sha256(font_path.read_bytes()).hexdigest() == fa["font_sha256"], "Vazirmatn checksum drift")
    fa_catalog = _json(ROOT / "apps/web/messages/fa.json")
    en_catalog = _json(ROOT / "apps/web/messages/en.json")
    _require(_leaf_paths(fa_catalog) == _leaf_paths(en_catalog), "translation catalog keys do not match")

    locale = (ROOT / "apps/web/src/i18n/config.ts").read_text(encoding="utf-8")
    _require('defaultLocale: Locale = "fa"' in locale, "default locale marker missing")
    layout = (ROOT / "apps/web/src/app/[locale]/layout.tsx").read_text(encoding="utf-8")
    for marker in ("next/font/local", "Vazirmatn-Variable.ttf", "directionFor(locale)"):
        _require(marker in layout, f"layout marker missing: {marker}")
    tokens = (ROOT / "packages/ui/src/tokens.css").read_text(encoding="utf-8")
    for marker in (":root", '[data-theme="dark"]', ":focus-visible", "prefers-reduced-motion"):
        _require(marker in tokens, f"token marker missing: {marker}")
    api = (ROOT / "apps/server/src/nexora/api.py").read_text(encoding="utf-8")
    for marker in ("docs_url=None", "redoc_url=None", '"/health/live"'):
        _require(marker in api, f"API marker missing: {marker}")
    worker = (ROOT / "apps/server/src/nexora/worker.py").read_text(encoding="utf-8")
    _require("worker execution is unavailable until NEX-P1-05" in worker, "worker fail-closed marker missing")


def validate_freeze_record(record: dict[str, Any], contract: dict[str, Any]) -> None:
    _require(
        record.get("schema_version") == "nexora-runtime-foundation-freeze-v1",
        "invalid runtime foundation freeze schema",
    )
    _require(record.get("decision_id") == "NEX-P1-01", "invalid freeze decision ID")
    _require(record.get("repository") == "amirhosseinhamidian/nexora", "invalid repository")
    _require(
        record.get("candidate_commit_sha") == "611557dd95241d7c45513772601e58bc055f398f",
        "candidate SHA does not match accepted P1-01 evidence",
    )
    _require(
        record.get("candidate_commit_message")
        == "feat(nexora): bootstrap P1-01 runtime and design foundation",
        "candidate commit message does not match accepted evidence",
    )

    actions = record.get("github_actions")
    _require(isinstance(actions, dict), "github_actions must be an object")
    _require(actions.get("run_id") == 40182361689, "invalid GitHub Actions run ID")
    _require(
        actions.get("run_url")
        == "https://github.com/amirhosseinhamidian/nexora/actions/runs/40182361689",
        "GitHub Actions URL does not match the accepted run",
    )
    _require(actions.get("head_branch") == "feature/v0.1-foundation", "invalid GitHub Actions branch")
    _require(actions.get("event") == "push", "invalid GitHub Actions event")
    _require(actions.get("attempt") == 1, "invalid GitHub Actions attempt")
    _require(actions.get("conclusion") == "success", "workflow was not successful")

    jobs = actions.get("jobs")
    _require(isinstance(jobs, dict), "GitHub Actions jobs must be an object")
    expected_jobs = {
        "foundation_contract": (121135890629, "foundation-contract"),
        "backend": (121135890830, "backend"),
        "web": (121135890759, "web"),
    }
    _require(set(jobs) == set(expected_jobs), "freeze requires all three P1-01 CI jobs")
    for key, (job_id, name) in expected_jobs.items():
        job = jobs.get(key)
        _require(isinstance(job, dict), f"{name} evidence must be an object")
        _require(job.get("job_id") == job_id, f"invalid {name} job ID")
        _require(job.get("name") == name, f"invalid {name} job name")
        _require(job.get("conclusion") == "success", f"{name} job was not successful")

    required_markers = {
        "foundation_contract": (
            "phase_zero_prerequisite_passed",
            "runtime_foundation_verifier_passed",
            "repository_contract_tests_passed",
        ),
        "backend": (
            "locked_dependencies_installed",
            "format_passed",
            "lint_passed",
            "typecheck_passed",
            "tests_passed",
        ),
        "web": (
            "locked_dependencies_installed",
            "format_passed",
            "lint_passed",
            "typecheck_passed",
            "tests_passed",
            "production_build_passed",
        ),
    }
    for job_name, markers in required_markers.items():
        for marker in markers:
            _require(jobs[job_name].get(marker) is True, f"{job_name} did not confirm {marker}")

    contract_evidence = record.get("runtime_foundation_contract")
    _require(isinstance(contract_evidence, dict), "runtime foundation evidence must be an object")
    _require(
        contract_evidence.get("schema_version") == contract.get("schema_version"),
        "runtime foundation schema mismatch",
    )
    _require(
        contract_evidence.get("checksum") == canonical_checksum(contract),
        "runtime foundation contract checksum mismatch",
    )

    phase_zero = record.get("phase_zero_prerequisite")
    _require(isinstance(phase_zero, dict), "Phase 0 prerequisite must be an object")
    _require(phase_zero.get("decision_id") == "NEX-P0-05", "invalid Phase 0 prerequisite")
    _require(phase_zero.get("frozen") is True, "Phase 0 prerequisite is not frozen")
    phase_zero_record = _json(ROOT / "artifacts/p0-05/phase-zero-freeze.json")
    _require(
        phase_zero.get("freeze_record_checksum") == canonical_checksum(phase_zero_record),
        "Phase 0 freeze record checksum mismatch",
    )

    _require(record.get("recorded_on") == "2026-10-25", "invalid freeze record date")
    _require(record.get("frozen") is True, "runtime foundation is not frozen")
    _require(record.get("runtime_foundation_complete") is True, "runtime foundation completion is not confirmed")
    _require(record.get("next_allowed_stage") == "NEX-P1-02", "invalid post-freeze next stage")


def validate_documents() -> None:
    document = (ROOT / "docs/v0.1/05-runtime-and-design-foundation-bootstrap.md").read_text(encoding="utf-8")
    for marker in (
        "NEX-P1-01",
        "وضعیت: **Frozen**",
        "Vazirmatn",
        "NEX_P1_01_RUNTIME_FOUNDATION=PASS",
        "NEX_P1_01_FREEZE=PASS",
        "611557dd95241d7c45513772601e58bc055f398f",
        "40182361689",
        "NEX-P1-02",
    ):
        _require(marker in document, f"document marker missing: {marker}")
    workflow = (ROOT / ".github/workflows/runtime-foundation.yml").read_text(encoding="utf-8")
    for marker in ("foundation-contract:", "backend:", "web:", "verify_runtime_foundation.py"):
        _require(marker in workflow, f"workflow marker missing: {marker}")


def main() -> int:
    validate_frozen_phase_zero()
    contract = load_contract()
    validate_contract(contract)
    validate_files(contract)
    validate_documents()
    freeze_record = load_freeze_record()
    validate_freeze_record(freeze_record, contract)
    print(f"schema_version={contract['schema_version']}")
    print(f"decision_id={contract['decision_id']}")
    print(f"contract_checksum={canonical_checksum(contract)}")
    print(f"candidate_commit_sha={freeze_record['candidate_commit_sha']}")
    print("NEX_P0_05_PREREQUISITE=PASS")
    print("NEX_P1_01_RUNTIME_FOUNDATION=PASS")
    print("NEX_P1_01_FREEZE=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
