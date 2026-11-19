#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import re
import subprocess
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PRODUCT_VERIFIER = importlib.util.spec_from_file_location(
    "p4_12_product_acceptance", ROOT / "scripts/verify_phase_four_product_acceptance.py"
)
if PRODUCT_VERIFIER is None or PRODUCT_VERIFIER.loader is None:
    raise RuntimeError("unable to load P4-11 verifier")
product = importlib.util.module_from_spec(PRODUCT_VERIFIER)
PRODUCT_VERIFIER.loader.exec_module(product)

CONTRACT_PATH = ROOT / "contracts/nexora-v0.1-phase-four-final-acceptance.json"
CONTRACT_CHECKSUM = "cee37b921999fb4eed8202bd0f26156b9d43b2894ba8ebc4a5947defc5d9ca17"
RECORD_PATH = ROOT / "artifacts/p4-12/phase-four-final-acceptance.json"
RECORD_SCHEMA = "nexora-phase-four-final-acceptance-record-v1"


def load_contract() -> dict[str, Any]:
    contract = product.load_json(CONTRACT_PATH)
    product.require(product.checksum(contract) == CONTRACT_CHECKSUM, "P4-12 contract checksum drift")
    return contract


def validate_repository(contract: dict[str, Any]) -> dict[str, Any]:
    reference = contract["roadmap"]
    roadmap = product.load_json(ROOT / reference["path"])
    product.require(product.checksum(roadmap) == reference["checksum"], "Phase 4 roadmap checksum drift")
    product.require(contract["deferred"] == roadmap["deferred"], "deferred inventory drift")
    product.require(
        contract["server_deployment_gate"] == roadmap["server_deployment_gate"], "server deployment gate drift"
    )
    product.require(contract["production_readiness_claimed"] is False, "production readiness cannot be claimed")

    chain = contract["freeze_chain"]
    for index in range(12):
        stage = f"NEX-P4-{index:02}"
        evidence = chain[stage]
        record = product.load_json(ROOT / evidence["path"])
        product.require(product.checksum(record) == evidence["checksum"], f"{stage} Freeze checksum drift")
        product.require(record["decision_id"] == stage and record["frozen"] is True, f"{stage} is not frozen")
        product.require(record["next_allowed_stage"] == f"NEX-P4-{index + 1:02}", f"{stage} transition drift")

    p4_11 = product.load_json(ROOT / chain["NEX-P4-11"]["path"])
    product.validate_freeze_record(p4_11, product.load_contract())
    product.require(
        p4_11["candidate_commit_sha"] == contract["p4_11_prerequisite"]["accepted_product_commit_sha"],
        "P4-11 accepted product SHA drift",
    )
    for gate in contract["required_ci_gates"].values():
        product.require((ROOT / gate["workflow"]).is_file(), f"workflow missing: {gate['workflow']}")
    return p4_11


def git_output(*args: str) -> bytes:
    return subprocess.check_output(("git", "--no-optional-locks", *args), cwd=ROOT)


def validate_reviewed_product_tree(contract: dict[str, Any], candidate: str) -> None:
    snapshot = git_output("ls-tree", "-r", "-z", candidate, "--", *contract["reviewed_product_paths"])
    product.require(
        hashlib.sha256(snapshot).hexdigest() == contract["reviewed_product_tree_checksum"],
        "product files changed since the P4-11 visual review",
    )


def candidate_identity(contract: dict[str, Any]) -> dict[str, str]:
    candidate, tree = git_output("show", "-s", "--format=%H%n%T", "HEAD").decode().splitlines()
    predecessor = contract["p4_11_prerequisite"]["freeze_commit_sha"]
    product.require(candidate != predecessor, "commit the P4-12 candidate before recording acceptance")
    product.require(not git_output("status", "--porcelain"), "record acceptance from a clean candidate checkout")
    try:
        git_output("merge-base", "--is-ancestor", predecessor, candidate)
    except subprocess.CalledProcessError as error:
        raise product.ProductAcceptanceError("the candidate must descend from the P4-11 Freeze") from error
    validate_reviewed_product_tree(contract, candidate)
    return {"candidate_commit_sha": candidate, "candidate_tree_sha": tree}


def validate_ci_gates(contract: dict[str, Any], identity: dict[str, str], runs: dict[str, Any]) -> dict[str, Any]:
    gates = {}
    for gate, spec in contract["required_ci_gates"].items():
        run = runs[spec["workflow"]]
        product.require(run.get("head_sha") == identity["candidate_commit_sha"], f"{gate}: CI head SHA drift")
        product.require(run.get("head_branch") == contract["candidate_branch"], f"{gate}: CI branch drift")
        product.require(
            run.get("event") == "push" and run.get("conclusion") == "success", f"{gate}: CI push did not succeed"
        )
        product.require(type(run.get("run_id")) is int and run["run_id"] > 0, f"{gate}: invalid CI run ID")
        product.require(type(run.get("attempt")) is int and run["attempt"] > 0, f"{gate}: invalid CI run attempt")
        job = run["jobs"][spec["job"]]
        product.require(job.get("head_sha") == run["head_sha"], f"{gate}: CI job head SHA drift")
        product.require(job.get("run_attempt") == run["attempt"], f"{gate}: CI job attempt drift")
        product.require(job.get("conclusion") == "success", f"{gate}: CI job did not succeed")
        product.require(type(job.get("job_id")) is int and job["job_id"] > 0, f"{gate}: invalid CI job ID")
        for step in spec["steps"]:
            product.require(job["steps"].get(step) == "success", f"{gate}: step did not pass: {step}")
        gates[gate] = {
            "passed": True,
            "workflow": spec["workflow"],
            "run_id": run["run_id"],
            "run_url": f"https://github.com/{contract['repository']}/actions/runs/{run['run_id']}",
            "run_attempt": run["attempt"],
            "job_id": job["job_id"],
            "passed_steps": spec["steps"],
        }
    return gates


def build_record(
    contract: dict[str, Any], p4_11: dict[str, Any], identity: dict[str, str], ci: dict[str, Any]
) -> dict[str, Any]:
    for key in ("candidate_commit_sha", "candidate_tree_sha"):
        product.require(bool(re.fullmatch(r"[0-9a-f]{40}", identity[key])), f"invalid {key}")
    product.require(
        identity["candidate_commit_sha"] != contract["p4_11_prerequisite"]["freeze_commit_sha"],
        "P4-11 Freeze cannot be the P4-12 candidate",
    )
    gates = validate_ci_gates(contract, identity, ci["workflows"])
    browser_gate = gates["product_browser_journeys"]
    product_contract = product.load_contract()
    product.validate_browser_evidence(
        ci["browser_evidence"],
        product_contract,
        identity,
        {"run_id": browser_gate["run_id"], "attempt": browser_gate["run_attempt"]},
    )
    artifact = ci["browser_artifact"]
    product.require(artifact.get("name") == product_contract["browser"]["artifact_name"], "browser artifact name drift")
    product.require(type(artifact.get("artifact_id")) is int and artifact["artifact_id"] > 0, "invalid artifact ID")
    product.require(artifact.get("run_id") == browser_gate["run_id"], "browser artifact CI run drift")
    product.require(bool(re.fullmatch(r"sha256:[0-9a-f]{64}", artifact["digest"])), "invalid browser artifact digest")
    manual = p4_11["manual_visual"]
    gates["owner_visual_review"] = {
        "passed": True,
        "reviewed_commit_sha": manual["record"]["candidate_commit_sha"],
        "reviewer_role": manual["record"]["reviewer_role"],
        "profile_count": len(manual["record"]["results"]),
        "record_checksum": manual["record_checksum"],
        "reviewed_product_tree_checksum": contract["reviewed_product_tree_checksum"],
    }

    record = {
        "schema_version": RECORD_SCHEMA,
        "decision_id": contract["decision_id"],
        "contract_checksum": CONTRACT_CHECKSUM,
        "product_version": contract["product_version"],
        "repository": contract["repository"],
        "candidate_branch": contract["candidate_branch"],
        **identity,
        "p4_11_prerequisite": contract["p4_11_prerequisite"],
        "passed_gates": gates,
        "failed_gates": [],
        "ci_evidence": ci,
        "known_limitations": contract["known_limitations"],
        "deferred": contract["deferred"],
        "server_deployment_gate": contract["server_deployment_gate"],
        "production_readiness_claimed": False,
        "phase_four_scope_accepted": True,
        "ready_to_freeze_phase_four": True,
    }
    return {**record, "record_checksum": product.checksum(record)}


def validate_final_record(record: dict[str, Any], contract: dict[str, Any], p4_11: dict[str, Any]) -> None:
    identity = {key: record[key] for key in ("candidate_commit_sha", "candidate_tree_sha")}
    expected = build_record(contract, p4_11, identity, record["ci_evidence"])
    product.require(record == expected, "final acceptance record or checksum drift")


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify the Phase 4 final acceptance contract and its evidence")
    subparsers = parser.add_subparsers(dest="command")
    capture = subparsers.add_parser("capture", help="Write the record from same-candidate GitHub Actions evidence")
    capture.add_argument("ci_evidence", type=Path)
    capture.add_argument("output", type=Path)
    verify = subparsers.add_parser("verify-record")
    verify.add_argument("path", type=Path, nargs="?", default=RECORD_PATH)
    args = parser.parse_args()

    try:
        contract = load_contract()
        p4_11 = validate_repository(contract)
        print("NEX_P4_11_PREREQUISITE=PASS")
        if args.command == "capture":
            record = build_record(contract, p4_11, candidate_identity(contract), product.load_json(args.ci_evidence))
            product.write_evidence(args.output, record)
        elif args.command == "verify-record":
            record = product.load_json(args.path)
            validate_final_record(record, contract, p4_11)
        else:
            candidate = git_output("rev-parse", "HEAD").decode().strip()
            validate_reviewed_product_tree(contract, candidate)
            print(f"contract_checksum={CONTRACT_CHECKSUM}")
            print("NEX_P4_12_FINAL_ACCEPTANCE_CANDIDATE=PASS")
            if not RECORD_PATH.exists():
                print("NEX_P4_12_FREEZE=PENDING_SAME_SHA_CI")
                return 0
            record = product.load_json(RECORD_PATH)
            validate_final_record(record, contract, p4_11)
        print(f"candidate_commit_sha={record['candidate_commit_sha']}")
        print(f"record_checksum={record['record_checksum']}")
        print("NEX_P4_12_FINAL_ACCEPTANCE_RECORD=PASS")
        print("PRODUCTION_READINESS_CLAIMED=false")
    except (KeyError, OSError, TypeError, ValueError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"P4-12: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
