#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "contracts/nexora-v0.1-human-decision-review.json"
DOMAIN_PATH = ROOT / "contracts/nexora-v0.1-decision-review-journal-domain.json"
SERVICE_PATH = ROOT / "apps/server/src/nexora/decision_review.py"
REPOSITORY_PATH = ROOT / "apps/server/src/nexora/adapters/postgresql/decision_review.py"
MODELS_PATH = ROOT / "apps/server/src/nexora/adapters/postgresql/models.py"
MIGRATION_PATH = ROOT / "alembic/versions/20261116_0012_human_decision_reviews.py"
API_PATH = ROOT / "apps/server/src/nexora/api.py"
WEB_PATH = ROOT / "apps/web/src/components/decision-feed.tsx"


class HumanDecisionReviewContractError(ValueError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise HumanDecisionReviewContractError(message)


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"{path.name} must contain an object")
    return value


def load_contract() -> dict[str, Any]:
    return load_json(CONTRACT_PATH)


def validate_prerequisite() -> None:
    domain = load_json(DOMAIN_PATH)
    require(domain.get("decision_id") == "NEX-P3-01", "P3-01 domain decision drift")
    review = domain.get("human_review")
    require(isinstance(review, dict), "frozen human review domain missing")
    require(review.get("optimistic_concurrency_required") is True, "optimistic concurrency weakened")
    require(review.get("mutation_after_recording") == "forbidden", "review immutability weakened")


def validate_contract(contract: dict[str, Any]) -> None:
    require(contract.get("schema_version") == "nexora-human-decision-review-contract-v1", "schema drift")
    require(contract.get("decision_id") == "NEX-P3-07", "stage ID drift")
    require(contract.get("status") == "candidate", "candidate status drift")
    prerequisite = contract.get("prerequisites")
    require(isinstance(prerequisite, dict), "prerequisite missing")
    require(
        prerequisite.get("p3_06_accepted_commit_sha") == "bf8facf3124822a5d22a57d346a4ed0538a69d7d",
        "accepted P3-06 SHA drift",
    )
    require(contract.get("review_actions") == ["accept", "reject", "defer"], "review actions drift")
    persistence = contract.get("persistence")
    require(isinstance(persistence, dict) and all(persistence.values()), "persistence invariant disabled")
    feedback = contract.get("provider_feedback")
    require(isinstance(feedback, dict), "provider feedback policy missing")
    for key in (
        "local_review_is_source_of_truth",
        "delivery_occurs_after_local_commit",
        "failed_delivery_remains_pending",
        "same_idempotency_key_retries_pending_delivery",
        "exact_decision_evaluation_reference_required",
    ):
        require(feedback.get(key) is True, f"provider feedback invariant disabled: {key}")
    require(feedback.get("secret_or_raw_provider_error_persisted") is False, "provider errors may expose secrets")
    security = contract.get("security_boundary")
    require(isinstance(security, dict) and all(value is False for value in security.values()), "security widened")
    transition = contract.get("transition")
    require(isinstance(transition, dict), "transition missing")
    require(transition.get("next_allowed_stage_after_ci_acceptance") == "NEX-P3-08", "next stage drift")
    require(transition.get("separate_freeze_task_required") is False, "separate Freeze task restored")
    require(transition.get("nex_p3_03_gate_opened") is False, "NEX-P3-03 opened prematurely")


def validate_implementation() -> None:
    paths = (SERVICE_PATH, REPOSITORY_PATH, MODELS_PATH, MIGRATION_PATH, API_PATH, WEB_PATH)
    for path in paths:
        require(path.is_file(), f"implementation file missing: {path.name}")
    for path in paths[:-1]:
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    combined = "\n".join(path.read_text(encoding="utf-8") for path in paths)
    for marker in (
        "DecisionReviewStateRecord",
        "DecisionReviewDeliveryRecord",
        "supersedes_review_id",
        "expected_version",
        "source_evidence_checksum",
        "Idempotency-Key",
        '"/v1/decisions/{decision_id}/reviews"',
        "execution_authorization",
        "order_intent_created",
        "transaction_created",
    ):
        require(marker in combined, f"review behavior missing: {marker}")
    for forbidden in ("exchange_api_key", "wallet_private_key", "fund_transfer(", "submit_order("):
        require(forbidden not in combined, f"forbidden capability present: {forbidden}")


def verify() -> None:
    validate_prerequisite()
    validate_contract(load_contract())
    validate_implementation()


def main() -> int:
    verify()
    print("NEX_P3_06_ACCEPTED_SHA=PASS")
    print("NEX_P3_07_HUMAN_DECISION_REVIEW=PASS")
    print("NEX_P3_07_OPTIMISTIC_CONCURRENCY=PASS")
    print("NEX_P3_07_IDEMPOTENCY=PASS")
    print("NEX_P3_07_EXECUTION_AUTHORIZATION=FORBIDDEN")
    print("NEX_P3_08=BLOCKED_PENDING_P3_07_CI_ACCEPTANCE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
