#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "contracts/nexora-v0.1-phase-two-portfolio-domain.json"
P1_13_ACCEPTANCE_PATH = ROOT / "artifacts/p1-13/phase-one-final-acceptance.json"
CONTRACT_CHECKSUM = "932187af8a74d5d30ed21fa83eb06a1038ab00c49086dcb2a71900a0d175eba5"
P1_13_ACCEPTANCE_CHECKSUM = "86e69a8a50ab75c2be9c5501ad90c8504a5c0d230cb18e90d787bb76dad86dfb"
P1_13_RECORD_CHECKSUM = "a874e2a18deedab36491cd927c818f1fa26d52df22a376f9f846cd719979ca4f"
P1_13_FREEZE_COMMIT = "5708a15d1c983c45885eeabdc4b3f77375cfc1d7"
P1_13_CANDIDATE_COMMIT = "61c5eba2ecf2a3696b6b60c87ecb1afb6064d26d"

EXPECTED_STAGES = [f"NEX-P2-{number:02d}" for number in range(1, 13)]
EXPECTED_ENTITIES = {
    "portfolio",
    "account",
    "asset",
    "asset_identifier",
    "transaction",
    "transaction_leg",
    "lot",
    "holding_projection",
    "price_observation",
    "fx_rate_observation",
    "manual_valuation",
    "import_batch",
    "import_row",
    "reconciliation_case",
    "valuation_snapshot",
    "performance_snapshot",
}
EXPECTED_EXPORT_FORMATS = {"json", "csv", "parquet", "zip_bundle"}
EXPECTED_EXPORT_PROFILES = {"private_complete", "ai_safe"}
FORBIDDEN_CAPABILITIES = {
    "saas",
    "multi_user",
    "public_internet_deployment",
    "exchange_credentials",
    "wallet_private_keys",
    "wallet_signing",
    "fund_transfer",
    "live_order_submission",
    "live_order_cancellation",
    "autonomous_ai_execution",
    "ml_training",
    "ml_inference",
    "financial_advice",
    "direct_trd_bot_database_access",
}


class PhaseTwoPortfolioDomainError(ValueError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise PhaseTwoPortfolioDomainError(message)


def _json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    _require(isinstance(payload, dict), f"{path.name} must contain an object")
    return payload


def canonical_checksum(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def load_contract(path: Path = CONTRACT_PATH) -> dict[str, Any]:
    return _json(path)


def validate_phase_one_prerequisite() -> None:
    acceptance = _json(P1_13_ACCEPTANCE_PATH)
    _require(canonical_checksum(acceptance) == P1_13_ACCEPTANCE_CHECKSUM, "P1-13 acceptance artifact drift")
    _require(acceptance.get("record_checksum") == P1_13_RECORD_CHECKSUM, "P1-13 record checksum drift")
    _require(acceptance.get("candidate_commit_sha") == P1_13_CANDIDATE_COMMIT, "P1-13 candidate drift")
    _require(acceptance.get("ready_to_freeze_phase_one") is True, "Phase 1 was not accepted")
    _require(acceptance.get("failed_gates") == [], "P1-13 contains failed gates")
    _require(acceptance.get("production_readiness_claimed") is False, "P1-13 cannot claim production readiness")
    server_gate = acceptance.get("server_deployment_acceptance")
    _require(isinstance(server_gate, dict), "P1-13 server deployment gate is missing")
    _require(server_gate.get("status") == "deferred_to_server_deployment", "server gate status drift")
    _require(server_gate.get("planned_country_code") == "DE", "planned VPS country drift")


def _validate_domain_model(contract: dict[str, Any]) -> None:
    domain = contract.get("domain_model")
    _require(isinstance(domain, dict), "domain_model must be an object")
    _require(set(domain.get("entities", [])) == EXPECTED_ENTITIES, "portfolio entity inventory drift")
    _require(set(domain.get("portfolio_kinds", [])) == {"personal", "paper", "shadow"}, "portfolio kinds drift")
    _require("wallet_watch_only" in domain.get("account_kinds", []), "wallet accounts must remain watch-only")

    journal = domain.get("transaction_semantics")
    _require(isinstance(journal, dict), "transaction_semantics must be an object")
    _require(journal.get("journal") == "immutable_double_entry_like_legs", "journal semantics drift")
    _require(journal.get("minimum_legs") == 2, "transactions require at least two legs")
    _require(journal.get("mutation") == "forbidden_after_posting", "posted transactions must be immutable")
    _require(journal.get("correction") == "reversal_or_supersession", "correction lineage drift")
    for key in ("idempotency_required", "source_lineage_required", "owner_scope_required"):
        _require(journal.get(key) is True, f"transaction journal requires {key}")

    projections = domain.get("projection_semantics")
    _require(isinstance(projections, dict), "projection_semantics must be an object")
    for key in ("holdings_are_derived", "lots_are_derived", "nav_is_derived", "pnl_is_derived"):
        _require(projections.get(key) is True, f"projection contract requires {key}")
    _require(projections.get("rebuildable_from_journal") is True, "projections must remain rebuildable")


def _validate_accounting_and_valuation(contract: dict[str, Any]) -> None:
    product = contract.get("product_boundary")
    _require(isinstance(product, dict), "product_boundary must be an object")
    _require(product.get("owner_model") == "single_owner", "owner model drift")
    _require(product.get("deployment_model") == "private_only", "deployment boundary drift")
    _require(product.get("financial_float_allowed") is False, "financial float is forbidden")
    _require(product.get("canonical_time") == "utc", "canonical time must remain UTC")
    _require(product.get("portfolio_product_complete") is False, "P2-01 cannot claim product completion")

    accounting = contract.get("accounting_policy")
    _require(isinstance(accounting, dict), "accounting_policy must be an object")
    _require(set(accounting.get("cost_basis_methods_initial", [])) == {"fifo", "weighted_average"}, "cost basis drift")
    _require(
        accounting.get("transfer_between_owned_accounts") == "non_disposal_with_basis_continuity",
        "transfer policy drift",
    )
    _require(accounting.get("negative_holding_default") == "reject_and_quarantine", "negative holding policy drift")
    _require(accounting.get("tax_advice_claimed") is False, "tax advice cannot be claimed")

    valuation = contract.get("valuation_policy")
    _require(isinstance(valuation, dict), "valuation_policy must be an object")
    for key in (
        "price_observation_immutable",
        "fx_observation_immutable",
        "stale_price_must_be_visible",
        "missing_price_must_be_visible",
    ):
        _require(valuation.get(key) is True, f"valuation policy requires {key}")
    _require(valuation.get("no_forward_fill_without_policy") is True, "implicit forward-fill is forbidden")


def _validate_import_and_export(contract: dict[str, Any]) -> None:
    imports = contract.get("import_and_reconciliation")
    _require(isinstance(imports, dict), "import_and_reconciliation must be an object")
    for key in (
        "dry_run_required",
        "deterministic_normalization",
        "content_checksum_required",
        "idempotent_reimport",
        "duplicate_detection",
        "unknown_rows_quarantined",
    ):
        _require(imports.get(key) is True, f"import runtime requires {key}")
    _require(imports.get("partial_publish_forbidden") is True, "partial import publication is forbidden")
    _require(imports.get("destructive_auto_fix") is False, "destructive reconciliation is forbidden")

    exports = contract.get("export_policy")
    _require(isinstance(exports, dict), "export_policy must be an object")
    _require(exports.get("export_first") is True, "export-first policy is required")
    _require(set(exports.get("formats", [])) == EXPECTED_EXPORT_FORMATS, "export format inventory drift")
    _require(set(exports.get("profiles", [])) == EXPECTED_EXPORT_PROFILES, "export profiles drift")
    for forbidden in ("credentials", "tokens", "recovery_codes", "private_keys", "session_identifiers"):
        _require(forbidden in exports.get("ai_safe_excludes", []), f"AI-safe export must exclude {forbidden}")
    _require(exports.get("public_download") is False, "public export download is forbidden")


def _validate_roadmap_and_boundaries(contract: dict[str, Any]) -> None:
    roadmap = contract.get("phase_two_roadmap")
    _require(isinstance(roadmap, list), "phase_two_roadmap must be a list")
    _require([stage.get("stage_id") for stage in roadmap] == EXPECTED_STAGES, "Phase 2 stage order drift")
    _require(roadmap[0].get("status") == "candidate", "P2-01 must remain candidate before Freeze")
    _require(all(stage.get("status") == "planned" for stage in roadmap[1:]), "future stages must remain planned")

    security = contract.get("security_boundary")
    _require(isinstance(security, dict), "security_boundary must be an object")
    _require(set(security) == FORBIDDEN_CAPABILITIES, "security capability inventory drift")
    for capability in FORBIDDEN_CAPABILITIES:
        _require(security.get(capability) is False, f"forbidden capability enabled: {capability}")

    trd_bot = contract.get("trd_bot_boundary")
    _require(isinstance(trd_bot, dict), "trd_bot_boundary must be an object")
    _require(trd_bot.get("trd_bot_0_3_0_compatible") is False, "TRD Bot 0.3.0 cannot be marked compatible")
    _require(trd_bot.get("runtime_mode") == "disabled_incompatible_provider", "TRD Bot runtime mode drift")
    _require(trd_bot.get("paper_shadow_only") is True, "TRD Bot projection must remain Paper/Shadow only")
    _require(trd_bot.get("live_orders") is False, "live orders are forbidden")
    _require(trd_bot.get("direct_database_access") is False, "direct TRD Bot database access is forbidden")

    server = contract.get("server_deployment_gate")
    _require(isinstance(server, dict), "server_deployment_gate must be an object")
    _require(server.get("gate_id") == "NEX-V0.1-SERVER-DEPLOYMENT-ACCEPTANCE", "server gate ID drift")
    _require(server.get("planned_country_code") == "DE", "planned VPS country drift")
    _require(server.get("status") == "deferred_to_server_deployment", "VPS gate must remain deferred")

    transition = contract.get("transition")
    _require(isinstance(transition, dict), "transition must be an object")
    _require(transition.get("next_allowed_stage") == "NEX-P2-01-FREEZE", "next stage must be P2-01 Freeze")
    _require(transition.get("post_freeze_stage") == "NEX-P2-02", "post-Freeze stage must be P2-02")
    _require(transition.get("requires_successful_ci_on_candidate_sha") is True, "candidate CI binding is required")
    _require(transition.get("freeze_before_implementation") is True, "P2-01 must Freeze before implementation")


def validate_contract(contract: dict[str, Any]) -> None:
    _require(contract.get("schema_version") == "nexora-phase-two-portfolio-domain-v1", "invalid schema version")
    _require(contract.get("decision_id") == "NEX-P2-01", "invalid decision ID")
    _require(contract.get("decision_date") == "2026-10-29", "invalid decision date")
    _require(contract.get("status") == "candidate", "P2-01 must remain a candidate")

    prerequisite = contract.get("prerequisite")
    _require(isinstance(prerequisite, dict), "prerequisite must be an object")
    _require(prerequisite.get("freeze_commit_sha") == P1_13_FREEZE_COMMIT, "P1-13 Freeze commit drift")
    _require(prerequisite.get("accepted_candidate_commit_sha") == P1_13_CANDIDATE_COMMIT, "P1-13 candidate drift")
    _require(prerequisite.get("artifact_checksum") == P1_13_ACCEPTANCE_CHECKSUM, "P1-13 artifact checksum drift")
    _require(prerequisite.get("record_checksum") == P1_13_RECORD_CHECKSUM, "P1-13 record checksum drift")
    _require(prerequisite.get("phase_one_complete") is True, "Phase 1 prerequisite must be complete")

    _validate_domain_model(contract)
    _validate_accounting_and_valuation(contract)
    _validate_import_and_export(contract)
    _validate_roadmap_and_boundaries(contract)


def main() -> int:
    validate_phase_one_prerequisite()
    contract = load_contract()
    validate_contract(contract)
    _require(canonical_checksum(contract) == CONTRACT_CHECKSUM, "P2-01 contract checksum drift")
    print(f"schema_version={contract['schema_version']}")
    print(f"decision_id={contract['decision_id']}")
    print(f"contract_checksum={CONTRACT_CHECKSUM}")
    print("NEX_P1_13_PREREQUISITE=PASS")
    print("NEX_P2_01_PORTFOLIO_DOMAIN=PASS")
    print("NEX_P2_01_READY_FOR_FREEZE=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
