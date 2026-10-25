from __future__ import annotations

import copy
import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "verify_postgresql_schema",
    ROOT / "scripts/verify_postgresql_schema.py",
)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("unable to load PostgreSQL schema verifier")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class PostgreSQLSchemaTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = MODULE.load_contract()
        self.freeze_record = MODULE.load_freeze_record()

    def test_frozen_application_composition_is_valid(self) -> None:
        MODULE.validate_frozen_application_composition()

    def test_candidate_is_valid(self) -> None:
        MODULE.validate_contract(self.contract)
        MODULE.validate_files(self.contract)
        MODULE.validate_documents()
        MODULE.validate_freeze_record(self.freeze_record, self.contract)

    def test_non_postgresql_workflows_exclude_integration_tests(self) -> None:
        for relative in (
            ".github/workflows/runtime-foundation.yml",
            ".github/workflows/application-composition.yml",
        ):
            source = (ROOT / relative).read_text(encoding="utf-8")
            self.assertIn('uv run pytest -m "not integration" -q', source)

    def test_checksum_is_deterministic(self) -> None:
        reversed_contract = dict(reversed(list(self.contract.items())))
        self.assertEqual(MODULE.canonical_checksum(self.contract), MODULE.canonical_checksum(reversed_contract))

    def test_application_composition_freeze_drift_is_rejected(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["application_composition_prerequisite"]["freeze_record_checksum"] = "0" * 64
        with self.assertRaisesRegex(MODULE.PostgreSQLSchemaError, "freeze checksum"):
            MODULE.validate_contract(changed)

    def test_direct_database_dsn_environment_variable_is_rejected(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["database_configuration"]["direct_dsn_environment_variable"] = True
        with self.assertRaisesRegex(MODULE.PostgreSQLSchemaError, "direct_dsn"):
            MODULE.validate_contract(changed)

    def test_production_file_mode_cannot_be_weakened(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["database_configuration"]["production_file_mode"] = "0600"
        with self.assertRaisesRegex(MODULE.PostgreSQLSchemaError, "production file mode"):
            MODULE.validate_contract(changed)

    def test_database_release_line_cannot_change(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["database_configuration"]["release_line"] = "18.x"
        with self.assertRaisesRegex(MODULE.PostgreSQLSchemaError, "release line"):
            MODULE.validate_contract(changed)

    def test_owner_awareness_cannot_be_disabled(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["schema"]["application_tables_require_owner_id"] = False
        with self.assertRaisesRegex(MODULE.PostgreSQLSchemaError, "owner_id"):
            MODULE.validate_contract(changed)

    def test_source_immutability_cannot_be_disabled(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["schema"]["source_evidence_database_immutable"] = False
        with self.assertRaisesRegex(MODULE.PostgreSQLSchemaError, "source_evidence_database_immutable"):
            MODULE.validate_contract(changed)

    def test_deferred_table_cannot_be_removed(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["deferred_tables"].remove("background_jobs")
        with self.assertRaisesRegex(MODULE.PostgreSQLSchemaError, "deferred table"):
            MODULE.validate_contract(changed)

    def test_startup_schema_mutation_cannot_be_enabled(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["delivery"]["production_schema_mutation_on_startup"] = True
        with self.assertRaisesRegex(MODULE.PostgreSQLSchemaError, "production_schema_mutation"):
            MODULE.validate_contract(changed)

    def test_direct_trd_bot_database_access_cannot_be_enabled(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["security_boundary"]["direct_trd_bot_database_access"] = True
        with self.assertRaisesRegex(MODULE.PostgreSQLSchemaError, "direct_trd_bot"):
            MODULE.validate_contract(changed)

    def test_live_order_table_cannot_be_enabled(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["security_boundary"]["live_order_table"] = True
        with self.assertRaisesRegex(MODULE.PostgreSQLSchemaError, "live_order"):
            MODULE.validate_contract(changed)

    def test_next_stage_is_only_freeze(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["transition"]["next_allowed_stage"] = "NEX-P1-04"
        with self.assertRaisesRegex(MODULE.PostgreSQLSchemaError, "next stage"):
            MODULE.validate_contract(changed)

    def test_freeze_record_rejects_a_different_candidate(self) -> None:
        changed = copy.deepcopy(self.freeze_record)
        changed["candidate_commit_sha"] = "0" * 40
        with self.assertRaisesRegex(MODULE.PostgreSQLSchemaError, "candidate SHA"):
            MODULE.validate_freeze_record(changed, self.contract)

    def test_freeze_record_rejects_wrong_commit_message(self) -> None:
        changed = copy.deepcopy(self.freeze_record)
        changed["candidate_commit_message"] = "feat(nexora): wrong candidate"
        with self.assertRaisesRegex(MODULE.PostgreSQLSchemaError, "commit message"):
            MODULE.validate_freeze_record(changed, self.contract)

    def test_freeze_record_requires_all_postgresql_jobs(self) -> None:
        changed = copy.deepcopy(self.freeze_record)
        del changed["github_actions"]["jobs"]["postgresql_17"]
        with self.assertRaisesRegex(MODULE.PostgreSQLSchemaError, "job inventory"):
            MODULE.validate_freeze_record(changed, self.contract)

    def test_freeze_record_rejects_failed_migration_drift_check(self) -> None:
        changed = copy.deepcopy(self.freeze_record)
        changed["github_actions"]["jobs"]["postgresql_17"]["migration_drift_check_passed"] = False
        with self.assertRaisesRegex(MODULE.PostgreSQLSchemaError, "migration_drift_check_passed"):
            MODULE.validate_freeze_record(changed, self.contract)

    def test_freeze_record_requires_all_regression_workflows(self) -> None:
        changed = copy.deepcopy(self.freeze_record)
        del changed["regression_workflows"]["runtime_foundation"]
        with self.assertRaisesRegex(MODULE.PostgreSQLSchemaError, "regression workflow inventory"):
            MODULE.validate_freeze_record(changed, self.contract)

    def test_freeze_record_rejects_regression_sha_drift(self) -> None:
        changed = copy.deepcopy(self.freeze_record)
        changed["regression_workflows"]["contracts"]["head_sha"] = "0" * 40
        with self.assertRaisesRegex(MODULE.PostgreSQLSchemaError, "workflow head SHA"):
            MODULE.validate_freeze_record(changed, self.contract)

    def test_freeze_record_rejects_contract_drift(self) -> None:
        changed_contract = copy.deepcopy(self.contract)
        changed_contract["schema"]["migration_revision"] = "wrong"
        with self.assertRaisesRegex(MODULE.PostgreSQLSchemaError, "contract checksum"):
            MODULE.validate_freeze_record(self.freeze_record, changed_contract)

    def test_freeze_record_rejects_application_composition_drift(self) -> None:
        changed = copy.deepcopy(self.freeze_record)
        changed["application_composition_prerequisite"]["freeze_record_checksum"] = "0" * 64
        with self.assertRaisesRegex(MODULE.PostgreSQLSchemaError, "freeze record checksum"):
            MODULE.validate_freeze_record(changed, self.contract)

    def test_freeze_record_opens_only_p1_04(self) -> None:
        changed = copy.deepcopy(self.freeze_record)
        changed["next_allowed_stage"] = "NEX-P1-05"
        with self.assertRaisesRegex(MODULE.PostgreSQLSchemaError, "post-freeze next stage"):
            MODULE.validate_freeze_record(changed, self.contract)


if __name__ == "__main__":
    unittest.main()
