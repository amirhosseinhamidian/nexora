from __future__ import annotations

import hashlib
import hmac
import json
import secrets
from dataclasses import dataclass
from datetime import datetime
from typing import Final, Protocol
from uuid import UUID

from webauthn import verify_authentication_response, verify_registration_response
from webauthn.helpers import base64url_to_bytes, bytes_to_base64url, decode_credential_public_key
from webauthn.helpers.cose import COSEAlgorithmIdentifier
from webauthn.helpers.exceptions import WebAuthnException

SESSION_COOKIE_NAME: Final = "__Host-nexora_session"
SESSION_IDLE_SECONDS: Final = 1800
SESSION_ABSOLUTE_SECONDS: Final = 43200
SESSION_ROTATION_SECONDS: Final = 900
SESSION_ROTATION_GRACE_SECONDS: Final = 30
MAXIMUM_CONCURRENT_SESSIONS: Final = 5
CHALLENGE_TTL_SECONDS: Final = 300
BOOTSTRAP_TTL_SECONDS: Final = 600
RECOVERY_CODE_COUNT: Final = 10
SERVICE_TOKEN_MAXIMUM_AGE_DAYS: Final = 90
ALLOWED_WEBAUTHN_ALGORITHMS: Final = frozenset({"ES256", "EdDSA"})
TRD_BOT_SCOPES: Final = frozenset(
    {
        "source.snapshot.read",
        "source.event.read",
        "source.export.create",
        "source.export.read",
        "decision_review.write_paper_shadow",
    }
)


class IdentityError(ValueError):
    """Base error for fail-closed identity operations."""


class AuthenticationDenied(IdentityError):
    pass


class CeremonyUnavailable(IdentityError):
    pass


@dataclass(frozen=True, slots=True)
class VerifiedCredential:
    credential_id: str
    public_key: bytes
    algorithm: str
    sign_count: int
    transports: tuple[str, ...]

    def __post_init__(self) -> None:
        if len(self.credential_id) < 16 or len(self.credential_id) > 1024:
            raise IdentityError("verified credential ID length is invalid")
        if not 32 <= len(self.public_key) <= 4096:
            raise IdentityError("verified credential public key length is invalid")
        if self.algorithm not in ALLOWED_WEBAUTHN_ALGORITHMS:
            raise IdentityError("verified credential algorithm is forbidden")
        if self.sign_count < 0:
            raise IdentityError("verified credential counter is invalid")


@dataclass(frozen=True, slots=True)
class VerifiedAssertion:
    credential_id: str
    sign_count: int


class WebAuthnCeremonyVerifier(Protocol):
    def verify_registration(
        self,
        *,
        response_json: str,
        expected_challenge: str,
        expected_origin: str,
        expected_rp_id: str,
    ) -> VerifiedCredential: ...

    def verify_authentication(
        self,
        *,
        response_json: str,
        expected_challenge: str,
        expected_origin: str,
        expected_rp_id: str,
        credential: VerifiedCredential,
    ) -> VerifiedAssertion: ...


class DenyAllWebAuthnVerifier:
    """Safe default until an audited WebAuthn cryptographic adapter is injected."""

    def verify_registration(self, **_: str) -> VerifiedCredential:
        raise CeremonyUnavailable("WebAuthn cryptographic verifier is not configured")

    def verify_authentication(self, **_: object) -> VerifiedAssertion:
        raise CeremonyUnavailable("WebAuthn cryptographic verifier is not configured")


class StandardWebAuthnVerifier:
    """Cryptographic WebAuthn verifier restricted to the frozen ES256/EdDSA policy."""

    def verify_registration(
        self,
        *,
        response_json: str,
        expected_challenge: str,
        expected_origin: str,
        expected_rp_id: str,
    ) -> VerifiedCredential:
        try:
            result = verify_registration_response(
                credential=response_json,
                expected_challenge=base64url_to_bytes(expected_challenge),
                expected_origin=expected_origin,
                expected_rp_id=expected_rp_id,
                require_user_presence=True,
                require_user_verification=True,
                supported_pub_key_algs=[
                    COSEAlgorithmIdentifier.ECDSA_SHA_256,
                    COSEAlgorithmIdentifier.EDDSA,
                ],
            )
            decoded_key = decode_credential_public_key(result.credential_public_key)
        except (WebAuthnException, ValueError, TypeError, json.JSONDecodeError) as error:
            raise AuthenticationDenied("WebAuthn registration response is invalid") from error
        algorithm = {
            COSEAlgorithmIdentifier.ECDSA_SHA_256: "ES256",
            COSEAlgorithmIdentifier.EDDSA: "EdDSA",
        }.get(decoded_key.alg)
        if algorithm is None or not result.user_verified:
            raise AuthenticationDenied("WebAuthn registration policy was not satisfied")
        transports = _registration_transports(response_json)
        return VerifiedCredential(
            credential_id=bytes_to_base64url(result.credential_id),
            public_key=result.credential_public_key,
            algorithm=algorithm,
            sign_count=result.sign_count,
            transports=transports,
        )

    def verify_authentication(
        self,
        *,
        response_json: str,
        expected_challenge: str,
        expected_origin: str,
        expected_rp_id: str,
        credential: VerifiedCredential,
    ) -> VerifiedAssertion:
        try:
            result = verify_authentication_response(
                credential=response_json,
                expected_challenge=base64url_to_bytes(expected_challenge),
                expected_origin=expected_origin,
                expected_rp_id=expected_rp_id,
                credential_public_key=credential.public_key,
                credential_current_sign_count=credential.sign_count,
                require_user_verification=True,
            )
        except (WebAuthnException, ValueError, TypeError, json.JSONDecodeError) as error:
            raise AuthenticationDenied("WebAuthn authentication response is invalid") from error
        credential_id = bytes_to_base64url(result.credential_id)
        if not result.user_verified or not hmac.compare_digest(credential_id, credential.credential_id):
            raise AuthenticationDenied("WebAuthn authentication policy was not satisfied")
        return VerifiedAssertion(credential_id=credential_id, sign_count=result.new_sign_count)


@dataclass(frozen=True, slots=True)
class IssuedSession:
    session_id: UUID
    owner_id: UUID
    token: str
    csrf_token: str
    idle_expires_at: datetime
    absolute_expires_at: datetime

    @property
    def set_cookie_value(self) -> str:
        return f"{SESSION_COOKIE_NAME}={self.token}; Path=/; Secure; HttpOnly; SameSite=Strict"


@dataclass(frozen=True, slots=True)
class AuthenticatedSession:
    session_id: UUID
    owner_id: UUID
    rotation_required: bool


def random_token(*, bytes_count: int = 32) -> str:
    if bytes_count < 16:
        raise ValueError("security token entropy cannot be below 128 bits")
    return secrets.token_urlsafe(bytes_count)


def token_digest(token: str) -> str:
    if not token or any(character.isspace() for character in token):
        raise AuthenticationDenied("credential representation is invalid")
    return hashlib.sha256(token.encode()).hexdigest()


def secret_matches(token: str, expected_digest: str) -> bool:
    try:
        actual = token_digest(token)
    except AuthenticationDenied:
        return False
    return hmac.compare_digest(actual, expected_digest)


def verify_exact_origin(origin: str | None, expected_origin: str) -> None:
    if origin is None or not hmac.compare_digest(origin, expected_origin):
        raise AuthenticationDenied("request origin is not allowed")


def ip_address_hmac(address: str, pepper: str) -> str:
    if not address or not pepper:
        raise ValueError("IP address HMAC input cannot be empty")
    return hmac.new(pepper.encode(), address.encode(), hashlib.sha256).hexdigest()


def validate_service_scopes(scopes: frozenset[str]) -> None:
    if not scopes or not scopes.issubset(TRD_BOT_SCOPES):
        raise AuthenticationDenied("service token scopes are invalid")
    if any("live" in scope or "wallet" in scope or "exchange" in scope for scope in scopes):
        raise AuthenticationDenied("live, wallet, and exchange credential scopes are forbidden")


def _registration_transports(response_json: str) -> tuple[str, ...]:
    try:
        payload = json.loads(response_json)
    except json.JSONDecodeError as error:
        raise AuthenticationDenied("WebAuthn registration response is invalid") from error
    if not isinstance(payload, dict):
        return ()
    response = payload.get("response")
    if not isinstance(response, dict):
        return ()
    transports = response.get("transports", [])
    if not isinstance(transports, list) or not all(isinstance(item, str) for item in transports):
        raise AuthenticationDenied("WebAuthn transports are invalid")
    allowed = {"ble", "hybrid", "internal", "nfc", "usb"}
    if not set(transports).issubset(allowed):
        raise AuthenticationDenied("WebAuthn transport is unsupported")
    return tuple(sorted(set(transports)))
