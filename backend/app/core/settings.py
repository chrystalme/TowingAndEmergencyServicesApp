"""Application configuration using pydantic-settings.

Settings come from environment variables, with defaults tuned for local
development. Two safety properties are deliberate:

* ``JWT_SECRET_KEY`` keeps a well-known default so a fresh clone runs with no
  setup, paired with a guard that refuses to start with that default anywhere
  that looks deployed. The safe state is the one you get by doing nothing.
* ``DATABASE_URL`` is normalized on the way in, so a managed-Postgres URL
  (Railway, Heroku, Neon, Supabase...) can be pasted verbatim without the app
  crashing on a driver mismatch.
"""

import os
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# The value baked into docker-compose.yml and this repository's git history.
# Anyone who has read the repo can forge a token for any user with it, so it is
# usable for local development only.
INSECURE_DEV_SECRET = "super-secret-key"

# Environment names treated as local/throwaway. Anything else counts as a real
# deployment and is subject to the checks below.
LOCAL_ENVIRONMENTS = {"development", "dev", "local", "test", "testing"}

# Schemes handed out by managed Postgres providers that SQLAlchemy's async
# engine cannot use directly. `postgres://` is rejected outright by SQLAlchemy;
# `postgresql://` resolves to psycopg2, which is not async.
SYNC_POSTGRES_SCHEMES = ("postgres", "postgresql")
ASYNC_POSTGRES_SCHEME = "postgresql+asyncpg"

# libpq connection parameters that providers append to DATABASE_URL but asyncpg
# does not accept. These survive create_async_engine() and only blow up on the
# first query, so they are stripped here. `sslmode` is translated rather than
# dropped (see _normalize_database_url).
LIBPQ_ONLY_PARAMS = {
    "sslmode",
    "sslrootcert",
    "sslcert",
    "sslkey",
    "sslcrl",
    "channel_binding",
    "gssencmode",
    "target_session_attrs",
}

# libpq sslmode -> asyncpg ssl. None means "drop it, the default is fine".
# NOTE: verify-ca/verify-full are mapped to "require", which encrypts but does
# NOT verify the server certificate — asyncpg needs an explicit CA bundle for
# that. Pass one via connect_args if you need real verification.
SSLMODE_TO_ASYNCPG_SSL = {
    "disable": None,
    "allow": None,
    "prefer": "prefer",
    "require": "require",
    "verify-ca": "require",
    "verify-full": "require",
}


class Settings(BaseSettings):
    # Database URL for async SQLAlchemy (asyncpg driver)
    DATABASE_URL: str = "postgresql+asyncpg://postgres:secret@db/towing"
    # JWT secret - MUST be overridden outside local development
    JWT_SECRET_KEY: str = INSECURE_DEV_SECRET
    # Token expiration in minutes
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 1 day
    # Deployment marker. Left as "development" locally; set to "production" (or
    # anything outside LOCAL_ENVIRONMENTS) when deploying.
    ENVIRONMENT: str = "development"
    # Comma-separated browser origins allowed to call the API, e.g.
    # "https://app.example.com,https://admin.example.com". "*" is dev-only and
    # forces credentials off (see app/main.py).
    CORS_ORIGINS: str = "*"
    # Redis, used for pub/sub fan-out (see app/core/broker.py). Empty means
    # in-process fan-out, which is correct for one instance and silently
    # wrong for two — so set this anywhere that can scale out. Railway
    # exposes it as ${{Redis.REDIS_URL}}.
    REDIS_URL: str = ""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    @field_validator("DATABASE_URL")
    @classmethod
    def _normalize_database_url(cls, value: str) -> str:
        """Rewrite a managed-provider Postgres URL into one asyncpg can use.

        Providers hand out `postgresql://host/db?sslmode=require`. That fails
        two different ways: the scheme selects the sync psycopg2 driver, and
        `sslmode` is a libpq parameter asyncpg rejects at connect time. Both are
        fixed here so the platform's DATABASE_URL can be used verbatim.
        """
        if not value:
            return value

        parts = urlsplit(value)
        scheme = parts.scheme

        # Only touch plain Postgres schemes; leave sqlite, an explicit
        # +asyncpg, or any other driver choice exactly as the operator wrote it.
        if scheme not in SYNC_POSTGRES_SCHEMES:
            return value
        scheme = ASYNC_POSTGRES_SCHEME

        kept = []
        ssl_value = None
        for key, val in parse_qsl(parts.query, keep_blank_values=True):
            if key not in LIBPQ_ONLY_PARAMS:
                kept.append((key, val))
                continue
            if key == "sslmode":
                ssl_value = SSLMODE_TO_ASYNCPG_SSL.get(val.strip().lower())

        # Don't clobber an `ssl` the operator set explicitly.
        if ssl_value is not None and not any(k == "ssl" for k, _ in kept):
            kept.append(("ssl", ssl_value))

        return urlunsplit((scheme, parts.netloc, parts.path, urlencode(kept), parts.fragment))

    @property
    def is_deployed(self) -> bool:
        """Whether this process is running somewhere that is not local dev.

        Railway injects RAILWAY_ENVIRONMENT into every service, so deploying
        there flips this on by itself — the guard fires even if nobody
        remembered to set ENVIRONMENT.
        """
        if os.getenv("RAILWAY_ENVIRONMENT"):
            return True
        return self.ENVIRONMENT.strip().lower() not in LOCAL_ENVIRONMENTS

    @property
    def cors_origin_list(self) -> list[str]:
        """CORS_ORIGINS parsed into a list; ["*"] means allow any origin."""
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()] or ["*"]

    @model_validator(mode="after")
    def _reject_insecure_secret_when_deployed(self) -> "Settings":
        if self.is_deployed and self.JWT_SECRET_KEY == INSECURE_DEV_SECRET:
            raise ValueError(
                "JWT_SECRET_KEY is still the public development default. "
                "Anyone who has read this repository could forge a token for any "
                "user, including the administrator. Generate a private value "
                "with:  python -c 'import secrets; print(secrets.token_urlsafe(64))'"
            )
        return self


settings = Settings()
