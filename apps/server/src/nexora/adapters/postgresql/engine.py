from __future__ import annotations

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from nexora.adapters.postgresql.base import DATABASE_SESSION_OPTIONS
from nexora.adapters.postgresql.config import DatabaseSettings


def create_database_engine(settings: DatabaseSettings) -> Engine:
    return create_engine(
        settings.dsn.get_secret_value(),
        connect_args={"options": DATABASE_SESSION_OPTIONS},
        max_overflow=settings.max_overflow,
        pool_pre_ping=True,
        pool_size=settings.pool_size,
        pool_timeout=settings.pool_timeout_seconds,
    )


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, class_=Session, expire_on_commit=False)


def probe_database(engine: Engine) -> bool:
    with engine.connect() as connection:
        result: object = connection.execute(text("SELECT 1")).scalar_one()
        return result == 1
