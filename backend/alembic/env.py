import os
import sys
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool, text
from alembic import context

# Import Base so Alembic can detect models
from app.core.database import Base
from app.core.config import settings

# Import all models here so Base.metadata is populated
import app.models  # noqa: F401

config = context.config


def _is_neon_host(host: str) -> bool:
    """Return True when the configured Postgres host looks like a Neon endpoint."""
    return "neon.tech" in host or ".neon.host" in host


def _guard_production_downgrade() -> None:
    """Refuse 'alembic downgrade …' against a live Neon host unless the operator
    has explicitly set ALEMBIC_ALLOW_PRODUCTION_DOWNGRADE=true.

    Background: the .env file ships with production Neon credentials so that
    'uv run alembic upgrade head' works from a developer laptop.  A mistaken
    'alembic downgrade base' with those credentials would wipe *all* rows from
    consensus_app while leaving the schema intact — exactly the data-loss
    pattern observed in production.  This guard makes that impossible without
    a deliberate override.
    """
    if not _is_neon_host(settings.postgres_host):
        return  # local or non-Neon target — no guard needed

    argv_lower = [a.lower() for a in sys.argv]
    if "downgrade" not in argv_lower:
        return  # upgrade / current / history — safe

    allow = os.environ.get("ALEMBIC_ALLOW_PRODUCTION_DOWNGRADE", "").strip().lower()
    if allow == "true":
        return  # explicit opt-in

    raise SystemExit(
        "\n"
        "⛔  ALEMBIC DOWNGRADE REFUSED — production Neon host detected\n"
        f"   POSTGRES_HOST = {settings.postgres_host}\n"
        "\n"
        "   Running 'alembic downgrade' against the live database would wipe all\n"
        "   application rows while leaving the schema intact.  This is the known\n"
        "   production data-loss pattern.\n"
        "\n"
        "   If you genuinely need to downgrade a STAGING branch, set:\n"
        "       export ALEMBIC_ALLOW_PRODUCTION_DOWNGRADE=true\n"
        "   and re-run the command.\n"
    )

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _configure_context_kwargs() -> dict:
    schema = settings.postgres_schema
    if schema and schema != "public":
        return {
            "version_table_schema": schema,
            "include_schemas": True,
        }
    return {}


def run_migrations_offline() -> None:
    _guard_production_downgrade()
    url = settings.sync_database_url
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        **_configure_context_kwargs(),
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    _guard_production_downgrade()
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = settings.sync_database_url
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    schema = settings.postgres_schema

    # Step 1: ensure the schema exists in its own committed transaction.
    # MUST be a separate connection so the CREATE SCHEMA commit is visible
    # before Alembic's migration transaction starts on a fresh connection.
    # (Executing DDL on the same connection before context.begin_transaction()
    # triggers SQLAlchemy 2 autobegin, which Alembic then wraps in a savepoint;
    # the outer implicit transaction never commits → silent rollback.)
    if schema and schema != "public":
        with connectable.connect() as setup_conn:
            with setup_conn.begin():
                setup_conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema}"'))

    # Step 2: run migrations on a fresh connection (no pre-existing transaction).
    # search_path is set via the URL's ?options= startup parameter.
    with connectable.connect() as connection:
        if schema and schema != "public":
            connection.dialect.default_schema_name = schema
            connection = connection.execution_options(schema_translate_map={None: schema})

        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            **_configure_context_kwargs(),
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
