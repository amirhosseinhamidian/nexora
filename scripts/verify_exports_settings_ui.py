#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "contracts/nexora-v0.1-exports-settings-ui.json"
PREREQUISITE_PATH = ROOT / "artifacts/p4-08/monitoring-experience-ui-freeze.json"
PREREQUISITE_CHECKSUM = "225a153858bfd377d9bd6f6691770d7e4eedb7be2e7634ea68ca9790a6b4ef92"
CONTRACT_CHECKSUM = "d0e0077c92f3c02399fc01647b531b1c2d75c58f32a9ae7e9c8d4cb2ccb63930"


class ExportsSettingsUiContractError(ValueError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ExportsSettingsUiContractError(message)


def load_contract(path: Path = CONTRACT_PATH) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    _require(isinstance(value, dict), f"{path.name} must contain an object")
    return value


def canonical_checksum(document: dict[str, Any]) -> str:
    encoded = json.dumps(document, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode()
    return hashlib.sha256(encoded).hexdigest()


def validate_prerequisite() -> None:
    record = load_contract(PREREQUISITE_PATH)
    _require(canonical_checksum(record) == PREREQUISITE_CHECKSUM, "P4-08 Freeze checksum drift")
    _require(record.get("frozen") is True, "P4-08 is not frozen")
    _require(record.get("next_allowed_stage") == "NEX-P4-09", "P4-09 is not open")


def validate_contract(contract: dict[str, Any]) -> None:
    _require(contract.get("schema_version") == "nexora-exports-settings-ui-v1", "schema drift")
    _require(contract.get("decision_id") == "NEX-P4-09" and contract.get("status") == "candidate", "decision drift")
    _require(
        contract.get("p4_08_prerequisite")
        == {
            "freeze_commit_sha": "c10ecffd33a3b12bfce61b7f10da31a3719e6fea",
            "freeze_record_path": PREREQUISITE_PATH.relative_to(ROOT).as_posix(),
            "freeze_record_checksum": PREREQUISITE_CHECKSUM,
            "successful_ci_run_id": 44484280599,
        },
        "P4-08 prerequisite drift",
    )
    export = contract.get("export", {})
    _require(export.get("public_download") is False, "public downloads are excluded")
    _require(export.get("downloads_verify_sha256_and_size") is True, "artifact verification is required")
    _require(
        contract.get("transition") == {"next_allowed_stage": "NEX-P4-09-FREEZE", "post_freeze_stage": "NEX-P4-10"},
        "stage transition drift",
    )
    _require(canonical_checksum(contract) == CONTRACT_CHECKSUM, "P4-09 contract checksum drift")


def validate_runtime_markers(contract: dict[str, Any]) -> None:
    api = load_contract(ROOT / "contracts/runtime/v1/openapi.json")
    export = contract["export"]
    _require(
        api["paths"][export["create_path"]]["post"]["operationId"] == export["create_operation"],
        "export operation drift",
    )
    _require(
        api["paths"]["/v1/decisions"]["get"]["operationId"] == contract["settings"]["provider_status_operation"],
        "provider status operation drift",
    )
    for schema, key in (("PortfolioExportProfile", "profiles"), ("PortfolioExportFormat", "formats")):
        _require(set(api["components"]["schemas"][schema]["enum"]) == set(export[key]), f"export {key} drift")

    web = ROOT / "apps/web/src"
    components = web / "components"
    for route in contract["routes"]:
        section = route.removeprefix("/{locale}/")
        source = (web / f"app/[locale]/(workspace)/{section}/page.tsx").read_text(encoding="utf-8")
        _require(f'section="{section}"' in source, f"P4-09 route drift: {route}")

    for path, markers in (
        (
            ROOT / "apps/server/src/nexora/api.py",
            (export["authenticated_download_path"], '"X-Artifact-SHA256"', "namespace=ArtifactNamespace.EXPORT"),
        ),
        (
            web / "lib/api-client.ts",
            ('credentials: "same-origin"', 'redirect: "error"', 'crypto.subtle.digest("SHA-256"', "blob.size"),
        ),
        (
            web / "lib/portfolio-exports.ts",
            ("/api/v1/portfolio-exports", "nexora-export-receipts-v1:", "maxHistory = 20", "manifest.public_download"),
        ),
        (
            components / "exports-workspace.tsx",
            ("<ConfirmationDialog", "<ExportHistory", "expected:", "downloadExport"),
        ),
        (
            components / "settings-workspace.tsx",
            ("rememberLocale", "setTheme", "displayTimeZones", "watchlistsHref(locale)", "decisionFeedPage"),
        ),
        (components / "authenticated-shell.tsx", ("<WorkspaceTimeZone.Provider", "writeDisplayPreferences")),
        (
            web / "proxy.ts",
            ("LOCALE_PREFERENCE_COOKIE", "entryLocale", 'response.headers.set("Cache-Control", "no-store")'),
        ),
    ):
        source = path.read_text(encoding="utf-8")
        for marker in markers:
            _require(marker in source, f"P4-09 runtime marker missing from {path.name}: {marker}")

    english, persian = (load_contract(ROOT / f"apps/web/messages/{locale}.json") for locale in ("en", "fa"))
    for section in ("exports", "settings"):
        _require(english[section].keys() == persian[section].keys(), f"{section} translations drift")


def main() -> int:
    contract = load_contract()
    validate_prerequisite()
    validate_contract(contract)
    validate_runtime_markers(contract)
    print(f"decision_id={contract['decision_id']}")
    print(f"contract_checksum={CONTRACT_CHECKSUM}")
    print("NEX_P4_08_PREREQUISITE=PASS")
    print("NEX_P4_09_EXPORTS_SETTINGS_UI_CANDIDATE=PASS")
    print("NEX_P4_09_FREEZE=PENDING_SAME_SHA_CI")
    print("NEX_P4_10=BLOCKED_PENDING_P4_09_FREEZE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
