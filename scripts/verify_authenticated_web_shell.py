#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "contracts/nexora-v0.1-authenticated-web-shell.json"
P1_10_FREEZE_PATH = ROOT / "artifacts/p1-10/artifact-export-storage-freeze.json"
FREEZE_PATH = ROOT / "artifacts/p1-11/authenticated-web-shell-freeze.json"
CONTRACT_CHECKSUM = "94bff81afa14519141972785d665f66ecb3bd0cbe2cb668c4a56ab2bf65f3338"
P1_10_FREEZE_CHECKSUM = "5a91f196a0872aafe9dfdd9ddd023a17375ece08799e6bc19abb9a0cc2273775"
P1_10_FREEZE_COMMIT = "c0a8662a760032d1b9f82777bf3e11f9f2614375"
CANDIDATE_SHA = "a32a4245a306173317556dcc5ecf85c22f1d4308"
CANDIDATE_TREE_SHA = "df9ad34c65e49ba8a4e75db626bb6629ac53b242"
CANDIDATE_MESSAGE = "test(nexora): disambiguate P1-11 browser assertion"
CANDIDATE_PREDECESSOR = "cb59cbeb9a9d23a05298642cd520c07cda059741"


class AuthenticatedWebShellContractError(ValueError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AuthenticatedWebShellContractError(message)


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


def _validate_workflow(
    workflow: object,
    *,
    label: str,
    run_id: int,
    expected_jobs: dict[str, tuple[int, str]],
) -> None:
    _require(isinstance(workflow, dict), f"{label} workflow evidence must be an object")
    _require(workflow.get("run_id") == run_id, f"{label} run ID drift")
    expected_url = f"https://github.com/amirhosseinhamidian/nexora/actions/runs/{run_id}"
    _require(workflow.get("run_url") == expected_url, f"{label} run URL drift")
    _require(workflow.get("head_sha") == CANDIDATE_SHA, f"{label} workflow head SHA drift")
    _require(workflow.get("event") == "push", f"{label} workflow must be a push run")
    _require(workflow.get("attempt") == 1, f"{label} workflow attempt drift")
    _require(workflow.get("conclusion") == "success", f"{label} workflow did not succeed")
    jobs = workflow.get("jobs")
    _require(isinstance(jobs, dict), f"{label} jobs must be an object")
    _require(set(jobs) == set(expected_jobs), f"{label} job inventory mismatch")
    for job_name, (job_id, displayed_name) in expected_jobs.items():
        job = jobs[job_name]
        _require(isinstance(job, dict), f"{label}/{job_name} must be an object")
        _require(job.get("job_id") == job_id, f"{label}/{job_name} job ID drift")
        _require(job.get("name") == displayed_name, f"{label}/{job_name} name drift")
        _require(job.get("conclusion") == "success", f"{label}/{job_name} did not succeed")


def validate_frozen_p1_10() -> None:
    path = ROOT / "scripts/verify_artifact_export_storage.py"
    spec = importlib.util.spec_from_file_location("verify_artifact_export_storage", path)
    if spec is None or spec.loader is None:
        raise AuthenticatedWebShellContractError("unable to load frozen P1-10 verifier")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.validate_frozen_p1_09()
    contract = module.load_contract()
    module.validate_contract(contract)
    module.validate_files_and_runtime_markers()
    module.validate_freeze_record(module.load_freeze_record(), contract)


def validate_contract(contract: dict[str, Any]) -> None:
    _require(contract.get("schema_version") == "nexora-authenticated-web-shell-v1", "invalid schema")
    _require(contract.get("decision_id") == "NEX-P1-11", "invalid decision ID")
    _require(contract.get("decision_date") == "2026-10-27", "invalid decision date")
    _require(contract.get("status") == "candidate", "P1-11 must remain candidate")

    prerequisite = contract.get("p1_10_prerequisite")
    _require(isinstance(prerequisite, dict), "P1-10 prerequisite must be an object")
    _require(prerequisite.get("decision_id") == "NEX-P1-10", "P1-10 prerequisite drift")
    _require(prerequisite.get("frozen") is True, "P1-10 prerequisite is not frozen")
    _require(prerequisite.get("freeze_commit_sha") == P1_10_FREEZE_COMMIT, "P1-10 commit drift")
    _require(
        prerequisite.get("freeze_record_path") == "artifacts/p1-10/artifact-export-storage-freeze.json",
        "P1-10 freeze path drift",
    )
    _require(prerequisite.get("freeze_record_checksum") == P1_10_FREEZE_CHECKSUM, "P1-10 checksum drift")
    _require(canonical_checksum(_json(P1_10_FREEZE_PATH)) == P1_10_FREEZE_CHECKSUM, "P1-10 record drift")
    _require(contract.get("closes_gaps") == ["NEX-P1-GAP-007"], "P1-11 gap ownership drift")

    routes = contract.get("routes")
    _require(isinstance(routes, dict), "routes must be an object")
    _require(routes.get("locales") == ["fa", "en"], "locale inventory drift")
    _require(routes.get("default_locale") == "fa", "default locale drift")
    _require(routes.get("authenticated_shell") == "/{locale}", "shell route drift")
    _require(routes.get("login") == "/{locale}/login", "login route drift")
    _require(routes.get("bootstrap") == "/{locale}/bootstrap", "bootstrap route drift")
    _require(routes.get("portfolio_domain_routes_enabled") is False, "Portfolio routes are deferred")

    identity = contract.get("identity_experience")
    _require(isinstance(identity, dict), "identity experience must be an object")
    _require(identity.get("authentication_method") == "webauthn_passkey", "authentication method drift")
    _require(identity.get("bootstrap_requires_one_time_token") is True, "bootstrap token is required")
    _require(identity.get("recovery_codes_displayed_once") is True, "recovery display policy drift")
    for key in ("password_login", "self_registration", "multi_user", "browser_session_token_storage"):
        _require(identity.get(key) is False, f"identity boundary forbids {key}")
    _require(identity.get("session_cookie") == "__Host-nexora_session", "session cookie drift")
    _require(identity.get("csrf_cookie") == "__Host-nexora_csrf", "CSRF cookie drift")
    _require(identity.get("session_cookie_http_only") is True, "session cookie must remain HttpOnly")
    _require(identity.get("csrf_cookie_http_only") is False, "Web client must be able to read CSRF cookie")
    _require(identity.get("cookies_secure") is True, "cookies must remain Secure")
    _require(identity.get("cookies_same_site") == "strict", "SameSite policy drift")
    _require(identity.get("unsafe_requests_require_csrf") is True, "unsafe requests require CSRF")

    shell = contract.get("application_shell")
    _require(isinstance(shell, dict), "application shell must be an object")
    for key in ("desktop_navigation", "mobile_layout", "rtl_persian", "ltr_english"):
        _require(shell.get(key) is True, f"application shell requires {key}")
    _require(shell.get("themes") == ["dark", "light", "system"], "theme inventory drift")
    _require(shell.get("persian_font") == "Vazirmatn Variable", "Persian font drift")
    _require(shell.get("english_font") == "Inter Variable", "English font drift")
    _require(
        shell.get("states") == ["loading", "authenticated", "empty", "offline", "error", "session_expired"],
        "shell state inventory drift",
    )
    _require(shell.get("deferred_navigation_is_disabled") is True, "deferred navigation must be disabled")

    transport = contract.get("browser_transport")
    _require(isinstance(transport, dict), "browser transport must be an object")
    _require(transport.get("api_prefix") == "/api", "API prefix drift")
    _require(transport.get("credentials_mode") == "same-origin", "credentials mode drift")
    _require(transport.get("cache_mode") == "no-store", "browser cache mode drift")
    for key in ("same_origin_only",):
        _require(transport.get(key) is True, f"browser transport requires {key}")
    for key in ("external_api_target_allowed", "direct_trd_bot_access"):
        _require(transport.get(key) is False, f"browser transport forbids {key}")

    content_security = contract.get("content_security")
    _require(isinstance(content_security, dict), "content security must be an object")
    _require(content_security.get("runtime_nonce") is True, "runtime CSP nonce is required")
    _require(content_security.get("production_unsafe_inline") is False, "unsafe-inline is forbidden")
    _require(content_security.get("production_unsafe_eval") is False, "unsafe-eval is forbidden")
    _require(content_security.get("frame_ancestors") == "none", "frame ancestors policy drift")
    _require(content_security.get("connect_source") == "self", "connect source policy drift")
    _require(content_security.get("authenticated_cache_control") == "no-store", "cache policy drift")

    download = contract.get("authenticated_export_download")
    _require(isinstance(download, dict), "export download must be an object")
    _require(download.get("namespace") == "export", "download namespace drift")
    for key in ("owner_scoped", "authentication_required", "integrity_verified_before_response"):
        _require(download.get(key) is True, f"export download requires {key}")
    for key in ("source_namespace_download", "backup_namespace_download", "public_static_access"):
        _require(download.get(key) is False, f"export download forbids {key}")

    security = contract.get("security_boundary")
    _require(isinstance(security, dict) and security, "security boundary must be an object")
    for capability, enabled in security.items():
        _require(enabled is False, f"forbidden Web capability enabled: {capability}")

    transition = contract.get("transition")
    _require(isinstance(transition, dict), "transition must be an object")
    _require(transition.get("ready_for_freeze") is True, "P1-11 is not ready for freeze")
    _require(transition.get("next_allowed_stage") == "NEX-P1-11-FREEZE", "next stage drift")
    _require(transition.get("post_freeze_stage") == "NEX-P1-12", "post-freeze stage drift")
    _require(canonical_checksum(contract) == CONTRACT_CHECKSUM, "authenticated Web shell contract drift")


def validate_files_and_runtime_markers() -> None:
    required = {
        "apps/web/src/components/auth-panel.tsx": (
            'mode: "bootstrap" | "login"',
            "createPasskeyAssertion",
            "createPasskeyRegistration",
        ),
        "apps/web/src/components/authenticated-shell.tsx": (
            'type ShellState = "authenticated" | "expired" | "loading" | "offline"',
            "SESSION_EXPIRED_EVENT",
            'aria-disabled="true"',
        ),
        "apps/web/src/lib/api-client.ts": (
            'const CSRF_COOKIE = "__Host-nexora_csrf"',
            'credentials: "same-origin"',
            'cache: "no-store"',
            "export async function downloadExport",
        ),
        "apps/web/src/proxy.ts": (
            "'strict-dynamic'",
            "\"connect-src 'self'\"",
            'response.headers.set("Cache-Control", "no-store")',
        ),
        "apps/server/src/nexora/api.py": (
            'CSRF_COOKIE_NAME = "__Host-nexora_csrf"',
            "namespace=ArtifactNamespace.EXPORT",
            '"Content-Disposition": _download_disposition',
        ),
        "infra/caddy/Caddyfile": ("handle_path /api/*", "reverse_proxy api:8000"),
        "apps/web/tests/e2e/authenticated-shell.spec.ts": (
            "Persian authenticated shell is RTL and responsive",
            "English login exposes a passkey-only flow",
            "expired session presents a bounded recovery action",
        ),
        "docs/adr/0025-authenticated-same-origin-web-shell.md": ("Status: Frozen by NEX-P1-11",),
        "docs/v0.1/16-authenticated-web-application-shell.md": (
            "NEX-P1-GAP-007",
            "NEX-P1-11-FREEZE",
            "NEX-P1-12",
        ),
        ".github/workflows/authenticated-web-shell.yml": ("Authenticated Web shell",),
    }
    for relative, markers in required.items():
        path = ROOT / relative
        _require(path.is_file(), f"missing P1-11 file: {relative}")
        content = path.read_text(encoding="utf-8")
        for marker in markers:
            _require(marker in content, f"missing P1-11 marker in {relative}: {marker}")

    client = (ROOT / "apps/web/src/lib/api-client.ts").read_text(encoding="utf-8")
    auth = (ROOT / "apps/web/src/components/auth-panel.tsx").read_text(encoding="utf-8")
    _require("localStorage" not in client + auth, "identity material cannot use localStorage")
    _require("sessionStorage" not in client + auth, "identity material cannot use sessionStorage")
    _require("http://" not in client and "https://" not in client, "browser API targets must remain relative")
    api = (ROOT / "apps/server/src/nexora/api.py").read_text(encoding="utf-8")
    _require("StaticFiles" not in api, "artifact storage cannot be mounted as static files")


def validate_freeze_record(record: dict[str, Any], contract: dict[str, Any]) -> None:
    _require(
        record.get("schema_version") == "nexora-authenticated-web-shell-freeze-v1",
        "invalid freeze schema",
    )
    _require(record.get("decision_id") == "NEX-P1-11", "invalid freeze decision ID")
    _require(record.get("repository") == "amirhosseinhamidian/nexora", "repository drift")
    _require(record.get("candidate_commit_sha") == CANDIDATE_SHA, "candidate SHA drift")
    _require(record.get("candidate_tree_sha") == CANDIDATE_TREE_SHA, "candidate tree drift")
    _require(record.get("candidate_commit_message") == CANDIDATE_MESSAGE, "commit message drift")
    _require(record.get("candidate_predecessor_sha") == CANDIDATE_PREDECESSOR, "candidate parent drift")

    primary = record.get("github_actions")
    _validate_workflow(
        primary,
        label="authenticated Web shell",
        run_id=40577080839,
        expected_jobs={
            "backend": (122446281761, "backend"),
            "browser": (122446282222, "browser"),
            "web_shell_contract": (122446282290, "web-shell-contract"),
            "web": (122446282422, "web"),
        },
    )
    _require(primary.get("head_branch") == "feature/v0.1-foundation", "primary workflow branch drift")
    required_markers = {
        "backend": (
            "locked_dependencies_installed",
            "format_passed",
            "lint_passed",
            "typecheck_passed",
            "backend_and_repository_tests_passed",
            "generated_contracts_checked",
        ),
        "browser": (
            "locked_dependencies_installed",
            "chromium_installed",
            "browser_lifecycle_tests_passed",
        ),
        "web_shell_contract": (
            "p1_10_freeze_prerequisite_passed",
            "web_shell_verifier_passed",
            "repository_contract_tests_passed",
        ),
        "web": (
            "locked_dependencies_installed",
            "format_passed",
            "lint_passed",
            "typecheck_passed",
            "unit_tests_passed",
            "production_build_passed",
        ),
    }
    for job_name, markers in required_markers.items():
        for marker in markers:
            _require(primary["jobs"][job_name].get(marker) is True, f"{job_name} did not confirm {marker}")

    regression = record.get("regression_workflows")
    _require(isinstance(regression, dict), "regression workflow evidence must be an object")
    expected_regression = {
        "application_composition": (
            40577080617,
            {
                "backend": (122446281586, "backend"),
                "composition_contract": (122446282093, "composition-contract"),
            },
        ),
        "single_owner_identity_runtime": (
            40577080997,
            {
                "backend": (122446281970, "backend"),
                "postgresql_17": (122446282493, "postgresql-17"),
                "identity_contract": (122446282499, "identity-contract"),
                "private_topology": (122446282630, "private-topology"),
            },
        ),
        "trd_bot_adapter": (
            40577080700,
            {
                "adapter_contract": (122446281505, "adapter-contract"),
                "backend": (122446281979, "backend"),
            },
        ),
        "contracts": (
            40577080823,
            {
                "technical_baseline": (122446282280, "technical-baseline"),
                "integration_contract": (122446282676, "integration-contract"),
                "scope_contract": (122446282729, "scope-contract"),
                "security_boundary": (122446282739, "security-boundary"),
                "phase_zero_acceptance": (122446282803, "phase-zero-acceptance"),
            },
        ),
        "runtime_foundation": (
            40577080952,
            {
                "web": (122446282184, "web"),
                "backend": (122446282593, "backend"),
                "foundation_contract": (122446282792, "foundation-contract"),
            },
        ),
        "runtime_api_auth": (
            40577080648,
            {
                "postgresql_17": (122446281132, "postgresql-17"),
                "cross_language_contract": (122446281702, "cross-language-contract"),
                "backend": (122446281853, "backend"),
                "runtime_contract": (122446281884, "runtime-contract"),
            },
        ),
        "audit_observability": (
            40577080614,
            {
                "observability_contract": (122446281664, "observability-contract"),
                "backend": (122446282215, "backend"),
                "postgresql_17": (122446282272, "postgresql-17"),
            },
        ),
        "durable_jobs_outbox": (
            40577080663,
            {
                "backend": (122446281575, "backend"),
                "durable_contract": (122446282062, "durable-contract"),
                "postgresql_17": (122446282128, "postgresql-17"),
            },
        ),
        "trd_bot_sync_runtime": (
            40577080838,
            {
                "postgresql_17": (122446282162, "postgresql-17"),
                "sync_contract": (122446282517, "sync-contract"),
                "backend": (122446283025, "backend"),
            },
        ),
        "artifact_export_storage": (
            40577080965,
            {
                "storage_contract": (122446282727, "storage-contract"),
                "storage_runtime": (122446282971, "storage-runtime"),
                "backend": (122446283131, "backend"),
            },
        ),
        "postgresql_schema": (
            40577080915,
            {
                "backend": (122446282301, "backend"),
                "postgresql_17": (122446282694, "postgresql-17"),
                "database_contract": (122446282698, "database-contract"),
            },
        ),
        "phase_one_readiness": (
            40577081070,
            {
                "backend": (122446283216, "backend"),
                "web": (122446283808, "web"),
                "readiness_contract": (122446283810, "readiness-contract"),
            },
        ),
    }
    _require(set(regression) == set(expected_regression), "regression workflow inventory mismatch")
    for label, (run_id, jobs) in expected_regression.items():
        _validate_workflow(regression[label], label=label, run_id=run_id, expected_jobs=jobs)

    evidence = record.get("authenticated_web_shell_contract")
    _require(isinstance(evidence, dict), "authenticated Web shell evidence must be an object")
    _require(evidence.get("schema_version") == contract.get("schema_version"), "contract schema mismatch")
    _require(
        evidence.get("path") == "contracts/nexora-v0.1-authenticated-web-shell.json",
        "contract path drift",
    )
    _require(evidence.get("checksum") == CONTRACT_CHECKSUM, "recorded contract checksum drift")
    _require(evidence.get("checksum") == canonical_checksum(contract), "contract checksum mismatch")

    prerequisite = record.get("p1_10_prerequisite")
    _require(isinstance(prerequisite, dict), "P1-10 prerequisite must be an object")
    _require(prerequisite.get("decision_id") == "NEX-P1-10", "P1-10 prerequisite decision drift")
    _require(prerequisite.get("frozen") is True, "P1-10 prerequisite is not frozen")
    _require(prerequisite.get("freeze_commit_sha") == P1_10_FREEZE_COMMIT, "P1-10 freeze commit drift")
    _require(
        prerequisite.get("freeze_record_path") == "artifacts/p1-10/artifact-export-storage-freeze.json",
        "P1-10 path drift",
    )
    _require(
        prerequisite.get("freeze_record_checksum")
        == canonical_checksum(_json(P1_10_FREEZE_PATH))
        == P1_10_FREEZE_CHECKSUM,
        "P1-10 freeze checksum mismatch",
    )

    _require(record.get("recorded_on") == "2026-10-27", "invalid freeze record date")
    _require(record.get("frozen") is True, "P1-11 is not frozen")
    _require(record.get("closed_gaps") == ["NEX-P1-GAP-007"], "frozen gap inventory drift")
    for key in (
        "production_readiness_claimed",
        "public_internet_profile",
        "public_artifact_access",
        "password_authentication",
        "session_token_in_browser_storage",
        "direct_trd_bot_database_access",
        "live_execution_capability",
        "exchange_credentials",
        "wallet_capability",
        "autonomous_ai_execution",
    ):
        _require(record.get(key) is False, f"freeze record cannot enable {key}")
    _require(record.get("next_allowed_stage") == "NEX-P1-12", "post-freeze stage drift")


def main() -> int:
    validate_frozen_p1_10()
    contract = load_contract()
    validate_contract(contract)
    validate_files_and_runtime_markers()
    validate_freeze_record(load_freeze_record(), contract)
    print(f"schema_version={contract['schema_version']}")
    print(f"decision_id={contract['decision_id']}")
    print(f"contract_checksum={canonical_checksum(contract)}")
    print("NEX_P1_10_PREREQUISITE=PASS")
    print("NEX_P1_11_AUTHENTICATED_WEB_SHELL=PASS")
    print(f"candidate_commit_sha={CANDIDATE_SHA}")
    print("NEX_P1_11_FREEZE=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
