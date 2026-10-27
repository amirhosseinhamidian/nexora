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
CONTRACT_CHECKSUM = "94bff81afa14519141972785d665f66ecb3bd0cbe2cb668c4a56ab2bf65f3338"
P1_10_FREEZE_CHECKSUM = "5a91f196a0872aafe9dfdd9ddd023a17375ece08799e6bc19abb9a0cc2273775"
P1_10_FREEZE_COMMIT = "c0a8662a760032d1b9f82777bf3e11f9f2614375"


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
        "docs/adr/0025-authenticated-same-origin-web-shell.md": ("Status: Candidate for NEX-P1-11",),
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


def main() -> int:
    validate_frozen_p1_10()
    contract = load_contract()
    validate_contract(contract)
    validate_files_and_runtime_markers()
    print(f"schema_version={contract['schema_version']}")
    print(f"decision_id={contract['decision_id']}")
    print(f"contract_checksum={canonical_checksum(contract)}")
    print("NEX_P1_10_PREREQUISITE=PASS")
    print("NEX_P1_11_AUTHENTICATED_WEB_SHELL=PASS")
    print("NEX_P1_11_READY_FOR_FREEZE=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
