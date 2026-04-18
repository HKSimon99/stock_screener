from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import AliasChoices, Field, model_validator, field_validator
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
    api_keys: str = ""  # Comma-separated list of valid API keys
    clerk_secret_key: str = ""
    clerk_publishable_key: str = Field(
        default="",
        validation_alias=AliasChoices(
            "CLERK_PUBLISHABLE_KEY",
            "NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY",
        ),
    )
    clerk_jwks_url: str = "https://api.clerk.com/v1/jwks"
    clerk_jwt_issuer: str = ""
    clerk_jwt_audiences: str = ""

    # CORS — comma-separated list of allowed origins.
    # Dev default allows local Next.js dev server.
    # Production: set CORS_ORIGINS=https://yourapp.vercel.app,https://yourapp.com
    cors_origins: str = "http://localhost:3000"

    @field_validator("secret_key")
    @classmethod
    def secret_key_must_be_set_in_production(cls, v: str, info) -> str:
        # info.data may not have app_env yet in field validators; check env directly
        import os
        if os.getenv("APP_ENV", "development") == "production" and v == "changeme":
            raise ValueError(
                "SECRET_KEY must be set to a strong random value in production. "
                "Generate one with: openssl rand -hex 32"
            )
        return v

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def clerk_jwt_audiences_list(self) -> list[str]:
        return [aud.strip() for aud in self.clerk_jwt_audiences.split(",") if aud.strip()]

    # Database
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "consensus"
    postgres_schema: str = "public"
    postgres_user: str = "consensus"
    postgres_password: str = "changeme"
    # Neon pooler hostname (e.g. ep-xxx-pooler.region.aws.neon.tech).
    # When set, the async runtime engine connects through Neon's built-in
    # PgBouncer so SQLAlchemy uses NullPool (no double-pooling).
    # Leave empty to use the direct host (local dev, non-Neon Postgres).
    postgres_host_pooler: str = ""
    # Neon read-replica hostname (e.g. ep-xxx-replica.region.aws.neon.tech).
    # Create via: Neon dashboard → your project → Compute → Add Read Replica.
    # When set, read-only query paths (rankings, instruments) route here to
    # offload the primary write connection.  Falls back to primary when absent.
    postgres_host_replica: str = ""
    # Set to true for hosted Postgres that requires TLS (e.g. Neon, Railway, Supabase)
    postgres_ssl: bool = False

    @property
    def database_url(self) -> str:
        """Async runtime URL — uses Neon pooler host if configured."""
        host = self.postgres_host_pooler or self.postgres_host
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def database_url_replica(self) -> str | None:
        """Async URL for the Neon read replica, or None when not configured."""
        if not self.postgres_host_replica:
            return None
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host_replica}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def sync_database_url(self) -> str:
        """Sync URL for Alembic migrations."""
        url = (
            f"postgresql+psycopg2://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )
        params: list[str] = []
        if self.postgres_schema and self.postgres_schema != "public":
            options = quote_plus(f"-csearch_path={self.postgres_schema}")
            params.append(f"options={options}")
        if self.postgres_ssl:
            params.append("sslmode=require")
        return f"{url}?{'&'.join(params)}" if params else url

    @property
    def asyncpg_connect_args(self) -> dict:
        args: dict = {}
        if self.postgres_schema and self.postgres_schema != "public":
            args["server_settings"] = {"search_path": self.postgres_schema}
        if self.postgres_ssl:
            args["ssl"] = True
        # Disable asyncpg's prepared statement cache.
        # PostgreSQL 16 on Neon + asyncpg raises "ORDER/GROUP BY expression not found
        # in targetlist" for GROUP BY queries over schema-qualified tables.
        # Setting statement_cache_size=0 prevents stale plan reuse across transactions.
        args["statement_cache_size"] = 0
        return args

    # Redis — optional, only needed for production caching
    redis_url: str = ""

    # Sentry — leave blank to disable error tracking
    sentry_dsn: str = ""
    sentry_traces_sample_rate: float = 0.1  # 10% performance traces in prod

    # Cloudflare R2 — leave blank to disable snapshot CDN upload.
    # Credentials are created in the Cloudflare dashboard → R2 → Manage API tokens.
    r2_account_id: str = ""
    r2_access_key_id: str = ""
    r2_secret_access_key: str = ""
    r2_bucket_name: str = "consensus-snapshots"
    # Public R2 URL (enable "Public Access" on the bucket in CF dashboard):
    #   e.g. https://pub-xxxx.r2.dev or a custom domain
    r2_public_url: str = ""  # Used to generate ETag-friendly public CDN URLs

    @property
    def r2_endpoint_url(self) -> str:
        return f"https://{self.r2_account_id}.r2.cloudflarestorage.com"

    @property
    def r2_enabled(self) -> bool:
        return bool(self.r2_account_id and self.r2_access_key_id and self.r2_secret_access_key)

    # OpenTelemetry — leave blank to disable tracing export
    # Set OTLP_ENDPOINT to your Grafana Cloud OTLP URL, e.g.:
    #   https://otlp-gateway-prod-us-east-0.grafana.net/otlp
    # Set OTLP_HEADERS to "Authorization=Basic <base64(user:token)>"
    otlp_endpoint: str = ""
    otlp_headers: str = ""  # Comma-separated "key=value" pairs
    otlp_service_name: str = "consensus-api"
    otlp_traces_sample_rate: float = 0.1  # 10% of requests traced in prod

    @property
    def otlp_headers_dict(self) -> dict[str, str]:
        """Parse "key=value,key2=value2" into a dict for OTLP exporter."""
        result: dict[str, str] = {}
        for pair in self.otlp_headers.split(","):
            pair = pair.strip()
            if "=" in pair:
                k, _, v = pair.partition("=")
                result[k.strip()] = v.strip()
        return result

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
