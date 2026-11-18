#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from itertools import pairwise
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "contracts/nexora-v0.1-phase-four-product-experience-roadmap.json"
P3_ACCEPTANCE_PATH = ROOT / "artifacts/p3-13/phase-three-final-acceptance.json"
FREEZE_PATH = ROOT / "artifacts/p4-00/phase-four-product-experience-roadmap-freeze.json"
WORD_ROADMAP_PATH = ROOT / "docs/v0.1/Nexora_Phase_4_Product_Experience_Roadmap_FA.docx"

CONTRACT_CHECKSUM = "023b800af6e339ce0fa18a0c20bcb6d06282f11110dc16f134151364e6fb6b61"
P3_ACCEPTANCE_CANONICAL_CHECKSUM = "7d362ce2a7cb4f916a5fd2da4d704ebbb45b714290ef746dbdb95456e24f01fa"
P3_ACCEPTANCE_RECORD_CHECKSUM = "c42b1fc54c1b8f4d74c25a8a3e4499a87eae5eb3d0590de8ebff7e452e224149"
P3_CANDIDATE_SHA = "bff9b1f3b4f84f0019eef6e25d50a22d4bc9ccb2"
P3_FREEZE_SHA = "0c08c71ccb3a75d3dd662eb6f780a677cf25d6f1"
P4_CANDIDATE_SHA = "1fc09c0354876d1ced6eebd7fe8d29338a8c9e8d"
P4_CANDIDATE_TREE_SHA = "e1981ea664884472fcd548d5740351fa83050d4a"
P4_CANDIDATE_PREDECESSOR_SHA = "0c08c71ccb3a75d3dd662eb6f780a677cf25d6f1"
P4_CANDIDATE_MESSAGE = "feat(nexora): define phase four product experience roadmap"
P4_PRIMARY_RUN_ID = 44307215455

EXPECTED_STAGES = [f"NEX-P4-{number:02d}" for number in range(13)]
EXPECTED_ROUTES = {
    "/{locale}/overview",
    "/{locale}/portfolios",
    "/{locale}/portfolios/{portfolio_id}",
    "/{locale}/transactions",
    "/{locale}/decisions",
    "/{locale}/alerts",
    "/{locale}/journal",
    "/{locale}/exports",
    "/{locale}/settings",
}
EXPECTED_DEFERRED = {
    "ai_copilot",
    "portfolio_ml",
    "connected_financial_accounts",
    "exchange_trade_credentials",
    "wallet_keys_and_fund_transfer",
    "live_trading",
    "multi_user_saas",
    "public_registration",
    "native_mobile_application",
    "autonomous_ai_actions",
    "financial_or_tax_advice",
}
FORBIDDEN_CAPABILITIES = {
    "saas",
    "multi_user",
    "public_internet_deployment",
    "exchange_credentials",
    "wallet_private_keys_or_signing",
    "fund_transfer",
    "live_order_capability",
    "autonomous_ai_execution",
    "ml_training_or_inference",
    "financial_advice",
    "tax_advice",
    "direct_trd_bot_database_access",
}
REQUIRED_EXPERIENCE_FLAGS = {
    "first_run_onboarding_required",
    "first_portfolio_creation_without_direct_api_required",
    "collapsible_desktop_sidebar_required",
    "mobile_navigation_required",
    "full_width_responsive_page_frame_required",
    "plain_language_messages_required",
    "persian_avoids_unnecessary_english_required",
    "shared_micro_components_required",
    "confirmation_dialog_for_sensitive_actions_required",
    "toast_for_transient_operation_feedback_required",
    "inline_form_errors_required",
    "charts_only_when_they_improve_understanding",
    "chart_text_equivalent_required",
    "rtl_ltr_required",
    "light_dark_required",
    "keyboard_and_screen_reader_required",
    "reduced_motion_required",
    "no_page_level_horizontal_overflow_required",
}
REQUIRED_COMPONENTS = {
    "button",
    "input",
    "select",
    "form_field",
    "field_error",
    "toast",
    "skeleton",
    "empty_state",
    "error_state",
    "modal",
    "confirmation_dialog",
    "drawer",
    "tooltip",
    "table",
    "responsive_record_list",
    "chart_container",
    "comparison_block",
}


class PhaseFourProductExperienceRoadmapError(ValueError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise PhaseFourProductExperienceRoadmapError(message)


def _json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    _require(isinstance(payload, dict), f"{path.name} must contain an object")
    return payload


def canonical_checksum(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def load_contract(path: Path = CONTRACT_PATH) -> dict[str, Any]:
    return _json(path)


def load_freeze_record(path: Path = FREEZE_PATH) -> dict[str, Any]:
    return _json(path)


def validate_phase_three_prerequisite(path: Path = P3_ACCEPTANCE_PATH) -> None:
    acceptance = _json(path)
    _require(canonical_checksum(acceptance) == P3_ACCEPTANCE_CANONICAL_CHECKSUM, "P3-13 acceptance artifact drift")
    _require(acceptance.get("record_checksum") == P3_ACCEPTANCE_RECORD_CHECKSUM, "P3-13 record checksum drift")
    _require(acceptance.get("candidate_commit_sha") == P3_CANDIDATE_SHA, "P3-13 candidate drift")
    _require(acceptance.get("phase_three_scope_accepted") is True, "Phase 3 scope was not accepted")
    _require(acceptance.get("ready_to_freeze_phase_three") is True, "Phase 3 was not ready to freeze")
    _require(acceptance.get("failed_gates") == [], "P3-13 contains failed gates")
    _require(acceptance.get("production_readiness_claimed") is False, "P3-13 cannot claim production readiness")


def _validate_source_hierarchy(contract: dict[str, Any]) -> None:
    sources = contract.get("source_hierarchy")
    _require(isinstance(sources, list) and len(sources) == 4, "source hierarchy must contain four sources")
    priorities = [source.get("priority") for source in sources if isinstance(source, dict)]
    _require(priorities == [1, 2, 3, 4], "source hierarchy priority drift")
    _require(
        sources[0].get("source") == "frozen_repository_contracts_and_acceptance_records",
        "frozen repository truth must remain first",
    )


def _validate_roadmap(contract: dict[str, Any]) -> None:
    roadmap = contract.get("phase_four_roadmap")
    _require(isinstance(roadmap, list), "Phase 4 roadmap must be a list")
    stage_ids = [stage.get("stage_id") for stage in roadmap if isinstance(stage, dict)]
    _require(stage_ids == EXPECTED_STAGES, "Phase 4 stage order drift")
    _require(roadmap[0].get("status") == "candidate", "P4-00 must remain the only candidate")
    _require(all(stage.get("status") == "planned" for stage in roadmap[1:]), "later Phase 4 stages must remain planned")
    _require(roadmap[0].get("depends_on") == ["NEX-P3-13-FREEZE"], "P4-00 Phase 3 dependency drift")
    for previous, stage in pairwise(roadmap):
        _require(
            stage.get("depends_on") == [f"{previous['stage_id']}-FREEZE"], f"{stage.get('stage_id')} dependency drift"
        )


def _validate_experience(contract: dict[str, Any]) -> None:
    experience = contract.get("product_experience_requirements")
    _require(isinstance(experience, dict), "product experience requirements must be an object")
    _require(experience.get("persian_sidebar_side") == "right", "Persian Sidebar must remain right")
    _require(experience.get("english_sidebar_side") == "left", "English Sidebar must remain left")
    for key in REQUIRED_EXPERIENCE_FLAGS:
        _require(experience.get(key) is True, f"required experience disabled: {key}")
    _require(
        set(contract.get("micro_component_inventory", [])) >= REQUIRED_COMPONENTS,
        "required micro-component inventory drift",
    )


def validate_contract(contract: dict[str, Any]) -> None:
    _require(
        contract.get("schema_version") == "nexora-phase-four-product-experience-roadmap-v1", "invalid schema version"
    )
    _require(contract.get("decision_id") == "NEX-P4-00", "invalid decision ID")
    _require(contract.get("decision_date") == "2026-11-18", "invalid decision date")
    _require(contract.get("status") == "candidate", "P4-00 must remain a candidate")

    prerequisite = contract.get("phase_three_prerequisite")
    _require(isinstance(prerequisite, dict), "Phase 3 prerequisite must be an object")
    _require(prerequisite.get("frozen") is True, "Phase 3 prerequisite must be frozen")
    _require(prerequisite.get("freeze_commit_sha") == P3_FREEZE_SHA, "Phase 3 Freeze commit drift")
    _require(prerequisite.get("accepted_candidate_commit_sha") == P3_CANDIDATE_SHA, "Phase 3 candidate drift")
    _require(
        prerequisite.get("acceptance_record_canonical_checksum") == P3_ACCEPTANCE_CANONICAL_CHECKSUM,
        "Phase 3 acceptance checksum drift",
    )
    _require(
        prerequisite.get("acceptance_record_checksum") == P3_ACCEPTANCE_RECORD_CHECKSUM, "Phase 3 record checksum drift"
    )
    _require(prerequisite.get("phase_three_scope_accepted") is True, "Phase 3 must be accepted")
    _require(
        prerequisite.get("production_readiness_claimed") is False,
        "Phase 3 prerequisite cannot claim production readiness",
    )

    _validate_source_hierarchy(contract)
    decision = contract.get("reconciliation_decision")
    _require(isinstance(decision, dict), "reconciliation decision must be an object")
    _require(decision.get("product_version") == "0.1.0", "product version drift")
    _require(decision.get("delivery_phase") == "P4", "delivery phase drift")
    _require(decision.get("phase_number_is_not_product_version") is True, "phase/version confusion restored")
    _require(decision.get("backend_domain_reimplementation_allowed") is False, "backend reimplementation opened")
    _require(decision.get("contract_defect_repairs_allowed") is True, "contract defect repair disabled")
    _require(decision.get("new_product_capabilities_allowed") is False, "feature expansion opened")
    _require(
        decision.get("existing_capabilities_must_become_usable_without_direct_api_calls") is True,
        "direct-API product gap preserved",
    )
    _require(decision.get("local_product_acceptance_is_production_acceptance") is False, "local production claim")
    _require(decision.get("private_vps_gate_preserved") is True, "private VPS gate removed")

    capabilities = contract.get("capability_reconciliation")
    _require(isinstance(capabilities, list) and len(capabilities) == 8, "capability matrix drift")
    _require(set(contract.get("target_routes", [])) == EXPECTED_ROUTES, "target route inventory drift")
    _validate_experience(contract)

    lifecycle = contract.get("destructive_and_sensitive_action_policy")
    _require(isinstance(lifecycle, dict), "lifecycle policy must be an object")
    _require(lifecycle.get("physical_delete_of_immutable_evidence") is False, "physical evidence deletion enabled")
    _require(lifecycle.get("portfolio_action") == "archive", "Portfolio lifecycle drift")
    _require(lifecycle.get("asset_action") == "deactivate", "Asset lifecycle drift")
    _require(lifecycle.get("account_action") == "close", "Account lifecycle drift")
    _require(lifecycle.get("transaction_correction") == "reversal_or_supersession", "Transaction correction drift")
    _require(lifecycle.get("confirmation_dialog_required") is True, "confirmation dialog disabled")

    _validate_roadmap(contract)
    policy = contract.get("stage_execution_policy")
    _require(isinstance(policy, dict), "stage execution policy must be an object")
    _require(policy.get("assistant_runs_tests_builds_or_migrations") is False, "assistant execution rule drift")
    _require(policy.get("owner_executes_commands") is True, "owner execution rule drift")
    _require(policy.get("freeze_before_next_stage") is True, "stage Freeze gate removed")
    _require(policy.get("roadmap_change_after_freeze_requires_amendment") is True, "amendment rule removed")

    acceptance = contract.get("phase_four_acceptance")
    _require(isinstance(acceptance, dict), "Phase 4 acceptance must be an object")
    for key, value in acceptance.items():
        _require(value is (key != "production_readiness_claimed"), f"Phase 4 acceptance drift: {key}")

    _require(set(contract.get("deferred", [])) == EXPECTED_DEFERRED, "deferred capability inventory drift")
    security = contract.get("security_boundary")
    _require(isinstance(security, dict), "security boundary must be an object")
    _require(set(security) == FORBIDDEN_CAPABILITIES, "security capability inventory drift")
    _require(not any(security.values()), "Phase 4 enabled a forbidden capability")

    server = contract.get("server_deployment_gate")
    _require(isinstance(server, dict), "server deployment gate must be an object")
    _require(server.get("gate_id") == "NEX-V0.1-SERVER-DEPLOYMENT-ACCEPTANCE", "server gate ID drift")
    _require(server.get("status") == "deferred_until_private_vps_available", "server gate status drift")
    _require(server.get("removed") is False, "server gate removed")
    _require(server.get("bypassed") is False, "server gate bypassed")
    _require(server.get("production_readiness_claimed") is False, "server production claim")

    transition = contract.get("transition")
    _require(isinstance(transition, dict), "transition must be an object")
    _require(transition.get("next_allowed_stage") == "NEX-P4-00-FREEZE", "next stage drift")
    _require(transition.get("post_freeze_stage") == "NEX-P4-01", "post-Freeze stage drift")
    _require(transition.get("freeze_before_implementation") is True, "implementation opened before Freeze")
    _require(transition.get("requires_successful_ci_on_candidate_sha") is True, "candidate CI gate removed")
    _require(transition.get("word_roadmap_generated_after_freeze") is True, "Word generation moved before Freeze")


def validate_freeze_record(record: dict[str, Any], contract: dict[str, Any]) -> None:
    _require(
        record.get("schema_version") == "nexora-phase-four-product-experience-roadmap-freeze-v1",
        "invalid freeze schema",
    )
    _require(record.get("decision_id") == "NEX-P4-00", "invalid freeze decision ID")
    _require(record.get("repository") == "amirhosseinhamidian/nexora", "repository drift")
    _require(record.get("candidate_commit_sha") == P4_CANDIDATE_SHA, "candidate SHA drift")
    _require(record.get("candidate_tree_sha") == P4_CANDIDATE_TREE_SHA, "candidate tree drift")
    _require(record.get("candidate_predecessor_sha") == P4_CANDIDATE_PREDECESSOR_SHA, "candidate predecessor drift")
    _require(record.get("candidate_commit_message") == P4_CANDIDATE_MESSAGE, "candidate message drift")

    workflow = record.get("github_actions")
    _require(isinstance(workflow, dict), "GitHub Actions evidence must be an object")
    _require(
        workflow.get("workflow_path") == ".github/workflows/phase-four-product-experience-roadmap.yml",
        "workflow path drift",
    )
    _require(workflow.get("run_id") == P4_PRIMARY_RUN_ID, "workflow run ID drift")
    _require(
        workflow.get("run_url") == f"https://github.com/amirhosseinhamidian/nexora/actions/runs/{P4_PRIMARY_RUN_ID}",
        "workflow URL drift",
    )
    _require(workflow.get("head_sha") == P4_CANDIDATE_SHA, "workflow head SHA drift")
    _require(workflow.get("head_branch") == "feature/v0.1-decision-intelligence", "workflow branch drift")
    _require(workflow.get("event") == "push", "workflow must be a push run")
    _require(workflow.get("attempt") == 1, "workflow attempt drift")
    _require(workflow.get("conclusion") == "success", "workflow did not succeed")
    jobs = workflow.get("jobs")
    _require(isinstance(jobs, dict), "workflow jobs must be an object")
    expected_jobs = {
        "product_experience_roadmap_contract": 134811770398,
        "backend_regression": 134811769903,
        "web_regression": 134811770353,
    }
    _require(set(jobs) == set(expected_jobs), "workflow job inventory drift")
    for name, job_id in expected_jobs.items():
        job = jobs[name]
        _require(isinstance(job, dict), f"{name} evidence must be an object")
        _require(job.get("job_id") == job_id, f"{name} job ID drift")
        _require(job.get("conclusion") == "success", f"{name} did not succeed")
        _require(job.get("required_steps_passed") is True, f"{name} required steps did not pass")

    evidence = record.get("phase_four_product_experience_roadmap_contract")
    _require(isinstance(evidence, dict), "P4-00 contract evidence must be an object")
    _require(
        evidence.get("path") == "contracts/nexora-v0.1-phase-four-product-experience-roadmap.json",
        "contract path drift",
    )
    _require(evidence.get("schema_version") == contract.get("schema_version"), "contract schema drift")
    _require(evidence.get("checksum") == CONTRACT_CHECKSUM, "recorded contract checksum drift")
    _require(evidence.get("checksum") == canonical_checksum(contract), "contract checksum mismatch")

    word = record.get("word_roadmap")
    _require(isinstance(word, dict), "Word roadmap evidence must be an object")
    _require(
        word.get("path") == "docs/v0.1/Nexora_Phase_4_Product_Experience_Roadmap_FA.docx",
        "Word roadmap path drift",
    )
    _require(word.get("language") == "fa-IR", "Word roadmap language drift")
    _require(word.get("generated_after_candidate_ci") is True, "Word roadmap was generated before candidate CI")
    _require(WORD_ROADMAP_PATH.is_file(), "Word roadmap is missing")
    _require(
        word.get("sha256") == hashlib.sha256(WORD_ROADMAP_PATH.read_bytes()).hexdigest(),
        "Word roadmap checksum drift",
    )
    _require(word.get("size_bytes") == WORD_ROADMAP_PATH.stat().st_size, "Word roadmap size drift")

    _require(record.get("recorded_on") == "2026-11-18", "freeze record date drift")
    _require(record.get("frozen") is True, "P4-00 is not frozen")
    _require(record.get("phase_four_implementation_started") is False, "Phase 4 implementation started before Freeze")
    _require(record.get("next_allowed_stage") == "NEX-P4-01", "post-Freeze stage drift")
    _require(record.get("roadmap_amendment_required_for_material_change") is True, "roadmap amendment gate removed")
    _require(record.get("production_readiness_claimed") is False, "production readiness cannot be claimed")

    server = record.get("server_deployment_acceptance")
    _require(isinstance(server, dict), "server gate evidence must be an object")
    _require(server.get("gate_id") == "NEX-V0.1-SERVER-DEPLOYMENT-ACCEPTANCE", "server gate ID drift")
    _require(server.get("status") == "deferred_until_private_vps_available", "server gate status drift")
    _require(server.get("removed") is False, "server gate was removed")
    _require(server.get("bypassed") is False, "server gate was bypassed")


def validate_files_and_markers() -> None:
    expected = (
        ("README.md", "`NEX-P4-00` is a Candidate"),
        ("README.md", "NEX_P4_00_FREEZE=PASS"),
        ("docs/v0.1/47-phase-four-product-experience-roadmap.md", "# NEX-P4-00"),
        (".github/workflows/phase-four-product-experience-roadmap.yml", "name: Phase 4 product experience roadmap"),
        ("tests/test_phase_four_product_experience_roadmap.py", "class PhaseFourProductExperienceRoadmapContractTests"),
    )
    for relative, marker in expected:
        content = (ROOT / relative).read_text(encoding="utf-8")
        _require(marker in content, f"{relative} is missing the P4-00 marker")


def main() -> int:
    validate_phase_three_prerequisite()
    contract = load_contract()
    validate_contract(contract)
    _require(canonical_checksum(contract) == CONTRACT_CHECKSUM, "P4-00 contract checksum drift")
    validate_files_and_markers()
    freeze_record = load_freeze_record()
    validate_freeze_record(freeze_record, contract)
    print(f"schema_version={contract['schema_version']}")
    print(f"decision_id={contract['decision_id']}")
    print(f"contract_checksum={CONTRACT_CHECKSUM}")
    print("NEX_P3_13_FREEZE_PREREQUISITE=PASS")
    print("NEX_P4_00_PRODUCT_EXPERIENCE_ROADMAP_CANDIDATE=PASS")
    print(f"candidate_commit_sha={P4_CANDIDATE_SHA}")
    print("NEX_P4_00_FREEZE=PASS")
    print("NEX_P4_01=OPEN")
    print("PRODUCTION_READINESS_CLAIMED=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
