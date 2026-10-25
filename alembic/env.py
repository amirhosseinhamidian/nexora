from __future__ import annotations

from logging.config import fileConfig

from nexora.adapters.postgresql import (
    ALEMBIC_VERSION_SCHEMA,
    DATABASE_SESSION_OPTIONS,
    Base,
    load_database_settings,
)
from sqlalchemy import engine_from_config, pool

from alembic import context

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _include_name(name: str | None, type_: str, parent_names: dict[str, str | None]) -> bool:
    if type_ == "table" and name == "alembic_version":
        return parent_names.get("schema_name") not in {None, ALEMBIC_VERSION_SCHEMA}
    return True


def _configuration() -> dict[str, str]:
    settings = load_database_settings()
    values = config.get_section(config.config_ini_section, {})
    values["sqlalchemy.url"] = settings.dsn.get_secret_value()
    return values


def run_migrations_offline() -> None:
    context.configure(
        url=_configuration()["sqlalchemy.url"],
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_schemas=True,
        compare_type=True,
        transaction_per_migration=True,
        version_table_schema=ALEMBIC_VERSION_SCHEMA,
        include_name=_include_name,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        _configuration(),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        connect_args={"options": DATABASE_SESSION_OPTIONS},
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_schemas=True,
            compare_type=True,
            transaction_per_migration=True,
            version_table_schema=ALEMBIC_VERSION_SCHEMA,
            include_name=_include_name,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
