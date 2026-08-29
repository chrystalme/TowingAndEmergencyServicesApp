"""Application configuration using pydantic-settings.

Settings come from environment variables, with defaults tuned for local
development. ``JWT_SECRET_KEY`` deliberately keeps a well-known default so a
fresh clone runs with no setup — paired with a guard that refuses to start with
that default anywhere that looks like a real deployment. The safe state is the
one you get by doing nothing.
"""

import os

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# The value baked into docker-compose.yml and this repository's git history.
# Anyone who has read the repo can forge a token for any user with it, so it is
# usable for local development only.
INSECURE_DEV_SECRET = "super-secret-key"

# Environment names treated as local/throwaway. Anything else counts as a real
# deployment and is subject to the checks below.
LOCAL_ENVIRONMENTS = {"development", "dev", "local", "test", "testing"}


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

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

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
