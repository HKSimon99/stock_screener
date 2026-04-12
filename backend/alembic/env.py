from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool, text
from alembic import context

# Import Base so Alembic can detect models
from app.core.database import Base
from app.core.config import settings

# Import all models here so Base.metadata is populated
import app.models  # noqa: F401

config = context.config

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
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = settings.sync_database_url
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        schema = settings.postgres_schema
        if schema and schema != "public":
            connection.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema}"'))
            connection.execute(text(f'SET search_path TO "{schema}", public'))
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
