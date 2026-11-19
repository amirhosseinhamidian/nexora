#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "contracts/nexora-v0.1-experience-hardening-ui.json"
PREREQUISITE_PATH = ROOT / "artifacts/p4-09/exports-settings-ui-freeze.json"
TOKENS_PATH = ROOT / "packages/ui/src/tokens.css"
PREREQUISITE_CHECKSUM = "142d49d36483801bd1089d84756abfb681c74b7bc214f5f159a9103270f5d943"
CONTRACT_CHECKSUM = "cf476b87530f1028cb1bb531dc0ab2aaebca0808b5f735ec24066329087da2d6"

TEXT_PAIRS = (
    ("text", "surface"),
    ("text-muted", "bg"),
    ("text-muted", "surface-raised"),
    ("primary-strong", "primary-soft"),
    ("warning", "warning-soft"),
    ("danger", "danger-soft"),
    ("info", "info-soft"),
    ("danger-on", "danger"),
)
CONTROL_PAIRS = (
    ("control-border", "surface"),
    ("control-border", "surface-raised"),
    ("focus", "bg"),
    ("focus", "primary-soft"),
)


class ExperienceHardeningUiContractError(ValueError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ExperienceHardeningUiContractError(message)


def load_contract(path: Path = CONTRACT_PATH) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    _require(isinstance(value, dict), f"{path.name} must contain an object")
    return value


def canonical_checksum(document: dict[str, Any]) -> str:
    encoded = json.dumps(document, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode()
    return hashlib.sha256(encoded).hexdigest()


def validate_prerequisite() -> None:
    record = load_contract(PREREQUISITE_PATH)
    _require(canonical_checksum(record) == PREREQUISITE_CHECKSUM, "P4-09 Freeze checksum drift")
    _require(record.get("frozen") is True, "P4-09 is not frozen")
    _require(record.get("next_allowed_stage") == "NEX-P4-10", "P4-10 is not open")


def validate_contract(contract: dict[str, Any]) -> None:
    _require(contract.get("schema_version") == "nexora-experience-hardening-ui-v1", "schema drift")
    _require(contract.get("decision_id") == "NEX-P4-10" and contract.get("status") == "candidate", "decision drift")
    _require(
        contract.get("p4_09_prerequisite")
        == {
            "freeze_commit_sha": "86c013131de77e036e0a8b81c98ea8a2644b6891",
            "freeze_record_path": PREREQUISITE_PATH.relative_to(ROOT).as_posix(),
            "freeze_record_checksum": PREREQUISITE_CHECKSUM,
            "successful_ci_run_id": 44490292631,
        },
        "P4-09 prerequisite drift",
    )
    _require(
        contract.get("transition") == {"next_allowed_stage": "NEX-P4-10-FREEZE", "post_freeze_stage": "NEX-P4-11"},
        "stage transition drift",
    )
    _require(canonical_checksum(contract) == CONTRACT_CHECKSUM, "P4-10 contract checksum drift")


def _luminance(color: str) -> float:
    channels = [int(color[index : index + 2], 16) / 255 for index in (0, 2, 4)]
    linear = [value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4 for value in channels]
    return sum(value * weight for value, weight in zip(linear, (0.2126, 0.7152, 0.0722), strict=True))


def validate_contrast(contract: dict[str, Any], stylesheet: str) -> None:
    for theme, selector in (("light", ":root"), ("dark", '[data-theme="dark"]')):
        rule = re.search(rf"{re.escape(selector)}\s*\{{([^}}]+)\}}", stylesheet)
        _require(rule is not None, f"{theme} palette missing")
        if rule is None:
            continue
        tokens = dict(re.findall(r"--nx-([\w-]+):\s*#([a-f0-9]{6});", rule.group(1)))
        presentation = contract["presentation"]
        for pairs, minimum in (
            (TEXT_PAIRS, presentation["text_token_contrast_min"]),
            (CONTROL_PAIRS, presentation["control_token_contrast_min"]),
        ):
            for foreground, background in pairs:
                label = f"{theme} {foreground}/{background}"
                _require(foreground in tokens and background in tokens, f"{label} token missing")
                lower, higher = sorted((_luminance(tokens[foreground]), _luminance(tokens[background])))
                ratio = (higher + 0.05) / (lower + 0.05)
                _require(ratio >= minimum, f"{label} contrast {ratio:.2f} is below {minimum}")


def _message_shape(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _message_shape(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_message_shape(item) for item in value]
    return type(value)


def validate_copy(english: dict[str, Any], persian: dict[str, Any]) -> None:
    _require(_message_shape(english) == _message_shape(persian), "translation message keys or types drift")
    _require(persian["portfolioOperations"]["tabs"]["journal"] == "دفتر تراکنش", "accounting journal wording drift")
    _require(persian["navigation"]["journal"] == "دفتر نتایج", "outcome journal wording drift")
    _require("کلید عبور" in persian["auth"]["loginTitle"], "passkey wording drift")


def validate_runtime_markers(contract: dict[str, Any]) -> None:
    web = ROOT / "apps/web/src"
    components = web / "components"
    ui = ROOT / "packages/ui/src"
    widths = ", ".join(str(width) for width in contract["presentation"]["viewport_widths_px"])
    for path, markers in (
        (components / "authenticated-shell.tsx", ("previousPath.current", 'getElementById("main-content")?.focus')),
        (components / "foundation-controls.tsx", ("useSearchParams().toString()", "localePath}?")),
        (components / "auth-panel.tsx", ('className="skip-link"', "bootstrapTokenHint")),
        (web / "app/[locale]/loading.tsx", ("useParams", "copy.loadingDescription")),
        (web / "app/[locale]/not-found.tsx", ("useParams", "copy.notFoundTitle")),
        (web / "styles/base.css", ("unicode-bidi:isolate", "wrap-anywhere")),
        (ui / "primitives/form-field.tsx", ('"aria-describedby"', '"aria-invalid"')),
        (
            ui / "primitives/dialog.tsx",
            ("suspendBackground", 'setAttribute("inert"', "keepFocusInside", "previouslyFocused?.focus()"),
        ),
        (ui / "primitives/table.tsx", ('className="nx-table-scroll"', "aria-labelledby={labelledBy}", "captionId")),
        (ui / "styles/controls.css", ("pointer: coarse", "outline-nx-focus", "border-nx-control-border")),
        (ui / "styles/overlays.css", ("100dvh", "--nx-tooltip-offset")),
        (ui / "styles/motion-and-responsive.css", ("prefers-reduced-motion: reduce", "transform-none")),
        (
            ROOT / "apps/web/tests/e2e/authenticated-shell.spec.ts",
            (
                f"[{widths}]",
                "workspace audit",
                "document.documentElement.scrollWidth",
                "language switch keeps a journal link",
            ),
        ),
    ):
        source = path.read_text(encoding="utf-8")
        for marker in markers:
            _require(marker in source, f"P4-10 runtime marker missing from {path.name}: {marker}")


def main() -> int:
    contract = load_contract()
    validate_prerequisite()
    validate_contract(contract)
    validate_copy(
        load_contract(ROOT / "apps/web/messages/en.json"),
        load_contract(ROOT / "apps/web/messages/fa.json"),
    )
    validate_contrast(contract, TOKENS_PATH.read_text(encoding="utf-8"))
    validate_runtime_markers(contract)
    print(f"decision_id={contract['decision_id']}")
    print(f"contract_checksum={CONTRACT_CHECKSUM}")
    print("NEX_P4_09_PREREQUISITE=PASS")
    print("NEX_P4_10_EXPERIENCE_HARDENING_UI_CANDIDATE=PASS")
    print("NEX_P4_10_FREEZE=PENDING_SAME_SHA_CI")
    print("NEX_P4_11=BLOCKED_PENDING_P4_10_FREEZE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
