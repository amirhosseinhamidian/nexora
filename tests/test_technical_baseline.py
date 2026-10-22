from __future__ import annotations

import copy
import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "verify_technical_baseline",
    ROOT / "scripts" / "verify_technical_baseline.py",
)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("unable to load technical baseline verifier")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class TechnicalBaselineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = MODULE.load_contract()
        self.freeze_record = MODULE.load_freeze_record()

    def test_frozen_scope_prerequisite_is_valid(self) -> None:
        MODULE.validate_frozen_scope()

    def test_frozen_contract_and_documents_are_valid(self) -> None:
        MODULE.validate_contract(self.contract)
        MODULE.validate_documents()
        MODULE.validate_freeze_record(self.freeze_record, self.contract)

    def test_checksum_is_deterministic(self) -> None:
        reversed_contract = dict(reversed(list(self.contract.items())))
        self.assertEqual(
            MODULE.canonical_checksum(self.contract),
            MODULE.canonical_checksum(reversed_contract),
        )

    def test_direct_trd_bot_database_access_cannot_be_enabled(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["architecture"]["trd_bot_database_access"] = "read_only"
        with self.assertRaisesRegex(MODULE.TechnicalBaselineError, "direct TRD Bot database"):
            MODULE.validate_contract(changed)

    def test_runtime_delivery_cannot_be_claimed_in_phase_zero(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["architecture"]["runtime_bootstrap_delivered"] = True
        with self.assertRaisesRegex(MODULE.TechnicalBaselineError, "runtime bootstrap"):
            MODULE.validate_contract(changed)

    def test_monorepo_cannot_silently_become_microservices(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["architecture"]["application_style"] = "microservices"
        with self.assertRaisesRegex(MODULE.TechnicalBaselineError, "modular monolith"):
            MODULE.validate_contract(changed)

    def test_web_business_logic_cannot_be_enabled(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["boundary_rules"]["web_business_logic"] = "allowed"
        with self.assertRaisesRegex(MODULE.TechnicalBaselineError, "web business logic"):
            MODULE.validate_contract(changed)

    def test_contracts_cannot_depend_on_runtime(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["boundary_rules"]["contracts_depend_on_runtime"] = True
        with self.assertRaisesRegex(MODULE.TechnicalBaselineError, "contracts must be independent"):
            MODULE.validate_contract(changed)

    def test_redis_cannot_become_an_implicit_requirement(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["technology_baseline"]["data"]["redis_required"] = True
        with self.assertRaisesRegex(MODULE.TechnicalBaselineError, "Redis"):
            MODULE.validate_contract(changed)

    def test_durable_jobs_cannot_be_in_memory(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["technology_baseline"]["data"]["durable_job_backend"] = "memory"
        with self.assertRaisesRegex(MODULE.TechnicalBaselineError, "durable jobs"):
            MODULE.validate_contract(changed)

    def test_production_schema_mutation_cannot_be_enabled(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["database_rules"]["production_schema_mutation_on_startup"] = True
        with self.assertRaisesRegex(MODULE.TechnicalBaselineError, "schema mutation"):
            MODULE.validate_contract(changed)

    def test_layout_cannot_drop_contract_package(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["repository_layout"] = [
            entry
            for entry in changed["repository_layout"]
            if entry["path"] != "packages/contracts"
        ]
        with self.assertRaisesRegex(MODULE.TechnicalBaselineError, "repository layout"):
            MODULE.validate_contract(changed)

    def test_domain_cannot_depend_on_framework_layers(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["server_layers"][0]["may_depend_on"] = ["adapters"]
        with self.assertRaisesRegex(MODULE.TechnicalBaselineError, "dependency direction"):
            MODULE.validate_contract(changed)

    def test_every_debt_requires_an_owner(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["debt_inventory"][0]["owner"] = ""
        with self.assertRaisesRegex(MODULE.TechnicalBaselineError, "debt requires an owner"):
            MODULE.validate_contract(changed)

    def test_live_order_module_must_remain_forbidden(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["forbidden_architecture"].remove("live_order_module")
        with self.assertRaisesRegex(MODULE.TechnicalBaselineError, "inventory is incomplete"):
            MODULE.validate_contract(changed)

    def test_quality_gate_cannot_drop_typechecking(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["quality_gates"]["repository"].remove("typecheck")
        with self.assertRaisesRegex(MODULE.TechnicalBaselineError, "quality gate group repository"):
            MODULE.validate_contract(changed)

    def test_kubernetes_cannot_become_an_initial_requirement(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["dependency_policy"]["no_kubernetes_initially"] = False
        with self.assertRaisesRegex(MODULE.TechnicalBaselineError, "no_kubernetes_initially"):
            MODULE.validate_contract(changed)

    def test_next_stage_is_freeze_not_p0_03(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["next_allowed_stage"] = "NEX-P0-03"
        with self.assertRaisesRegex(MODULE.TechnicalBaselineError, "P0-02 freeze"):
            MODULE.validate_contract(changed)

    def test_freeze_record_rejects_a_different_candidate(self) -> None:
        changed = copy.deepcopy(self.freeze_record)
        changed["candidate_commit_sha"] = "0" * 40
        with self.assertRaisesRegex(MODULE.TechnicalBaselineError, "candidate SHA"):
            MODULE.validate_freeze_record(changed, self.contract)

    def test_freeze_record_rejects_wrong_commit_message(self) -> None:
        changed = copy.deepcopy(self.freeze_record)
        changed["candidate_commit_message"] = "chore(nexora): freeze NEX-P0-01 scope contract"
        with self.assertRaisesRegex(MODULE.TechnicalBaselineError, "commit message"):
            MODULE.validate_freeze_record(changed, self.contract)

    def test_freeze_record_requires_both_successful_jobs(self) -> None:
        changed = copy.deepcopy(self.freeze_record)
        changed["github_actions"]["jobs"]["technical_baseline"]["conclusion"] = "failure"
        with self.assertRaisesRegex(MODULE.TechnicalBaselineError, "was not successful"):
            MODULE.validate_freeze_record(changed, self.contract)

    def test_freeze_record_rejects_a_different_job(self) -> None:
        changed = copy.deepcopy(self.freeze_record)
        changed["github_actions"]["jobs"]["technical_baseline"]["job_id"] = 0
        with self.assertRaisesRegex(MODULE.TechnicalBaselineError, "job ID"):
            MODULE.validate_freeze_record(changed, self.contract)

    def test_freeze_record_rejects_contract_drift(self) -> None:
        changed_contract = copy.deepcopy(self.contract)
        changed_contract["technology_baseline"]["server"]["runtime_release_line"] = "3.14.x"
        with self.assertRaisesRegex(MODULE.TechnicalBaselineError, "checksum mismatch"):
            MODULE.validate_freeze_record(self.freeze_record, changed_contract)

    def test_freeze_record_rejects_scope_prerequisite_drift(self) -> None:
        changed = copy.deepcopy(self.freeze_record)
        changed["scope_prerequisite"]["contract_checksum"] = "0" * 64
        with self.assertRaisesRegex(MODULE.TechnicalBaselineError, "scope prerequisite checksum"):
            MODULE.validate_freeze_record(changed, self.contract)

    def test_freeze_record_opens_only_p0_03(self) -> None:
        changed = copy.deepcopy(self.freeze_record)
        changed["next_allowed_stage"] = "NEX-P1-01"
        with self.assertRaisesRegex(MODULE.TechnicalBaselineError, "frozen next stage"):
            MODULE.validate_freeze_record(changed, self.contract)


if __name__ == "__main__":
    unittest.main()
