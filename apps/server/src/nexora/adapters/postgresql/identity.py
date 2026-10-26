from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import select, text, update
from sqlalchemy.orm import Session, sessionmaker

from nexora.adapters.postgresql.models import (
    BootstrapToken,
    BrowserSession,
    OwnerProfile,
    RecoveryCode,
    SecurityAuditEvent,
    ServiceTokenRecord,
    WebAuthnChallenge,
    WebAuthnCredential,
)
from nexora.identity import (
    BOOTSTRAP_TTL_SECONDS,
    CHALLENGE_TTL_SECONDS,
    MAXIMUM_CONCURRENT_SESSIONS,
    RECENT_REAUTHENTICATION_SECONDS,
    RECOVERY_CODE_COUNT,
    SERVICE_TOKEN_MAXIMUM_AGE_DAYS,
    SESSION_ABSOLUTE_SECONDS,
    SESSION_IDLE_SECONDS,
    SESSION_ROTATION_GRACE_SECONDS,
    SESSION_ROTATION_SECONDS,
    AuthenticatedSession,
    AuthenticationDenied,
    IssuedSession,
    VerifiedCredential,
    random_token,
    secret_matches,
    token_digest,
    validate_service_scopes,
)
from nexora.security_audit import sanitize_audit_metadata


class IdentityStateConflict(AuthenticationDenied):
    pass


class PostgreSQLIdentityRepository:
    """Authoritative single-owner identity state; raw credentials are never persisted."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def create_bootstrap_token(self, *, now: datetime | None = None) -> str:
        observed_at = _utc(now)
        raw = random_token()
        with self._session_factory.begin() as session:
            self._lock_identity(session, "primary_owner_bootstrap")
            if (
                session.execute(
                    select(WebAuthnCredential.credential_record_id)
                    .where(WebAuthnCredential.revoked_at.is_(None))
                    .limit(1)
                ).scalar_one_or_none()
                is not None
            ):
                raise IdentityStateConflict("bootstrap is disabled after first passkey enrollment")
            session.execute(
                update(BootstrapToken).where(BootstrapToken.consumed_at.is_(None)).values(consumed_at=observed_at)
            )
            session.add(
                BootstrapToken(
                    bootstrap_token_id=uuid4(),
                    token_digest=token_digest(raw),
                    created_at=observed_at,
                    expires_at=observed_at + timedelta(seconds=BOOTSTRAP_TTL_SECONDS),
                )
            )
            self._audit(
                session,
                event_type="identity.bootstrap.started",
                actor_type="system",
                actor_id="local_operator_cli",
                target_type="identity",
                target_id="primary_owner",
                reason_code="BOOTSTRAP_TOKEN_ISSUED",
                now=observed_at,
            )
        return raw

    def get_single_owner_id(self) -> UUID:
        with self._session_factory() as session:
            owners = tuple(session.execute(select(OwnerProfile.owner_id).limit(2)).scalars())
        if len(owners) != 1:
            raise AuthenticationDenied("single-owner identity is not initialized")
        return owners[0]

    def list_active_credentials(self, *, owner_id: UUID) -> tuple[VerifiedCredential, ...]:
        with self._session_factory() as session:
            rows = session.execute(
                select(WebAuthnCredential)
                .where(
                    WebAuthnCredential.owner_id == owner_id,
                    WebAuthnCredential.revoked_at.is_(None),
                )
                .order_by(WebAuthnCredential.created_at, WebAuthnCredential.credential_id)
            ).scalars()
            return tuple(
                VerifiedCredential(
                    credential_id=row.credential_id,
                    public_key=row.public_key,
                    algorithm=row.algorithm,
                    sign_count=row.sign_count,
                    transports=tuple(row.transports),
                )
                for row in rows
            )

    def complete_bootstrap(
        self,
        *,
        bootstrap_token: str,
        credential: VerifiedCredential,
        now: datetime | None = None,
    ) -> tuple[UUID, tuple[str, ...]]:
        observed_at = _utc(now)
        digest = token_digest(bootstrap_token)
        with self._session_factory.begin() as session:
            self._lock_identity(session, "primary_owner_bootstrap")
            token = session.execute(
                select(BootstrapToken).where(BootstrapToken.token_digest == digest).with_for_update()
            ).scalar_one_or_none()
            if token is None or token.consumed_at is not None or token.expires_at <= observed_at:
                raise AuthenticationDenied("bootstrap credential is invalid or expired")
            if session.execute(select(OwnerProfile.owner_id).limit(1)).scalar_one_or_none() is not None:
                raise IdentityStateConflict("the single owner already exists")
            owner_id = uuid4()
            session.add(OwnerProfile(owner_id=owner_id, owner_key="primary_owner"))
            session.flush()
            self._add_credential(session, owner_id, credential, observed_at)
            recovery_codes = self._replace_recovery_codes(session, owner_id, observed_at)
            token.consumed_at = observed_at
            self._audit(
                session,
                event_type="identity.bootstrap.completed",
                actor_type="owner",
                actor_id=str(owner_id),
                target_type="identity",
                target_id=str(owner_id),
                reason_code="BOOTSTRAP_COMPLETED",
                now=observed_at,
            )
        return owner_id, recovery_codes

    def issue_challenge(
        self,
        *,
        owner_id: UUID,
        purpose: str,
        now: datetime | None = None,
    ) -> str:
        if purpose not in {"registration", "authentication"}:
            raise ValueError("challenge purpose is invalid")
        observed_at = _utc(now)
        raw = random_token()
        with self._session_factory.begin() as session:
            self._lock_identity(session, str(owner_id))
            self._require_owner(session, owner_id)
            session.add(
                WebAuthnChallenge(
                    challenge_id=uuid4(),
                    owner_id=owner_id,
                    challenge_digest=token_digest(raw),
                    purpose=purpose,
                    created_at=observed_at,
                    expires_at=observed_at + timedelta(seconds=CHALLENGE_TTL_SECONDS),
                )
            )
        return raw

    def consume_challenge(
        self,
        *,
        owner_id: UUID,
        purpose: str,
        challenge: str,
        now: datetime | None = None,
    ) -> None:
        observed_at = _utc(now)
        with self._session_factory.begin() as session:
            row = session.execute(
                select(WebAuthnChallenge)
                .where(
                    WebAuthnChallenge.owner_id == owner_id,
                    WebAuthnChallenge.purpose == purpose,
                    WebAuthnChallenge.challenge_digest == token_digest(challenge),
                )
                .with_for_update()
            ).scalar_one_or_none()
            if row is None or row.consumed_at is not None or row.expires_at <= observed_at:
                raise AuthenticationDenied("WebAuthn challenge is invalid or expired")
            row.consumed_at = observed_at

    def enroll_credential(
        self,
        *,
        owner_id: UUID,
        credential: VerifiedCredential,
        now: datetime | None = None,
    ) -> None:
        observed_at = _utc(now)
        with self._session_factory.begin() as session:
            self._require_owner(session, owner_id)
            self._add_credential(session, owner_id, credential, observed_at)
            self._audit(
                session,
                event_type="credential.enrolled",
                actor_type="owner",
                actor_id=str(owner_id),
                target_type="credential",
                target_id="passkey",
                reason_code="PASSKEY_ENROLLED",
                now=observed_at,
            )

    def accept_assertion_counter(
        self,
        *,
        owner_id: UUID,
        credential_id: str,
        sign_count: int,
        now: datetime | None = None,
    ) -> None:
        observed_at = _utc(now)
        with self._session_factory.begin() as session:
            credential = session.execute(
                select(WebAuthnCredential)
                .where(
                    WebAuthnCredential.owner_id == owner_id,
                    WebAuthnCredential.credential_id == credential_id,
                    WebAuthnCredential.revoked_at.is_(None),
                )
                .with_for_update()
            ).scalar_one_or_none()
            if credential is None:
                raise AuthenticationDenied("credential is not active")
            if credential.sign_count and sign_count <= credential.sign_count:
                raise AuthenticationDenied("credential counter did not advance")
            credential.sign_count = sign_count
            credential.last_used_at = observed_at

    def get_active_credential(self, *, owner_id: UUID, credential_id: str) -> VerifiedCredential:
        with self._session_factory() as session:
            credential = session.execute(
                select(WebAuthnCredential).where(
                    WebAuthnCredential.owner_id == owner_id,
                    WebAuthnCredential.credential_id == credential_id,
                    WebAuthnCredential.revoked_at.is_(None),
                )
            ).scalar_one_or_none()
            if credential is None:
                raise AuthenticationDenied("credential is not active")
            return VerifiedCredential(
                credential_id=credential.credential_id,
                public_key=credential.public_key,
                algorithm=credential.algorithm,
                sign_count=credential.sign_count,
                transports=tuple(credential.transports),
            )

    def create_session(self, *, owner_id: UUID, now: datetime | None = None) -> IssuedSession:
        observed_at = _utc(now)
        raw_token = random_token()
        csrf_token = random_token()
        idle_expires_at = observed_at + timedelta(seconds=SESSION_IDLE_SECONDS)
        absolute_expires_at = observed_at + timedelta(seconds=SESSION_ABSOLUTE_SECONDS)
        session_id = uuid4()
        with self._session_factory.begin() as session:
            self._lock_identity(session, str(owner_id))
            self._require_owner(session, owner_id)
            active = list(
                session.execute(
                    select(BrowserSession)
                    .where(
                        BrowserSession.owner_id == owner_id,
                        BrowserSession.revoked_at.is_(None),
                        BrowserSession.idle_expires_at > observed_at,
                        BrowserSession.absolute_expires_at > observed_at,
                    )
                    .order_by(BrowserSession.created_at)
                    .with_for_update()
                )
                .scalars()
                .all()
            )
            while len(active) >= MAXIMUM_CONCURRENT_SESSIONS:
                active.pop(0).revoked_at = observed_at
            session.add(
                BrowserSession(
                    session_id=session_id,
                    owner_id=owner_id,
                    token_digest=token_digest(raw_token),
                    csrf_digest=token_digest(csrf_token),
                    created_at=observed_at,
                    last_seen_at=observed_at,
                    rotated_at=observed_at,
                    reauthenticated_at=observed_at,
                    idle_expires_at=idle_expires_at,
                    absolute_expires_at=absolute_expires_at,
                )
            )
            self._audit(
                session,
                event_type="session.created",
                actor_type="owner",
                actor_id=str(owner_id),
                target_type="session",
                target_id=str(session_id),
                reason_code="AUTHENTICATION_SUCCEEDED",
                now=observed_at,
            )
        return IssuedSession(
            session_id=session_id,
            owner_id=owner_id,
            token=raw_token,
            csrf_token=csrf_token,
            idle_expires_at=idle_expires_at,
            absolute_expires_at=absolute_expires_at,
        )

    def authenticate_session(
        self,
        *,
        token: str,
        csrf_token: str | None = None,
        now: datetime | None = None,
    ) -> AuthenticatedSession:
        observed_at = _utc(now)
        with self._session_factory.begin() as session:
            row = session.execute(
                select(BrowserSession).where(BrowserSession.token_digest == token_digest(token)).with_for_update()
            ).scalar_one_or_none()
            if (
                row is None
                or row.revoked_at is not None
                or (row.rotation_grace_expires_at is not None and row.rotation_grace_expires_at <= observed_at)
                or row.idle_expires_at <= observed_at
                or row.absolute_expires_at <= observed_at
            ):
                raise AuthenticationDenied("session is invalid or expired")
            if csrf_token is not None and not secret_matches(csrf_token, row.csrf_digest):
                raise AuthenticationDenied("CSRF token is invalid")
            row.last_seen_at = observed_at
            row.idle_expires_at = min(
                observed_at + timedelta(seconds=SESSION_IDLE_SECONDS),
                row.absolute_expires_at,
            )
            return AuthenticatedSession(
                session_id=row.session_id,
                owner_id=row.owner_id,
                rotation_required=(
                    row.replaced_at is None
                    and (observed_at - row.rotated_at).total_seconds() >= SESSION_ROTATION_SECONDS
                ),
                recently_reauthenticated=(observed_at - row.reauthenticated_at).total_seconds()
                <= RECENT_REAUTHENTICATION_SECONDS,
            )

    def rotate_session(
        self,
        *,
        token: str,
        csrf_token: str,
        now: datetime | None = None,
    ) -> IssuedSession:
        observed_at = _utc(now)
        raw_token = random_token()
        new_csrf = random_token()
        new_session_id = uuid4()
        with self._session_factory.begin() as session:
            current = session.execute(
                select(BrowserSession).where(BrowserSession.token_digest == token_digest(token)).with_for_update()
            ).scalar_one_or_none()
            if (
                current is None
                or current.revoked_at is not None
                or current.replaced_at is not None
                or current.idle_expires_at <= observed_at
                or current.absolute_expires_at <= observed_at
                or not secret_matches(csrf_token, current.csrf_digest)
            ):
                raise AuthenticationDenied("session cannot be rotated")
            current.replaced_at = observed_at
            current.rotation_grace_expires_at = observed_at + timedelta(seconds=SESSION_ROTATION_GRACE_SECONDS)
            idle_expires_at = min(
                observed_at + timedelta(seconds=SESSION_IDLE_SECONDS),
                current.absolute_expires_at,
            )
            session.add(
                BrowserSession(
                    session_id=new_session_id,
                    owner_id=current.owner_id,
                    token_digest=token_digest(raw_token),
                    csrf_digest=token_digest(new_csrf),
                    created_at=observed_at,
                    last_seen_at=observed_at,
                    rotated_at=observed_at,
                    reauthenticated_at=current.reauthenticated_at,
                    idle_expires_at=idle_expires_at,
                    absolute_expires_at=current.absolute_expires_at,
                )
            )
            self._audit(
                session,
                event_type="session.rotated",
                actor_type="owner",
                actor_id=str(current.owner_id),
                target_type="session",
                target_id=str(new_session_id),
                reason_code="SESSION_ROTATED",
                now=observed_at,
            )
            return IssuedSession(
                session_id=new_session_id,
                owner_id=current.owner_id,
                token=raw_token,
                csrf_token=new_csrf,
                idle_expires_at=idle_expires_at,
                absolute_expires_at=current.absolute_expires_at,
            )

    def mark_session_reauthenticated(
        self,
        *,
        token: str,
        owner_id: UUID,
        now: datetime | None = None,
    ) -> None:
        observed_at = _utc(now)
        with self._session_factory.begin() as session:
            row = session.execute(
                select(BrowserSession).where(BrowserSession.token_digest == token_digest(token)).with_for_update()
            ).scalar_one_or_none()
            if (
                row is None
                or row.owner_id != owner_id
                or row.revoked_at is not None
                or row.replaced_at is not None
                or row.idle_expires_at <= observed_at
                or row.absolute_expires_at <= observed_at
            ):
                raise AuthenticationDenied("session cannot be reauthenticated")
            row.reauthenticated_at = observed_at
            self._audit(
                session,
                event_type="session.reauthenticated",
                actor_type="owner",
                actor_id=str(owner_id),
                target_type="session",
                target_id=str(row.session_id),
                reason_code="RECENT_REAUTHENTICATION_SUCCEEDED",
                now=observed_at,
            )

    def require_recent_reauthentication(
        self,
        *,
        session_id: UUID,
        now: datetime | None = None,
    ) -> None:
        observed_at = _utc(now)
        with self._session_factory() as session:
            row = session.get(BrowserSession, session_id)
            if (
                row is None
                or row.revoked_at is not None
                or row.replaced_at is not None
                or row.idle_expires_at <= observed_at
                or row.absolute_expires_at <= observed_at
                or (observed_at - row.reauthenticated_at).total_seconds() > RECENT_REAUTHENTICATION_SECONDS
            ):
                raise AuthenticationDenied("recent reauthentication is required")

    def revoke_session(self, *, token: str, now: datetime | None = None) -> None:
        observed_at = _utc(now)
        with self._session_factory.begin() as session:
            row = session.execute(
                select(BrowserSession).where(BrowserSession.token_digest == token_digest(token)).with_for_update()
            ).scalar_one_or_none()
            if row is None or row.revoked_at is not None:
                raise AuthenticationDenied("session is invalid")
            row.revoked_at = observed_at
            self._audit(
                session,
                event_type="session.revoked",
                actor_type="owner",
                actor_id=str(row.owner_id),
                target_type="session",
                target_id=str(row.session_id),
                reason_code="SESSION_LOGOUT",
                now=observed_at,
            )

    def revoke_all_sessions(self, *, owner_id: UUID, now: datetime | None = None) -> int:
        observed_at = _utc(now)
        with self._session_factory.begin() as session:
            result = session.execute(
                update(BrowserSession)
                .where(BrowserSession.owner_id == owner_id, BrowserSession.revoked_at.is_(None))
                .values(revoked_at=observed_at)
            )
            return int(getattr(result, "rowcount", 0) or 0)

    def use_recovery_code(self, *, owner_id: UUID, code: str, now: datetime | None = None) -> None:
        observed_at = _utc(now)
        with self._session_factory.begin() as session:
            self._lock_identity(session, str(owner_id))
            recovery = session.execute(
                select(RecoveryCode)
                .where(RecoveryCode.owner_id == owner_id, RecoveryCode.code_digest == token_digest(code))
                .with_for_update()
            ).scalar_one_or_none()
            if recovery is None or recovery.used_at is not None:
                raise AuthenticationDenied("recovery credential is invalid")
            recovery.used_at = observed_at
            session.execute(
                update(BrowserSession)
                .where(BrowserSession.owner_id == owner_id, BrowserSession.revoked_at.is_(None))
                .values(revoked_at=observed_at)
            )
            session.execute(
                update(WebAuthnCredential)
                .where(WebAuthnCredential.owner_id == owner_id, WebAuthnCredential.revoked_at.is_(None))
                .values(revoked_at=observed_at)
            )
            self._audit(
                session,
                event_type="recovery.used",
                actor_type="owner",
                actor_id=str(owner_id),
                target_type="identity",
                target_id=str(owner_id),
                reason_code="RECOVERY_CODE_ACCEPTED",
                now=observed_at,
            )

    def register_service_token(
        self,
        *,
        raw_token: str,
        scopes: frozenset[str],
        now: datetime | None = None,
    ) -> UUID:
        validate_service_scopes(scopes)
        observed_at = _utc(now)
        record_id = uuid4()
        with self._session_factory.begin() as session:
            session.add(
                ServiceTokenRecord(
                    service_token_id=record_id,
                    principal="trd_bot_integration",
                    token_digest=token_digest(raw_token),
                    scopes=sorted(scopes),
                    created_at=observed_at,
                    expires_at=observed_at + timedelta(days=SERVICE_TOKEN_MAXIMUM_AGE_DAYS),
                )
            )
        return record_id

    def authenticate_service_token(
        self,
        *,
        raw_token: str,
        required_scope: str,
        now: datetime | None = None,
    ) -> UUID:
        observed_at = _utc(now)
        if required_scope not in {
            "source.snapshot.read",
            "source.event.read",
            "source.export.create",
            "source.export.read",
            "decision_review.write_paper_shadow",
        }:
            raise AuthenticationDenied("required service scope is forbidden")
        with self._session_factory() as session:
            record = session.execute(
                select(ServiceTokenRecord).where(ServiceTokenRecord.token_digest == token_digest(raw_token))
            ).scalar_one_or_none()
            if (
                record is None
                or record.revoked_at is not None
                or record.expires_at <= observed_at
                or required_scope not in record.scopes
            ):
                raise AuthenticationDenied("service token is invalid or unauthorized")
            return record.service_token_id

    @staticmethod
    def _require_owner(session: Session, owner_id: UUID) -> None:
        if session.get(OwnerProfile, owner_id) is None:
            raise AuthenticationDenied("owner does not exist")

    @staticmethod
    def _lock_identity(session: Session, key: str) -> None:
        session.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:identity_key, 0))"),
            {"identity_key": key},
        )

    @staticmethod
    def _add_credential(
        session: Session,
        owner_id: UUID,
        credential: VerifiedCredential,
        now: datetime,
    ) -> None:
        session.add(
            WebAuthnCredential(
                credential_record_id=uuid4(),
                owner_id=owner_id,
                credential_id=credential.credential_id,
                public_key=credential.public_key,
                algorithm=credential.algorithm,
                sign_count=credential.sign_count,
                transports=list(credential.transports),
                created_at=now,
            )
        )

    @staticmethod
    def _replace_recovery_codes(session: Session, owner_id: UUID, now: datetime) -> tuple[str, ...]:
        codes = tuple(random_token(bytes_count=16) for _ in range(RECOVERY_CODE_COUNT))
        for code in codes:
            session.add(
                RecoveryCode(
                    recovery_code_id=uuid4(),
                    owner_id=owner_id,
                    code_digest=token_digest(code),
                    created_at=now,
                )
            )
        return codes

    @staticmethod
    def _audit(
        session: Session,
        *,
        event_type: str,
        actor_type: str,
        actor_id: str,
        target_type: str,
        target_id: str,
        reason_code: str,
        now: datetime,
    ) -> None:
        session.add(
            SecurityAuditEvent(
                event_id=f"sec_{random_token(bytes_count=18)}",
                occurred_at=now,
                correlation_id=uuid4(),
                event_type=event_type,
                actor_type=actor_type,
                actor_id=actor_id,
                target_type=target_type,
                target_id=target_id,
                outcome="success",
                reason_code=reason_code,
                source_class="unknown",
                event_metadata=sanitize_audit_metadata({}),
            )
        )


def _utc(value: datetime | None) -> datetime:
    result = datetime.now(UTC) if value is None else value
    if result.tzinfo is None or result.utcoffset() is None:
        raise ValueError("security timestamps must be timezone-aware")
    return result.astimezone(UTC)
