from __future__ import annotations

from uuid import UUID

from nexora.adapters.postgresql.identity import PostgreSQLIdentityRepository
from nexora.identity import AuthenticatedSession, IssuedSession, VerifiedCredential, WebAuthnCeremonyVerifier
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

    def begin_registration(self, *, session_token: str) -> tuple[AuthenticatedSession, str]:
        session = self._repository.authenticate_session(token=session_token)
        self._repository.require_recent_reauthentication(session_id=session.session_id)
        challenge = self._repository.issue_challenge(owner_id=session.owner_id, purpose="registration")
        return session, challenge

    def complete_registration(
        self,
        *,
        session_token: str,
        challenge: str,
        response_json: str,
    ) -> None:
        session = self._repository.authenticate_session(token=session_token)
        self._repository.require_recent_reauthentication(session_id=session.session_id)
        credential = self._verifier.verify_registration(
            response_json=response_json,
            expected_challenge=challenge,
            expected_origin=self._settings.canonical_origin,
            expected_rp_id=self._settings.rp_id,
        )
        self._repository.consume_challenge(
            owner_id=session.owner_id,
            purpose="registration",
            challenge=challenge,
        )
        self._repository.enroll_credential(owner_id=session.owner_id, credential=credential)

    def begin_authentication(self) -> tuple[UUID, str, tuple[VerifiedCredential, ...]]:
        owner_id = self._repository.get_single_owner_id()
        challenge = self._repository.issue_challenge(owner_id=owner_id, purpose="authentication")
        credentials = self._repository.list_active_credentials(owner_id=owner_id)
        return owner_id, challenge, credentials

    def complete_authentication(
        self,
        *,
        credential_id: str,
        challenge: str,
        response_json: str,
    ) -> IssuedSession:
        owner_id = self._repository.get_single_owner_id()
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

    def begin_reauthentication(
        self,
        *,
        session_token: str,
    ) -> tuple[AuthenticatedSession, str, tuple[VerifiedCredential, ...]]:
        session = self._repository.authenticate_session(token=session_token)
        challenge = self._repository.issue_challenge(owner_id=session.owner_id, purpose="authentication")
        credentials = self._repository.list_active_credentials(owner_id=session.owner_id)
        return session, challenge, credentials

    def complete_reauthentication(
        self,
        *,
        session_token: str,
        credential_id: str,
        challenge: str,
        response_json: str,
    ) -> AuthenticatedSession:
        session = self._repository.authenticate_session(token=session_token)
        credential = self._repository.get_active_credential(
            owner_id=session.owner_id,
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
            owner_id=session.owner_id,
            purpose="authentication",
            challenge=challenge,
        )
        self._repository.accept_assertion_counter(
            owner_id=session.owner_id,
            credential_id=assertion.credential_id,
            sign_count=assertion.sign_count,
        )
        self._repository.mark_session_reauthenticated(token=session_token, owner_id=session.owner_id)
        return self._repository.authenticate_session(token=session_token)

    def recover(self, *, recovery_code: str) -> tuple[UUID, str]:
        owner_id = self._repository.get_single_owner_id()
        self._repository.use_recovery_code(owner_id=owner_id, code=recovery_code)
        challenge = self._repository.issue_challenge(owner_id=owner_id, purpose="registration")
        return owner_id, challenge

    def complete_recovery_registration(
        self,
        *,
        owner_id: UUID,
        challenge: str,
        response_json: str,
    ) -> IssuedSession:
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
        return self._repository.create_session(owner_id=owner_id)
