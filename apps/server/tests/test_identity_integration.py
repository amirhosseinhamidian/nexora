from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from nexora.adapters.postgresql import (
    BrowserSession,
    PostgreSQLIdentityRepository,
    RecoveryCode,
    SecurityAuditEvent,
    WebAuthnCredential,
    create_database_engine,
    create_session_factory,
    load_database_settings,
)
from nexora.identity import AuthenticationDenied, VerifiedCredential, token_digest
from sqlalchemy import Engine, delete, select, text
from sqlalchemy.exc import DBAPIError

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def engine() -> Iterator[Engine]:
    database_engine = create_database_engine(load_database_settings())
    yield database_engine
    database_engine.dispose()


def test_bootstrap_session_recovery_and_audit_are_fail_closed(engine: Engine) -> None:
    factory = create_session_factory(engine)
    repository = PostgreSQLIdentityRepository(factory)
    now = datetime.now(UTC)
    bootstrap = repository.create_bootstrap_token(now=now)
    owner_id, recovery_codes = repository.complete_bootstrap(
        bootstrap_token=bootstrap,
        credential=VerifiedCredential(
            credential_id="integration-credential-id",
            public_key=b"k" * 64,
            algorithm="ES256",
            sign_count=0,
            transports=("internal",),
        ),
        now=now + timedelta(seconds=1),
    )
    assert len(recovery_codes) == 10
    with pytest.raises(AuthenticationDenied):
        repository.complete_bootstrap(
            bootstrap_token=bootstrap,
            credential=VerifiedCredential(
                credential_id="replayed-credential-id",
                public_key=b"k" * 64,
                algorithm="ES256",
                sign_count=0,
                transports=(),
            ),
            now=now + timedelta(seconds=2),
        )

    issued = repository.create_session(owner_id=owner_id, now=now + timedelta(seconds=2))
    authenticated = repository.authenticate_session(
        token=issued.token,
        csrf_token=issued.csrf_token,
        now=now + timedelta(seconds=3),
    )
    assert authenticated.owner_id == owner_id
    with pytest.raises(AuthenticationDenied, match="CSRF"):
        repository.authenticate_session(
            token=issued.token,
            csrf_token="wrong-csrf-token",
            now=now + timedelta(seconds=4),
        )

    due = repository.authenticate_session(
        token=issued.token,
        csrf_token=issued.csrf_token,
        now=now + timedelta(seconds=903),
    )
    assert due.rotation_required is True
    rotated = repository.rotate_session(
        token=issued.token,
        csrf_token=issued.csrf_token,
        now=now + timedelta(seconds=904),
    )
    assert (
        repository.authenticate_session(
            token=issued.token,
            now=now + timedelta(seconds=920),
        ).rotation_required
        is False
    )
    with pytest.raises(AuthenticationDenied):
        repository.authenticate_session(token=issued.token, now=now + timedelta(seconds=935))
    assert (
        repository.authenticate_session(
            token=rotated.token,
            csrf_token=rotated.csrf_token,
            now=now + timedelta(seconds=936),
        ).owner_id
        == owner_id
    )

    repository.use_recovery_code(
        owner_id=owner_id,
        code=recovery_codes[0],
        now=now + timedelta(seconds=937),
    )
    with pytest.raises(AuthenticationDenied):
        repository.authenticate_session(token=rotated.token, now=now + timedelta(seconds=938))
    with pytest.raises(AuthenticationDenied):
        repository.use_recovery_code(
            owner_id=owner_id,
            code=recovery_codes[0],
            now=now + timedelta(seconds=939),
        )

    try:
        with factory() as session:
            stored_sessions = session.execute(select(BrowserSession)).scalars().all()
            credential = session.execute(select(WebAuthnCredential)).scalar_one()
            codes = session.execute(select(RecoveryCode)).scalars().all()
            audit = session.execute(select(SecurityAuditEvent)).scalars().all()
            assert {row.token_digest for row in stored_sessions} == {
                token_digest(issued.token),
                token_digest(rotated.token),
            }
            assert all(issued.token not in row.token_digest for row in stored_sessions)
            assert credential.revoked_at is not None
            assert all(code.code_digest not in recovery_codes for code in codes)
            assert {event.event_type for event in audit}.issuperset(
                {"identity.bootstrap.started", "identity.bootstrap.completed", "session.created", "recovery.used"}
            )
        with engine.begin() as connection:
            savepoint = connection.begin_nested()
            with pytest.raises(DBAPIError, match="immutable Nexora security audit event"):
                connection.execute(text("UPDATE nexora.security_audit_events SET metadata = '{}'::jsonb"))
            savepoint.rollback()
    finally:
        with factory.begin() as session:
            session.execute(delete(BrowserSession).where(BrowserSession.owner_id == owner_id))
            session.execute(delete(RecoveryCode).where(RecoveryCode.owner_id == owner_id))
            session.execute(delete(WebAuthnCredential).where(WebAuthnCredential.owner_id == owner_id))
            session.execute(text("DELETE FROM nexora.bootstrap_tokens"))
            session.execute(
                text("DELETE FROM nexora.owner_profiles WHERE owner_id = :owner_id"), {"owner_id": owner_id}
            )
        with engine.begin() as connection:
            connection.execute(text("TRUNCATE nexora.security_audit_events"))
