#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "contracts" / "nexora-v0.1-technical-baseline.json"
DOCUMENT_PATH = ROOT / "docs" / "v0.1" / "01-technical-baseline-and-repository-architecture.md"
ADR_PATHS = (
    ROOT / "docs" / "adr" / "0001-lightweight-polyglot-monorepo.md",
    ROOT / "docs" / "adr" / "0002-nextjs-web-fastapi-server.md",
    ROOT / "docs" / "adr" / "0003-postgresql-durable-state-and-jobs.md",
    ROOT / "docs" / "adr" / "0004-contract-first-boundaries.md",
)
SCOPE_VERIFIER_PATH = ROOT / "scripts" / "verify_scope_contract.py"


class TechnicalBaselineError(ValueError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise TechnicalBaselineError(message)


def _require_exact_set(payload: dict[str, Any], key: str, expected: set[str]) -> None:
    actual = payload.get(key)
    _require(isinstance(actual, list), f"{key} must be an array")
    _require(set(actual) == expected, f"{key} does not match the baseline")


def _load_scope_verifier() -> Any:
    spec = importlib.util.spec_from_file_location("verify_scope_contract", SCOPE_VERIFIER_PATH)
    if spec is None or spec.loader is None:
        raise TechnicalBaselineError("unable to load the frozen scope verifier")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def validate_frozen_scope() -> None:
    module = _load_scope_verifier()
    contract = module.load_contract()
    freeze_record = module.load_freeze_record()
    module.validate_contract(contract)
    module.validate_document()
    module.validate_freeze_record(freeze_record, contract)


def load_contract(path: Path = CONTRACT_PATH) -> dict[str, Any]:
    with path.open(encoding="utf-8") as stream:
        payload = json.load(stream)
    _require(isinstance(payload, dict), "technical baseline must be an object")
    return payload


def canonical_checksum(contract: dict[str, Any]) -> str:
    encoded = json.dumps(
        contract,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def validate_architecture(contract: dict[str, Any]) -> None:
    architecture = contract.get("architecture")
    _require(isinstance(architecture, dict), "architecture must be an object")
    _require(
        architecture.get("repository_model") == "lightweight_polyglot_monorepo",
        "repository model must remain a lightweight polyglot monorepo",
    )
    _require(
        architecture.get("application_style") == "modular_monolith",
        "application style must remain a modular monolith",
    )
    _require_exact_set(
        architecture,
        "deployment_units",
        {"web", "server_api", "server_worker"},
    )
    _require(
        architecture.get("source_of_truth_database") == "nexora_postgresql",
        "Nexora PostgreSQL must remain the source-of-truth database",
    )
    _require(
        architecture.get("trd_bot_database_access") == "forbidden",
        "direct TRD Bot database access must remain forbidden",
    )
    _require(
        architecture.get("runtime_bootstrap_delivered") is False,
        "P0-02 cannot claim runtime bootstrap delivery",
    )
    _require(
        architecture.get("microservices_required") is False,
        "microservices cannot be required in the v0.1 baseline",
    )


def validate_technology(contract: dict[str, Any]) -> None:
    baseline = contract.get("technology_baseline")
    _require(isinstance(baseline, dict), "technology_baseline must be an object")

    web = baseline.get("web")
    _require(isinstance(web, dict), "web baseline must be an object")
    expected_web = {
        "runtime": "nodejs",
        "runtime_release_line": "24.x-lts",
        "package_manager": "pnpm",
        "package_manager_release_line": "10.x",
        "framework": "nextjs",
        "framework_release_line": "16.x",
        "router": "app_router",
        "ui_runtime": "react",
        "ui_runtime_release_line": "19.x",
        "language": "typescript",
        "language_release_line": "5.x",
        "styling": "tailwind_css_4",
        "component_primitives": "radix_ui",
    }
    for key, expected in expected_web.items():
        _require(web.get(key) == expected, f"web {key} does not match the baseline")
    _require(web.get("typescript_strict") is True, "TypeScript strict mode is required")

    server = baseline.get("server")
    _require(isinstance(server, dict), "server baseline must be an object")
    expected_server = {
        "runtime": "python",
        "runtime_release_line": "3.13.x",
        "package_manager": "uv",
        "framework": "fastapi",
        "validation": "pydantic_2",
        "orm": "sqlalchemy_2",
        "migrations": "alembic_1",
        "postgres_driver": "psycopg_3",
        "unit_and_integration_tests": "pytest",
        "format_and_lint": "ruff",
        "typecheck": "mypy_strict",
    }
    for key, expected in expected_server.items():
        _require(server.get(key) == expected, f"server {key} does not match the baseline")

    data = baseline.get("data")
    _require(isinstance(data, dict), "data baseline must be an object")
    _require(data.get("database") == "postgresql", "PostgreSQL is required")
    _require(data.get("database_release_line") == "17.x", "PostgreSQL 17.x is required")
    _require(
        data.get("durable_job_backend") == "postgresql",
        "durable jobs must use PostgreSQL",
    )
    _require(
        data.get("event_delivery_pattern") == "transactional_outbox",
        "transactional outbox is required",
    )
    _require(
        data.get("artifact_storage_initial") == "versioned_local_filesystem_adapter",
        "initial artifact storage must remain adapter-backed and versioned",
    )
    _require(data.get("parquet_engine") == "pyarrow", "PyArrow is the Parquet baseline")
    _require(data.get("redis_required") is False, "Redis must not be required initially")
    _require(
        data.get("external_message_broker_required") is False,
        "an external message broker must not be required initially",
    )

    delivery = baseline.get("delivery")
    _require(isinstance(delivery, dict), "delivery baseline must be an object")
    _require(
        delivery.get("local_and_single_host_orchestration") == "docker_compose",
        "Docker Compose is the local and single-host baseline",
    )
    _require(delivery.get("ci") == "github_actions", "GitHub Actions is the CI baseline")
    _require(delivery.get("javascript_lockfile") == "pnpm-lock.yaml", "invalid JS lockfile")
    _require(delivery.get("python_lockfile") == "uv.lock", "invalid Python lockfile")
    _require(delivery.get("container_base_images_pinned") is True, "container images must be pinned")


def validate_layout(contract: dict[str, Any]) -> None:
    layout = contract.get("repository_layout")
    _require(isinstance(layout, list), "repository_layout must be an array")
    paths = [entry.get("path") for entry in layout if isinstance(entry, dict)]
    _require(len(paths) == len(layout), "every repository layout entry must be an object")
    _require(len(paths) == len(set(paths)), "repository layout paths must be unique")
    expected = {
        "apps/web",
        "apps/server",
        "packages/contracts",
        "packages/ui",
        "packages/config",
        "infra/compose",
        "docs/adr",
        "scripts",
        "tests",
        "artifacts",
    }
    _require(set(paths) == expected, "repository layout does not match the frozen plan")
    for entry in layout:
        _require(bool(entry.get("owner")), "repository layout owner is required")
        _require(bool(entry.get("purpose")), "repository layout purpose is required")


def validate_layers(contract: dict[str, Any]) -> None:
    layers = contract.get("server_layers")
    _require(isinstance(layers, list), "server_layers must be an array")
    actual = {
        entry.get("name"): set(entry.get("may_depend_on", []))
        for entry in layers
        if isinstance(entry, dict)
    }
    expected = {
        "domain": set(),
        "application": {"domain"},
        "adapters": {"application", "domain"},
        "api": {"application", "adapters", "domain"},
        "worker": {"application", "adapters", "domain"},
    }
    _require(actual == expected, "server dependency direction does not match the baseline")


def validate_boundaries(contract: dict[str, Any]) -> None:
    boundaries = contract.get("boundary_rules")
    _require(isinstance(boundaries, dict), "boundary_rules must be an object")
    _require(boundaries.get("web_business_logic") == "forbidden", "web business logic forbidden")
    _require(
        boundaries.get("next_route_handlers") == "same_origin_transport_only",
        "Next.js route handlers must remain transport-only",
    )
    _require(boundaries.get("server_owns_domain_commands") is True, "server must own commands")
    _require(boundaries.get("contracts_depend_on_runtime") is False, "contracts must be independent")
    _require(
        boundaries.get("direct_cross_database_queries") is False,
        "cross-database queries must remain forbidden",
    )
    _require_exact_set(
        boundaries,
        "trd_bot_integration",
        {"versioned_rest_api", "versioned_event_contract", "versioned_export_contract"},
    )
    _require(boundaries.get("unknown_schema_behavior") == "fail_closed", "schema must fail closed")
    _require(boundaries.get("canonical_storage_timezone") == "UTC", "storage timezone must be UTC")


def validate_database_rules(contract: dict[str, Any]) -> None:
    rules = contract.get("database_rules")
    _require(isinstance(rules, dict), "database_rules must be an object")
    _require(rules.get("schema_owner") == "nexora_server", "invalid database owner")
    _require(rules.get("migration_tool") == "alembic", "Alembic is required")
    required_true = {
        "application_tables_require_owner_id",
        "external_source_projections_require_source_reference",
        "external_evidence_is_immutable",
        "jobs_require_idempotency_key",
        "outbox_written_in_domain_transaction",
        "timestamps_are_timezone_aware",
    }
    for key in required_true:
        _require(rules.get(key) is True, f"database rule {key} must be enabled")
    _require(
        rules.get("production_schema_mutation_on_startup") is False,
        "production schema mutation on startup must be disabled",
    )


def validate_debt_and_security(contract: dict[str, Any]) -> None:
    debts = contract.get("debt_inventory")
    _require(isinstance(debts, list), "debt_inventory must be an array")
    _require(len(debts) == 5, "all five known baseline debts must be tracked")
    ids = {entry.get("id") for entry in debts if isinstance(entry, dict)}
    _require(len(ids) == len(debts), "debt IDs must be unique")
    for debt in debts:
        _require(bool(debt.get("owner")), "every debt requires an owner")
        _require(bool(debt.get("due_stage")), "every debt requires a due stage")
        _require(debt.get("risk") in {"low", "medium", "high"}, "invalid debt risk")
        _require(bool(debt.get("temporary_behavior")), "every debt needs temporary behavior")

    forbidden = set(contract.get("forbidden_architecture", []))
    required_forbidden = {
        "shared_database_with_trd_bot",
        "direct_trd_bot_database_read",
        "frontend_domain_persistence",
        "redis_as_source_of_truth",
        "in_memory_only_durable_jobs",
        "unversioned_external_contract",
        "live_order_module",
        "exchange_credential_module",
        "wallet_module",
        "multi_tenant_billing_module",
    }
    _require(required_forbidden <= forbidden, "forbidden architecture inventory is incomplete")


def validate_quality_and_dependency_policy(contract: dict[str, Any]) -> None:
    gates = contract.get("quality_gates")
    _require(isinstance(gates, dict), "quality_gates must be an object")
    expected_gates = {
        "repository": {"format", "lint", "typecheck", "unit_tests", "contract_tests", "build"},
        "server": {"ruff_format_check", "ruff_check", "mypy_strict", "pytest"},
        "web": {"prettier_check", "eslint", "typescript_no_emit", "vitest", "next_build"},
        "database": {"upgrade_head", "downgrade_base", "rebuild_head", "alembic_check"},
        "security": {"dependency_audit", "secret_scan", "forbidden_capability_inventory"},
    }
    _require(set(gates) == set(expected_gates), "quality gate groups do not match the baseline")
    for group, expected in expected_gates.items():
        _require(set(gates.get(group, [])) == expected, f"quality gate group {group} is incomplete")

    policy = contract.get("dependency_policy")
    _require(isinstance(policy, dict), "dependency_policy must be an object")
    for key in (
        "lockfiles_committed",
        "exact_resolutions_recorded",
        "security_updates_reviewed",
        "dependency_addition_requires_owner_and_reason",
        "no_turborepo_or_nx_initially",
        "no_redis_initially",
        "no_kubernetes_initially",
    ):
        _require(policy.get(key) is True, f"dependency policy {key} must remain enabled")
    _require(
        policy.get("automated_major_updates") is False,
        "automated major dependency updates must remain disabled",
    )

    snapshot = contract.get("reference_snapshot")
    _require(isinstance(snapshot, dict), "reference_snapshot must be an object")
    _require(snapshot.get("checked_on") == "2026-10-22", "invalid reference snapshot date")
    sources = snapshot.get("sources")
    _require(isinstance(sources, list) and len(sources) == 4, "four official references are required")
    allowed_hosts = (
        "https://nextjs.org/",
        "https://nodejs.org/",
        "https://www.python.org/",
        "https://www.postgresql.org/",
    )
    _require(
        all(isinstance(source, str) and source.startswith(allowed_hosts) for source in sources),
        "reference snapshot must contain only the selected official sources",
    )


def validate_contract(contract: dict[str, Any]) -> None:
    _require(
        contract.get("schema_version") == "nexora-technical-baseline-v1",
        "invalid technical baseline schema",
    )
    _require(contract.get("decision_id") == "NEX-P0-02", "invalid decision ID")
    _require(contract.get("decision_date") == "2026-10-22", "invalid decision date")
    _require(contract.get("status") == "candidate", "baseline must remain a candidate before freeze")
    product = contract.get("product")
    _require(isinstance(product, dict), "product must be an object")
    _require(product.get("name") == "Nexora", "invalid product name")
    _require(product.get("version") == "0.1.0", "invalid product version")
    _require(product.get("edition") == "personal", "Nexora v0.1 must be personal edition")
    _require(product.get("operating_model") == "single_owner", "Nexora v0.1 must be single-owner")
    validate_architecture(contract)
    validate_technology(contract)
    validate_layout(contract)
    validate_layers(contract)
    validate_boundaries(contract)
    validate_database_rules(contract)
    validate_debt_and_security(contract)
    validate_quality_and_dependency_policy(contract)
    _require(
        contract.get("bootstrap_sequence")
        == ["NEX-P0-03", "NEX-P0-04", "NEX-P0-05", "NEX-P1-01"],
        "bootstrap sequence does not preserve the Phase 0 gate",
    )
    _require(
        contract.get("next_allowed_stage") == "NEX-P0-02-FREEZE",
        "next stage must be the P0-02 freeze",
    )


def validate_documents() -> None:
    text = DOCUMENT_PATH.read_text(encoding="utf-8")
    markers = (
        "NEX-P0-02",
        "Candidate آماده بررسی و Freeze",
        "Lightweight polyglot monorepo",
        "Modular Monolith",
        "Node.js 24 LTS",
        "Next.js 16",
        "Python 3.13",
        "FastAPI",
        "PostgreSQL 17",
        "NEX-DEBT-P0-02-005",
        "NEX_P0_02_TECHNICAL_BASELINE=PASS",
        "NEX-P0-02-FREEZE",
    )
    missing = [marker for marker in markers if marker not in text]
    _require(not missing, f"technical baseline document is missing markers: {missing}")
    for path in ADR_PATHS:
        _require(path.is_file(), f"missing ADR: {path.relative_to(ROOT)}")
        adr = path.read_text(encoding="utf-8")
        _require("Accepted candidate for NEX-P0-02" in adr, f"invalid ADR status: {path.name}")
        _require("## Decision" in adr, f"ADR decision is missing: {path.name}")
        _require("## Consequences" in adr, f"ADR consequences are missing: {path.name}")


def main() -> int:
    validate_frozen_scope()
    contract = load_contract()
    validate_contract(contract)
    validate_documents()
    print(f"schema_version={contract['schema_version']}")
    print(f"decision_id={contract['decision_id']}")
    print(f"contract_checksum={canonical_checksum(contract)}")
    print("NEX_P0_01_PREREQUISITE=PASS")
    print("NEX_P0_02_TECHNICAL_BASELINE=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
