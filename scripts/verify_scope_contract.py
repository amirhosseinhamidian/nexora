#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "contracts" / "nexora-v0.1-scope.json"
DOCUMENT_PATH = ROOT / "docs" / "v0.1" / "00-scope-and-system-boundary.md"
FREEZE_PATH = ROOT / "artifacts" / "p0-01" / "scope-freeze.json"


class ScopeContractError(ValueError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ScopeContractError(message)


def _require_exact_set(payload: dict[str, Any], key: str, expected: set[str]) -> None:
    actual = payload.get(key)
    _require(isinstance(actual, list), f"{key} must be an array")
    _require(set(actual) == expected, f"{key} does not match the frozen contract")


def load_contract(path: Path = CONTRACT_PATH) -> dict[str, Any]:
    with path.open(encoding="utf-8") as stream:
        payload = json.load(stream)
    _require(isinstance(payload, dict), "scope contract must be an object")
    return payload


def load_freeze_record(path: Path = FREEZE_PATH) -> dict[str, Any]:
    with path.open(encoding="utf-8") as stream:
        payload = json.load(stream)
    _require(isinstance(payload, dict), "freeze record must be an object")
    return payload


def validate_contract(contract: dict[str, Any]) -> None:
    _require(contract.get("schema_version") == "nexora-scope-contract-v1", "invalid schema")
    _require(contract.get("decision_id") == "NEX-P0-01", "invalid decision ID")
    _require(contract.get("decision_date") == "2026-10-22", "invalid decision date")

    product = contract.get("product")
    _require(isinstance(product, dict), "product must be an object")
    _require(product.get("name") == "Nexora", "invalid product name")
    _require(product.get("version") == "0.1.0", "invalid product version")
    _require(product.get("edition") == "personal", "v0.1 must be personal edition")
    _require(product.get("operating_model") == "single_owner", "v0.1 must be single-owner")
    _require(product.get("public_registration") is False, "public registration must be disabled")
    _require(product.get("saas_enabled") is False, "SaaS must be disabled")

    target = contract.get("target")
    _require(isinstance(target, dict), "target must be an object")
    _require_exact_set(target, "asset_classes", {"crypto"})
    _require_exact_set(target, "market_types", {"spot"})
    _require_exact_set(target, "portfolio_modes", {"shadow", "paper"})
    _require(target.get("live_trading") is False, "live trading must be disabled")
    _require(target.get("canonical_timezone") == "UTC", "canonical timezone must be UTC")

    integration = contract.get("integration")
    _require(isinstance(integration, dict), "integration must be an object")
    _require(integration.get("source_product") == "TRD Bot", "source product must be TRD Bot")
    _require(integration.get("compatible_release_line") == "0.3.x", "invalid TRD Bot baseline")
    _require(integration.get("direct_database_access") is False, "direct database access forbidden")
    _require_exact_set(
        integration,
        "required_boundaries",
        {"versioned_rest_api", "versioned_event_contract", "versioned_export_contract"},
    )

    export = contract.get("export")
    _require(isinstance(export, dict), "export must be an object")
    _require(export.get("required") is True, "export must be mandatory")
    _require_exact_set(export, "modes", {"full", "incremental", "selected"})
    _require_exact_set(export, "formats", {"json", "jsonl", "csv", "parquet", "zip_bundle"})
    _require_exact_set(export, "profiles", {"private", "ai_safe"})
    required_export_metadata = {
        "schema_version",
        "export_id",
        "generated_at",
        "source_versions",
        "scope",
        "filters",
        "timezone",
        "currency_unit_context",
        "lineage_references",
        "file_checksums",
        "redaction_profile",
        "completion_status",
    }
    _require_exact_set(export, "required_metadata", required_export_metadata)
    forbidden_export_fields = set(export.get("forbidden_fields", []))
    _require(
        {"password_hash", "session_token", "api_secret", "encryption_key"}
        <= forbidden_export_fields,
        "export secret denylist is incomplete",
    )

    ai_ml = contract.get("ai_ml")
    _require(isinstance(ai_ml, dict), "ai_ml must be an object")
    _require(ai_ml.get("v0_1_delivery_layer") == "ai_ready_data", "invalid AI delivery layer")
    _require(ai_ml.get("internal_copilot_enabled") is False, "internal copilot is out of scope")
    _require(ai_ml.get("predictive_ml_enabled") is False, "predictive ML is out of scope")
    _require(
        ai_ml.get("autonomous_execution_allowed") is False,
        "autonomous AI execution must be disabled",
    )
    _require(bool(ai_ml.get("trd_bot_domain")), "TRD Bot ML ownership must be explicit")
    _require(bool(ai_ml.get("nexora_domain")), "Nexora ML ownership must be explicit")

    forbidden = set(contract.get("forbidden_capabilities", []))
    required_forbidden = {
        "multi_tenant_saas",
        "exchange_account_connection",
        "production_exchange_credentials",
        "wallet",
        "withdrawal",
        "fund_transfer",
        "live_order_submit",
        "live_order_modify",
        "live_order_cancel",
        "autonomous_ai_policy_change",
        "autonomous_ai_execution",
    }
    _require(required_forbidden <= forbidden, "security capability denylist is incomplete")

    _require(
        contract.get("phase_zero")
        == ["NEX-P0-01", "NEX-P0-02", "NEX-P0-03", "NEX-P0-04", "NEX-P0-05"],
        "Phase 0 order is not frozen",
    )
    _require(contract.get("next_allowed_stage") == "NEX-P0-02", "invalid next stage")


def validate_document(path: Path = DOCUMENT_PATH) -> None:
    text = path.read_text(encoding="utf-8")
    required_markers = (
        "NEX-P0-01",
        "single-owner",
        "Crypto Spot",
        "Shadow",
        "Paper",
        "Export Contract",
        "AI-ready Data",
        "NEX-P0-02",
        "NEX_P0_01_SCOPE_CONTRACT=PASS",
        "NEX_P0_01_FREEZE=PASS",
        "وضعیت: **Frozen**",
        "da7b9d5c2f04129c055aaf403b196bac4bd7f992",
        "39763668108",
    )
    missing = [marker for marker in required_markers if marker not in text]
    _require(not missing, f"scope document is missing markers: {missing}")


def canonical_checksum(contract: dict[str, Any]) -> str:
    encoded = json.dumps(
        contract,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def validate_freeze_record(record: dict[str, Any], contract: dict[str, Any]) -> None:
    _require(record.get("schema_version") == "nexora-scope-freeze-v1", "invalid freeze schema")
    _require(record.get("decision_id") == "NEX-P0-01", "invalid freeze decision ID")
    _require(record.get("repository") == "amirhosseinhamidian/nexora", "invalid repository")
    candidate_sha = record.get("candidate_commit_sha")
    _require(
        isinstance(candidate_sha, str)
        and len(candidate_sha) == 40
        and all(character in "0123456789abcdef" for character in candidate_sha),
        "candidate SHA must be a full lowercase Git SHA",
    )
    _require(
        candidate_sha == "da7b9d5c2f04129c055aaf403b196bac4bd7f992",
        "candidate SHA does not match accepted evidence",
    )

    github_actions = record.get("github_actions")
    _require(isinstance(github_actions, dict), "github_actions must be an object")
    run_id = github_actions.get("run_id")
    _require(run_id == 39763668108, "invalid GitHub Actions run ID")
    _require(
        github_actions.get("run_url")
        == "https://github.com/amirhosseinhamidian/nexora/actions/runs/39763668108",
        "GitHub Actions URL does not match the accepted run",
    )
    _require(github_actions.get("job_name") == "scope-contract", "invalid workflow job")
    _require(github_actions.get("conclusion") == "success", "workflow was not successful")
    _require(github_actions.get("scope_verifier_passed") is True, "scope verifier not confirmed")
    _require(github_actions.get("contract_tests_passed") is True, "contract tests not confirmed")

    scope_contract = record.get("scope_contract")
    _require(isinstance(scope_contract, dict), "scope_contract evidence must be an object")
    _require(
        scope_contract.get("schema_version") == contract.get("schema_version"),
        "scope schema mismatch",
    )
    _require(
        scope_contract.get("checksum") == canonical_checksum(contract),
        "scope contract checksum mismatch",
    )
    _require(record.get("frozen") is True, "freeze record is not frozen")
    _require(record.get("next_allowed_stage") == "NEX-P0-02", "invalid frozen next stage")


def main() -> int:
    contract = load_contract()
    freeze_record = load_freeze_record()
    validate_contract(contract)
    validate_document()
    validate_freeze_record(freeze_record, contract)
    print(f"schema_version={contract['schema_version']}")
    print(f"decision_id={contract['decision_id']}")
    print(f"contract_checksum={canonical_checksum(contract)}")
    print(f"candidate_commit_sha={freeze_record['candidate_commit_sha']}")
    print("NEX_P0_01_SCOPE_CONTRACT=PASS")
    print("NEX_P0_01_FREEZE=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
