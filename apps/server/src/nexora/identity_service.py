from __future__ import annotations

from uuid import UUID

from nexora.adapters.postgresql.identity import PostgreSQLIdentityRepository
from nexora.identity import IssuedSession, WebAuthnCeremonyVerifier
from nexora.security_config import SecuritySettings


class OwnerIdentityService:
    """Coordinates verified WebAuthn ceremonies with single-use durable state."""

    def __init__(
        self,
        repository: PostgreSQLIdentityRepository,
        verifier: WebAuthnCeremonyVerifier,
        settings: SecuritySettings,
    ) -> None:
        self._repository = repository
        self._verifier = verifier
        self._settings = settings

    def create_local_bootstrap_token(self) -> str:
        return self._repository.create_bootstrap_token()

    def complete_initial_registration(
        self,
        *,
        bootstrap_token: str,
        response_json: str,
    ) -> tuple[UUID, tuple[str, ...]]:
        credential = self._verifier.verify_registration(
            response_json=response_json,
            expected_challenge=bootstrap_token,
            expected_origin=self._settings.canonical_origin,
            expected_rp_id=self._settings.rp_id,
        )
        return self._repository.complete_bootstrap(
            bootstrap_token=bootstrap_token,
            credential=credential,
        )

    def begin_registration(self, *, owner_id: UUID) -> str:
        return self._repository.issue_challenge(owner_id=owner_id, purpose="registration")

    def complete_registration(
        self,
        *,
        owner_id: UUID,
        challenge: str,
        response_json: str,
    ) -> None:
        credential = self._verifier.verify_registration(
            response_json=response_json,
            expected_challenge=challenge,
            expected_origin=self._settings.canonical_origin,
            expected_rp_id=self._settings.rp_id,
        )
        self._repository.consume_challenge(
            owner_id=owner_id,
            purpose="registration",
            challenge=challenge,
        )
        self._repository.enroll_credential(owner_id=owner_id, credential=credential)

    def begin_authentication(self, *, owner_id: UUID) -> str:
        return self._repository.issue_challenge(owner_id=owner_id, purpose="authentication")

    def complete_authentication(
        self,
        *,
        owner_id: UUID,
        credential_id: str,
        challenge: str,
        response_json: str,
    ) -> IssuedSession:
        credential = self._repository.get_active_credential(
            owner_id=owner_id,
            credential_id=credential_id,
        )
        assertion = self._verifier.verify_authentication(
            response_json=response_json,
            expected_challenge=challenge,
            expected_origin=self._settings.canonical_origin,
            expected_rp_id=self._settings.rp_id,
            credential=credential,
        )
        self._repository.consume_challenge(
            owner_id=owner_id,
            purpose="authentication",
            challenge=challenge,
        )
        self._repository.accept_assertion_counter(
            owner_id=owner_id,
            credential_id=assertion.credential_id,
            sign_count=assertion.sign_count,
        )
        return self._repository.create_session(owner_id=owner_id)

    def recover(self, *, owner_id: UUID, recovery_code: str) -> str:
        self._repository.use_recovery_code(owner_id=owner_id, code=recovery_code)
        return self.begin_registration(owner_id=owner_id)
