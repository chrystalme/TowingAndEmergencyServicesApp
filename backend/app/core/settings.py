"""Application configuration using pydantic-settings.

The settings are read from environment variables; defaults are provided for local development.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # Database URL for async SQLAlchemy (asyncpg driver)
    DATABASE_URL: str = "postgresql+asyncpg://postgres:secret@db/towing"
    # JWT secret – should be overridden in production
    JWT_SECRET_KEY: str = "super-secret-key"
    # Token expiration in minutes
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 1 day

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

settings = Settings()
