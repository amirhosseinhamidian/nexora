#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from datetime import UTC, datetime
from itertools import product
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "contracts/nexora-v0.1-phase-four-product-acceptance.json"
CONTRACT_CHECKSUM = "436c29ae20c4d24069d4b86b94ccfce42da3bfc2af4da2451ad086875b330637"
E2E_ROOT = ROOT / "apps/web/tests/e2e"
MANUAL_SCHEMA = "nexora-phase-four-manual-visual-evidence-v1"
BROWSER_SCHEMA = "nexora-phase-four-browser-evidence-v1"


class ProductAcceptanceError(ValueError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ProductAcceptanceError(message)


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ProductAcceptanceError(f"{path.name} must contain an object")
    return value


def checksum(value: object) -> str:
    encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode()
    return hashlib.sha256(encoded).hexdigest()


def load_contract() -> dict[str, Any]:
    contract = load_json(CONTRACT_PATH)
    require(checksum(contract) == CONTRACT_CHECKSUM, "P4-11 contract checksum drift")
    return contract


def validate_prerequisite(contract: dict[str, Any]) -> None:
    prerequisite = contract["p4_10_prerequisite"]
    record = load_json(ROOT / prerequisite["freeze_record_path"])
    require(checksum(record) == prerequisite["freeze_record_checksum"], "P4-10 Freeze checksum drift")
    require(record.get("frozen") is True, "P4-10 is not frozen")
    require(record.get("next_allowed_stage") == contract["decision_id"], "P4-11 is not open")


def validate_repository(contract: dict[str, Any]) -> None:
    workflow = (ROOT / contract["browser"]["workflow_path"]).read_text(encoding="utf-8")
    for marker in ("--reporter=line,json", "browser-evidence", contract["browser"]["artifact_name"]):
        require(marker in workflow, f"CI evidence step missing: {marker}")
    for scenario in contract["browser"]["scenarios"].values():
        path = E2E_ROOT / scenario["file"]
        require(f'"{scenario["title"]}"' in path.read_text(encoding="utf-8"), f"missing test: {scenario['title']}")


def _git(*args: str) -> str:
    return subprocess.check_output(("git", "--no-optional-locks", *args), cwd=ROOT, text=True).strip()


def candidate_identity(contract: dict[str, Any]) -> dict[str, str]:
    candidate, tree = _git("show", "-s", "--format=%H%n%T", "HEAD").splitlines()
    predecessor = contract["p4_10_prerequisite"]["freeze_commit_sha"]
    require(candidate != predecessor, "commit the P4-11 candidate before capturing evidence")
    require(not _git("status", "--porcelain"), "capture evidence from a clean candidate checkout")
    try:
        _git("merge-base", "--is-ancestor", predecessor, candidate)
    except subprocess.CalledProcessError as error:
        raise ProductAcceptanceError("the candidate must descend from the P4-10 Freeze") from error
    return {"candidate_commit_sha": candidate, "candidate_tree_sha": tree}


def _visual_profiles(contract: dict[str, Any]) -> list[tuple[str, str, int]]:
    manual = contract["manual_visual"]
    return list(product(manual["locales"], manual["themes"], manual["viewport_widths_px"]))


def manual_template(contract: dict[str, Any], identity: dict[str, str]) -> dict[str, Any]:
    return {
        "schema_version": MANUAL_SCHEMA,
        "contract_checksum": CONTRACT_CHECKSUM,
        **identity,
        "reviewer_role": contract["manual_visual"]["reviewer"],
        "created_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "results": [
            {"locale": locale, "theme": theme, "width_px": width, "result": "pending"}
            for locale, theme, width in _visual_profiles(contract)
        ],
    }


def validate_manual(record: dict[str, Any], contract: dict[str, Any], identity: dict[str, str]) -> None:
    require(record.get("schema_version") == MANUAL_SCHEMA, "manual evidence schema drift")
    require(record.get("contract_checksum") == CONTRACT_CHECKSUM, "manual evidence contract checksum drift")
    for key, value in identity.items():
        require(record.get(key) == value, f"manual evidence {key} does not match the candidate")
    require(record.get("reviewer_role") == contract["manual_visual"]["reviewer"], "manual owner review is required")
    results = record.get("results")
    require(isinstance(results, list) and all(isinstance(row, dict) for row in results), "manual results are invalid")
    expected = _visual_profiles(contract)
    profiles = [(row.get("locale"), row.get("theme"), row.get("width_px")) for row in results]
    require(
        len(profiles) == len(expected) and set(profiles) == set(expected),
        "manual review must include each required profile exactly once",
    )
    missing = [f"{row['locale']}/{row['theme']}/{row['width_px']}px" for row in results if row.get("result") != "pass"]
    require(not missing, "manual profiles awaiting a pass: " + ", ".join(missing))


def _collect_specs(suite: dict[str, Any], specs: dict[tuple[str, str], list[dict[str, Any]]]) -> None:
    for spec in suite.get("specs", []):
        key = (Path(spec["file"]).name, spec["title"])
        specs.setdefault(key, []).extend(spec["tests"])
    for child in suite.get("suites", []):
        _collect_specs(child, specs)


def browser_results(contract: dict[str, Any], report: dict[str, Any]) -> dict[str, Any]:
    require(report.get("errors") == [], "Playwright reported run-level errors")
    require(report["stats"].get("unexpected") == 0, "Playwright has failed cases")
    specs: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for suite in report["suites"]:
        _collect_specs(suite, specs)

    def require_passed(file: str, title: str) -> None:
        cases = specs.get((file, title), [])
        require(len(cases) == 1, f"expected exactly one Playwright result for {file}: {title}")
        case = cases[0]
        require(
            case.get("status") == "expected"
            and case.get("expectedStatus") == "passed"
            and [result.get("status") for result in case.get("results", [])] == ["passed"],
            f"required browser case did not pass: {title}",
        )

    journeys = {}
    for key, scenario in contract["browser"]["scenarios"].items():
        require_passed(scenario["file"], scenario["title"])
        journeys[key] = {"result": "pass", "journeys": scenario["journeys"]}

    widths = contract["manual_visual"]["viewport_widths_px"]
    profiles = []
    for index, width in enumerate(widths):
        for locale in contract["manual_visual"]["locales"]:
            theme = "light" if (index % 2 == 0) == (locale == "en") else "dark"
            require_passed("authenticated-shell.spec.ts", f"workspace audit · {locale} · {theme} · {width}px")
            profiles.append({"locale": locale, "theme": theme, "width_px": width, "result": "pass"})
    return {"journeys": journeys, "automated_viewports": profiles}


def write_evidence(path: Path, record: dict[str, Any]) -> None:
    with path.open("x", encoding="utf-8") as output:
        output.write(json.dumps(record, ensure_ascii=False, indent=2) + "\n")


def capture_browser(contract: dict[str, Any], report_path: Path, output: Path) -> None:
    identity = candidate_identity(contract)
    require(os.environ.get("GITHUB_SHA") == identity["candidate_commit_sha"], "GitHub Actions head SHA drift")
    run_id = int(os.environ.get("GITHUB_RUN_ID", "0"))
    attempt = int(os.environ.get("GITHUB_RUN_ATTEMPT", "0"))
    require(run_id > 0 and attempt > 0, "GitHub Actions run metadata is required")
    raw_report = report_path.read_bytes()
    result = browser_results(contract, json.loads(raw_report))
    record = {
        "schema_version": BROWSER_SCHEMA,
        "contract_checksum": CONTRACT_CHECKSUM,
        **identity,
        "github_actions": {"run_id": run_id, "attempt": attempt},
        "playwright_report_sha256": hashlib.sha256(raw_report).hexdigest(),
        **result,
    }
    write_evidence(output, {**record, "record_checksum": checksum(record)})


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify the Phase 4 product acceptance candidate and capture evidence")
    subparsers = parser.add_subparsers(dest="command")
    for command in ("manual-template", "verify-manual"):
        subparsers.add_parser(command).add_argument("path", type=Path)
    browser = subparsers.add_parser("browser-evidence")
    browser.add_argument("report", type=Path)
    browser.add_argument("output", type=Path)
    args = parser.parse_args()

    try:
        contract = load_contract()
        validate_prerequisite(contract)
        if args.command == "manual-template":
            write_evidence(args.path, manual_template(contract, candidate_identity(contract)))
            print(args.path)
        elif args.command == "verify-manual":
            record = load_json(args.path)
            identity = candidate_identity(contract)
            validate_manual(record, contract, identity)
            print(f"candidate_commit_sha={identity['candidate_commit_sha']}")
            print(f"manual_evidence_checksum={checksum(record)}")
            print("NEX_P4_11_MANUAL_VISUAL=PASS")
        elif args.command == "browser-evidence":
            capture_browser(contract, args.report, args.output)
            print("NEX_P4_11_BROWSER_EVIDENCE=PASS")
        else:
            validate_repository(contract)
            print(f"decision_id={contract['decision_id']}")
            print(f"contract_checksum={CONTRACT_CHECKSUM}")
            print("NEX_P4_10_PREREQUISITE=PASS")
            print("NEX_P4_11_PRODUCT_ACCEPTANCE_CANDIDATE=PASS")
            print("NEX_P4_11_FREEZE=PENDING_CANDIDATE_CI_AND_MANUAL_VISUAL")
    except (KeyError, OSError, TypeError, ValueError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"P4-11: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
