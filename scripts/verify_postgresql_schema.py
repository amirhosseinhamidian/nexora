#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "contracts/nexora-v0.1-postgresql-schema.json"
FREEZE_PATH = ROOT / "artifacts/p1-03/postgresql-schema-freeze.json"

EXPECTED_TABLES = [
    "owner_profiles",
    "source_references",
    "immutable_source_evidence",
]
EXPECTED_DEFERRED_TABLES = [
    "projection_checkpoints",
    "background_jobs",
    "outbox_events",
    "webauthn_credentials",
    "sessions",
    "service_tokens",
    "portfolio_workspaces",
    "journal_entries",
    "export_jobs",
]


class PostgreSQLSchemaError(ValueError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise PostgreSQLSchemaError(message)


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


def validate_frozen_application_composition() -> None:
    path = ROOT / "scripts/verify_application_composition.py"
    spec = importlib.util.spec_from_file_location("verify_application_composition", path)
    if spec is None or spec.loader is None:
        raise PostgreSQLSchemaError("unable to load frozen P1-02 verifier")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.validate_frozen_runtime_foundation()
    contract = module.load_contract()
    module.validate_contract(contract)
    module.validate_files(contract)
    module.validate_documents()
    module.validate_freeze_record(module.load_freeze_record(), contract)


def validate_contract(contract: dict[str, Any]) -> None:
    _require(contract.get("schema_version") == "nexora-postgresql-schema-v1", "invalid schema")
    _require(contract.get("decision_id") == "NEX-P1-03", "invalid decision ID")
    _require(contract.get("decision_date") == "2026-10-25", "invalid decision date")
    _require(contract.get("status") == "candidate", "P1-03 must remain candidate")

    prerequisite = contract.get("application_composition_prerequisite")
    _require(isinstance(prerequisite, dict), "application composition prerequisite must be an object")
    _require(prerequisite.get("decision_id") == "NEX-P1-02", "invalid application composition prerequisite")
    _require(prerequisite.get("frozen") is True, "application composition prerequisite is not frozen")
    _require(
        prerequisite.get("freeze_commit_sha") == "6ee2db690fa713a94bad016cc19f18eed6729879",
        "application composition freeze commit drift",
    )
    freeze = _json(ROOT / prerequisite["freeze_record_path"])
    _require(
        canonical_checksum(freeze) == prerequisite.get("freeze_record_checksum"),
        "application composition freeze checksum drift",
    )

    delivery = contract.get("delivery")
    _require(isinstance(delivery, dict), "delivery must be an object")
    for key in (
        "postgresql_adapter_primitives_delivered",
        "alembic_environment_delivered",
        "reversible_initial_migration_delivered",
        "owner_aware_persistence_spine_delivered",
        "immutable_source_evidence_storage_delivered",
    ):
        _require(delivery.get(key) is True, f"P1-03 must deliver {key}")
    for key in (
        "application_composition_database_registered",
        "production_schema_mutation_on_startup",
        "trd_bot_runtime_integration_delivered",
        "durable_jobs_delivered",
        "transactional_outbox_delivered",
        "identity_runtime_delivered",
    ):
        _require(delivery.get(key) is False, f"P1-03 cannot claim {key}")

    configuration = contract.get("database_configuration")
    _require(isinstance(configuration, dict), "database configuration must be an object")
    _require(configuration.get("engine") == "postgresql", "database engine drift")
    _require(configuration.get("release_line") == "17.x", "PostgreSQL release line drift")
    _require(configuration.get("driver") == "postgresql+psycopg", "database driver drift")
    _require(configuration.get("dsn_source") == "absolute_private_file", "database DSN source drift")
    _require(
        configuration.get("dsn_file_environment_variable") == "NEXORA_MIGRATION_DATABASE_DSN_FILE",
        "database DSN file variable drift",
    )
    for key in ("direct_dsn_environment_variable", "dotenv_auto_load", "committed_credentials"):
        _require(configuration.get(key) is False, f"database configuration requires false: {key}")
    _require(configuration.get("symbolic_link_allowed") is False, "database DSN symlinks must remain forbidden")
    _require(configuration.get("development_file_maximum_mode") == "0600", "development file mode drift")
    _require(configuration.get("production_file_mode") == "0400", "production file mode drift")
    _require(configuration.get("timezone") == "UTC", "database timezone drift")

    schema = contract.get("schema")
    _require(isinstance(schema, dict), "schema must be an object")
    _require(schema.get("namespace") == "nexora", "database namespace drift")
    _require(schema.get("migration_revision") == "20261025_0001", "migration revision drift")
    _require(schema.get("alembic_version_table") == "public.alembic_version", "Alembic version table drift")
    _require(schema.get("tables") == EXPECTED_TABLES, "initial table inventory drift")
    _require(schema.get("owner_profile_singleton_key") == "primary_owner", "owner singleton drift")
    for key in (
        "application_tables_require_owner_id",
        "timestamps_are_timezone_aware",
        "source_reference_requires_schema_version",
        "source_reference_requires_source_version",
        "source_reference_requires_correlation_id",
        "source_reference_requires_sha256",
        "source_evidence_checksum_matches_reference",
        "source_references_database_immutable",
        "source_evidence_database_immutable",
    ):
        _require(schema.get(key) is True, f"database invariant requires {key}")
    _require(schema.get("source_system_allowlist") == ["trd_bot"], "source system allowlist drift")
    _require(schema.get("source_evidence_payload_type") == "jsonb_object", "evidence payload type drift")

    migration = contract.get("migration_policy")
    _require(isinstance(migration, dict), "migration policy must be an object")
    _require(migration.get("tool") == "alembic", "migration tool drift")
    for key in (
        "upgrade_head_required",
        "downgrade_base_required",
        "rebuild_head_required",
        "autogenerate_drift_check_required",
        "transaction_per_migration",
    ):
        _require(migration.get(key) is True, f"migration policy requires {key}")
    for key in ("create_all_forbidden", "application_startup_migration_forbidden"):
        _require(migration.get(key) is True, f"migration safety requires {key}")

    _require(contract.get("deferred_tables") == EXPECTED_DEFERRED_TABLES, "deferred table inventory drift")
    security = contract.get("security_boundary")
    _require(isinstance(security, dict) and len(security) == 9, "security inventory drift")
    for key, value in security.items():
        _require(value is False, f"forbidden database capability enabled: {key}")

    transition = contract.get("transition")
    _require(isinstance(transition, dict), "transition must be an object")
    _require(transition.get("ready_for_freeze") is True, "P1-03 is not ready for freeze")
    _require(transition.get("next_allowed_stage") == "NEX-P1-03-FREEZE", "next stage must be freeze")
    _require(transition.get("post_freeze_stage") == "NEX-P1-04", "post-freeze stage drift")


def validate_files(contract: dict[str, Any]) -> None:
    required = (
        "alembic.ini",
        "alembic/env.py",
        "alembic/versions/20261025_0001_initial_persistence_spine.py",
        "apps/server/src/nexora/adapters/postgresql/config.py",
        "apps/server/src/nexora/adapters/postgresql/engine.py",
        "apps/server/src/nexora/adapters/postgresql/models.py",
        "apps/server/tests/test_postgresql_config.py",
        "apps/server/tests/test_postgresql_models.py",
        "apps/server/tests/test_postgresql_integration.py",
        "infra/compose/postgresql.dev.yml",
        ".github/workflows/postgresql-schema.yml",
    )
    for relative in required:
        _require((ROOT / relative).is_file(), f"missing PostgreSQL file: {relative}")

    config_source = (ROOT / "apps/server/src/nexora/adapters/postgresql/config.py").read_text(encoding="utf-8")
    for marker in (
        'DATABASE_DSN_FILE_ENV: Final = "NEXORA_MIGRATION_DATABASE_DSN_FILE"',
        'ALLOWED_DRIVER: Final = "postgresql+psycopg"',
        "path.is_absolute()",
        "stat.S_ISLNK",
        "mode != 0o400",
        "mode & 0o077",
        "SecretStr",
        "hide_password=True",
    ):
        _require(marker in config_source, f"database configuration marker missing: {marker}")
    for forbidden in ("dotenv", "NEXORA_DATABASE_URL", "print("):
        _require(forbidden not in config_source, f"unsafe database configuration marker present: {forbidden}")
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
    _require("*.dsn" in gitignore, "database DSN files must be ignored by Git")

    models = (ROOT / "apps/server/src/nexora/adapters/postgresql/models.py").read_text(encoding="utf-8")
    for table in EXPECTED_TABLES:
        _require(f'__tablename__ = "{table}"' in models, f"model table missing: {table}")
    for marker in ("owner_id", "source_schema_version", "source_version", "correlation_id", "payload_sha256", "JSONB"):
        _require(marker in models, f"model invariant missing: {marker}")
    for forbidden in EXPECTED_DEFERRED_TABLES:
        _require(f'__tablename__ = "{forbidden}"' not in models, f"deferred table created early: {forbidden}")

    migration = (ROOT / "alembic/versions/20261025_0001_initial_persistence_spine.py").read_text(encoding="utf-8")
    for marker in (
        'revision: str = "20261025_0001"',
        "def upgrade()",
        "def downgrade()",
        "CREATE SCHEMA nexora",
        "reject_immutable_source_mutation",
        "BEFORE UPDATE OR DELETE",
        "DROP SCHEMA nexora",
    ):
        _require(marker in migration, f"migration marker missing: {marker}")
    for table in EXPECTED_TABLES:
        _require(f'"{table}"' in migration, f"migration table missing: {table}")
    for forbidden in ("create_all", "live_orders", "wallets", "exchange_credentials"):
        _require(forbidden not in migration, f"forbidden migration capability present: {forbidden}")

    base_source = (ROOT / "apps/server/src/nexora/adapters/postgresql/base.py").read_text(encoding="utf-8")
    _require('ALEMBIC_VERSION_SCHEMA: Final = "public"' in base_source, "Alembic version schema is not explicit")
    _require(
        'DATABASE_SESSION_OPTIONS: Final = "-c timezone=UTC -c search_path=public"' in base_source,
        "database search path is not deterministic",
    )
    alembic_environment = (ROOT / "alembic/env.py").read_text(encoding="utf-8")
    _require(
        "version_table_schema=ALEMBIC_VERSION_SCHEMA" in alembic_environment,
        "Alembic version table schema is not enforced",
    )
    _require("include_name=_include_name" in alembic_environment, "Alembic internal table filter is not enforced")
    _require(
        'connect_args={"options": DATABASE_SESSION_OPTIONS}' in alembic_environment,
        "Alembic session options are not enforced",
    )

    for entrypoint in ("apps/server/src/nexora/api.py", "apps/server/src/nexora/worker.py"):
        source = (ROOT / entrypoint).read_text(encoding="utf-8")
        for forbidden in ("create_all", "alembic", "create_database_engine"):
            _require(forbidden not in source, f"startup schema mutation enabled in {entrypoint}: {forbidden}")

    compose = (ROOT / "infra/compose/postgresql.dev.yml").read_text(encoding="utf-8")
    _require("127.0.0.1:${NEXORA_DEV_DB_PORT:-55432}:5432" in compose, "development database is not loopback-only")
    _require("POSTGRES_PASSWORD_FILE" in compose, "development database must use a password file")
    _require("POSTGRES_PASSWORD:" not in compose, "plaintext development password is forbidden")

    workflow = (ROOT / ".github/workflows/postgresql-schema.yml").read_text(encoding="utf-8")
    for marker in (
        "database-contract:",
        "backend:",
        "postgresql-17:",
        "alembic upgrade head",
        "alembic downgrade base",
        "alembic check",
    ):
        _require(marker in workflow, f"database workflow marker missing: {marker}")

    quality = contract["quality_gates"]["postgresql_17"]
    _require(len(quality) == 5, "PostgreSQL quality gate inventory drift")

    for relative in (
        ".github/workflows/runtime-foundation.yml",
        ".github/workflows/application-composition.yml",
    ):
        source = (ROOT / relative).read_text(encoding="utf-8")
        _require(
            'uv run pytest -m "not integration" -q' in source,
            f"non-PostgreSQL workflow must exclude integration tests: {relative}",
        )


def _validate_workflow(
    workflow: Any,
    *,
    label: str,
    run_id: int,
    expected_jobs: dict[str, tuple[int, str]],
    candidate_sha: str,
) -> None:
    _require(isinstance(workflow, dict), f"{label} workflow evidence must be an object")
    _require(workflow.get("run_id") == run_id, f"invalid {label} workflow run ID")
    _require(
        workflow.get("run_url") == f"https://github.com/amirhosseinhamidian/nexora/actions/runs/{run_id}",
        f"invalid {label} workflow URL",
    )
    _require(workflow.get("head_sha") == candidate_sha, f"{label} workflow head SHA mismatch")
    _require(workflow.get("event") == "push", f"invalid {label} workflow event")
    _require(workflow.get("attempt") == 1, f"invalid {label} workflow attempt")
    _require(workflow.get("conclusion") == "success", f"{label} workflow was not successful")
    jobs = workflow.get("jobs")
    _require(isinstance(jobs, dict), f"{label} jobs must be an object")
    _require(set(jobs) == set(expected_jobs), f"{label} job inventory mismatch")
    for key, (job_id, name) in expected_jobs.items():
        job = jobs.get(key)
        _require(isinstance(job, dict), f"{label} {name} evidence must be an object")
        _require(job.get("job_id") == job_id, f"invalid {label} {name} job ID")
        _require(job.get("name") == name, f"invalid {label} {name} job name")
        _require(job.get("conclusion") == "success", f"{label} {name} job was not successful")


def validate_freeze_record(record: dict[str, Any], contract: dict[str, Any]) -> None:
    _require(record.get("schema_version") == "nexora-postgresql-schema-freeze-v1", "invalid freeze schema")
    _require(record.get("decision_id") == "NEX-P1-03", "invalid freeze decision ID")
    _require(record.get("repository") == "amirhosseinhamidian/nexora", "invalid repository")
    candidate_sha = "a448c996acdbee33bba88e788d7f768a6a96b5f9"
    _require(record.get("candidate_commit_sha") == candidate_sha, "candidate SHA does not match accepted evidence")
    _require(
        record.get("candidate_commit_message") == "fix(nexora): isolate PostgreSQL integration tests in CI",
        "candidate commit message does not match accepted evidence",
    )

    actions = record.get("github_actions")
    _validate_workflow(
        actions,
        label="PostgreSQL schema",
        run_id=40204544416,
        expected_jobs={
            "database_contract": (121202571041, "database-contract"),
            "backend": (121202571309, "backend"),
            "postgresql_17": (121202571375, "postgresql-17"),
        },
        candidate_sha=candidate_sha,
    )
    _require(actions.get("head_branch") == "feature/v0.1-foundation", "invalid GitHub Actions branch")
    required_markers = {
        "database_contract": (
            "application_composition_prerequisite_passed",
            "postgresql_schema_verifier_passed",
            "repository_contract_tests_passed",
        ),
        "backend": (
            "locked_dependencies_installed",
            "format_passed",
            "lint_passed",
            "typecheck_passed",
            "non_integration_tests_passed",
        ),
        "postgresql_17": (
            "private_dsn_fixture_created",
            "upgrade_head_passed",
            "integration_tests_passed",
            "downgrade_base_passed",
            "rebuild_head_passed",
            "migration_drift_check_passed",
        ),
    }
    for job_name, markers in required_markers.items():
        for marker in markers:
            _require(actions["jobs"][job_name].get(marker) is True, f"{job_name} did not confirm {marker}")

    regression = record.get("regression_workflows")
    _require(isinstance(regression, dict), "regression workflow evidence must be an object")
    expected_regression = {
        "runtime_foundation": (
            40204544421,
            {
                "foundation_contract": (121202570449, "foundation-contract"),
                "web": (121202570533, "web"),
                "backend": (121202570659, "backend"),
            },
        ),
        "contracts": (
            40204544423,
            {
                "technical_baseline": (121202571446, "technical-baseline"),
                "phase_zero_acceptance": (121202571489, "phase-zero-acceptance"),
                "integration_contract": (121202571573, "integration-contract"),
                "scope_contract": (121202571619, "scope-contract"),
                "security_boundary": (121202571973, "security-boundary"),
            },
        ),
        "application_composition": (
            40204544462,
            {
                "composition_contract": (121202570636, "composition-contract"),
                "backend": (121202570750, "backend"),
            },
        ),
    }
    _require(set(regression) == set(expected_regression), "regression workflow inventory mismatch")
    for label, (run_id, jobs) in expected_regression.items():
        _validate_workflow(
            regression[label],
            label=label,
            run_id=run_id,
            expected_jobs=jobs,
            candidate_sha=candidate_sha,
        )

    contract_evidence = record.get("postgresql_schema_contract")
    _require(isinstance(contract_evidence, dict), "PostgreSQL schema evidence must be an object")
    _require(contract_evidence.get("schema_version") == contract.get("schema_version"), "contract schema mismatch")
    _require(contract_evidence.get("checksum") == canonical_checksum(contract), "contract checksum mismatch")

    prerequisite = record.get("application_composition_prerequisite")
    _require(isinstance(prerequisite, dict), "application composition prerequisite must be an object")
    _require(prerequisite.get("decision_id") == "NEX-P1-02", "invalid application composition prerequisite")
    _require(prerequisite.get("frozen") is True, "application composition prerequisite is not frozen")
    prerequisite_record = _json(ROOT / "artifacts/p1-02/application-composition-freeze.json")
    _require(
        prerequisite.get("freeze_record_checksum") == canonical_checksum(prerequisite_record),
        "application composition freeze record checksum mismatch",
    )

    _require(record.get("recorded_on") == "2026-10-25", "invalid freeze record date")
    _require(record.get("frozen") is True, "PostgreSQL schema is not frozen")
    _require(record.get("postgresql_schema_complete") is True, "PostgreSQL schema stage is incomplete")
    _require(record.get("next_allowed_stage") == "NEX-P1-04", "invalid post-freeze next stage")


def validate_documents() -> None:
    document = (ROOT / "docs/v0.1/07-postgresql-schema-and-migrations.md").read_text(encoding="utf-8")
    for marker in (
        "NEX-P1-03",
        "وضعیت: **Frozen**",
        "PostgreSQL 17",
        "20261025_0001",
        "NEX_P1_03_POSTGRESQL_SCHEMA=PASS",
        "NEX_P1_03_FREEZE=PASS",
        "a448c996acdbee33bba88e788d7f768a6a96b5f9",
        "40204544416",
        "NEX-P1-04",
    ):
        _require(marker in document, f"document marker missing: {marker}")
    adr = (ROOT / "docs/adr/0017-owner-aware-postgresql-persistence-spine.md").read_text(encoding="utf-8")
    for marker in ("Status: Frozen by NEX-P1-03", "## Decision", "## Consequences"):
        _require(marker in adr, f"ADR marker missing: {marker}")


def main() -> int:
    validate_frozen_application_composition()
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
    print("NEX_P1_02_PREREQUISITE=PASS")
    print("NEX_P1_03_POSTGRESQL_SCHEMA=PASS")
    print("NEX_P1_03_FREEZE=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
