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

    def test_frozen_application_composition_is_valid(self) -> None:
        MODULE.validate_frozen_application_composition()

    def test_candidate_is_valid(self) -> None:
        MODULE.validate_contract(self.contract)
        MODULE.validate_files(self.contract)
        MODULE.validate_documents()

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


if __name__ == "__main__":
    unittest.main()
