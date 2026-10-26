from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from nexora.identity import (
    SESSION_COOKIE_NAME,
    TRD_BOT_SCOPES,
    AuthenticationDenied,
    CeremonyUnavailable,
    DenyAllWebAuthnVerifier,
    IssuedSession,
    StandardWebAuthnVerifier,
    VerifiedCredential,
    ip_address_hmac,
    random_token,
    secret_matches,
    token_digest,
    validate_service_scopes,
    verify_exact_origin,
)


def test_tokens_have_required_entropy_and_only_digest_is_compared() -> None:
    token = random_token()
    assert len(token) >= 43
    assert len(token_digest(token)) == 64
    assert secret_matches(token, token_digest(token)) is True
    assert secret_matches(f"{token}x", token_digest(token)) is False


def test_session_cookie_has_frozen_host_only_attributes() -> None:
    issued = IssuedSession(
        session_id=uuid4(),
        owner_id=uuid4(),
        token=random_token(),
        csrf_token=random_token(),
        idle_expires_at=datetime.now(UTC),
        absolute_expires_at=datetime.now(UTC),
    )
    assert issued.set_cookie_value.startswith(f"{SESSION_COOKIE_NAME}=")
    assert "; Path=/; Secure; HttpOnly; SameSite=Strict" in issued.set_cookie_value
    assert "Domain=" not in issued.set_cookie_value


def test_exact_origin_and_service_scope_validation_fail_closed() -> None:
    verify_exact_origin("https://nexora.private", "https://nexora.private")
    with pytest.raises(AuthenticationDenied):
        verify_exact_origin("https://attacker.invalid", "https://nexora.private")
    validate_service_scopes(frozenset({"source.event.read"}))
    with pytest.raises(AuthenticationDenied):
        validate_service_scopes(frozenset({"live.order.write"}))
    assert "live.order.write" not in TRD_BOT_SCOPES


def test_verified_credential_is_bounded_and_default_verifier_denies() -> None:
    credential = VerifiedCredential(
        credential_id="credential-id-1234",
        public_key=b"p" * 64,
        algorithm="ES256",
        sign_count=0,
        transports=("internal",),
    )
    assert credential.algorithm == "ES256"
    with pytest.raises(CeremonyUnavailable):
        DenyAllWebAuthnVerifier().verify_registration(
            response_json="{}",
            expected_challenge="challenge",
            expected_origin="https://nexora.private",
            expected_rp_id="nexora.private",
        )
    with pytest.raises(AuthenticationDenied, match="registration response"):
        StandardWebAuthnVerifier().verify_registration(
            response_json="{}",
            expected_challenge="Y2hhbGxlbmdl",
            expected_origin="https://nexora.private",
            expected_rp_id="nexora.private",
        )


def test_ip_address_audit_value_is_pseudonymized() -> None:
    first = ip_address_hmac("10.0.0.1", "p" * 43)
    second = ip_address_hmac("10.0.0.1", "p" * 43)
    assert first == second and len(first) == 64
    assert "10.0.0.1" not in first
