"""Alembic migration environment.

Wires Alembic to the app's SQLAlchemy metadata and uses the same DATABASE_URL
the app itself reads from settings/.env — so `alembic` commands never drift
from runtime config.
"""

from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context

# Import app config + models so `target_metadata` covers every table. Importing
# `app.models` triggers each model module to register itself on `Base.metadata`.
from app.core.config import settings
from app.core.database import Base
import app.models  # noqa: F401 — side-effect: register all mappers


config = context.config

# Inject the runtime DATABASE_URL so alembic.ini doesn't duplicate config.
config.set_main_option("sqlalchemy.url", settings.database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
