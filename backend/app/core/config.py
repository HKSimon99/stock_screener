from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import model_validator
from functools import lru_cache
from pathlib import Path
from urllib.parse import quote_plus


REPO_ROOT = Path(__file__).resolve().parents[3]
ENV_FILE = REPO_ROOT / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ENV_FILE, extra="ignore")

    # App
    app_env: str = "development"
    secret_key: str = "changeme"
    api_v1_prefix: str = "/api/v1"

    # Database
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "consensus"
    postgres_schema: str = "public"
    postgres_user: str = "consensus"
    postgres_password: str = "changeme"

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def sync_database_url(self) -> str:
        """Sync URL for Alembic migrations."""
        url = (
            f"postgresql+psycopg2://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )
        if self.postgres_schema and self.postgres_schema != "public":
            options = quote_plus(f"-csearch_path={self.postgres_schema}")
            return f"{url}?options={options}"
        return url

    @property
    def asyncpg_connect_args(self) -> dict[str, dict[str, str]]:
        if self.postgres_schema and self.postgres_schema != "public":
            return {"server_settings": {"search_path": self.postgres_schema}}
        return {}

    # Redis — optional, only needed for production caching
    redis_url: str = ""

    # Celery — defaults to PostgreSQL broker so no Redis required for local dev.
    # Override in .env with a Redis URL for production: redis://localhost:6379/1
    celery_broker_url: str = ""
    celery_result_backend: str = ""

    @model_validator(mode="after")
    def set_celery_defaults(self) -> "Settings":
        """Auto-derive Celery URLs from Postgres config if not explicitly set."""
        pg = (
            f"db+postgresql+psycopg2://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )
        if not self.celery_broker_url:
            self.celery_broker_url = pg
        if not self.celery_result_backend:
            self.celery_result_backend = pg
        return self

    # US data
    fmp_api_key: str = ""
    fred_api_key: str = ""

    # KR data — KIS Developers
    kis_app_key: str = ""
    kis_app_secret: str = ""
    kis_account_no: str = ""
    kis_account_product_code: str = "01"
    kis_env: str = "paper"  # 'paper' | 'real'

    # KR data — OpenDART
    opendart_api_key: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
