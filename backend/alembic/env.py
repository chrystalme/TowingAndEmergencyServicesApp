import os
import sys
from logging.config import fileConfig

from sqlalchemy import create_engine, pool
from alembic import context

# Add the app directory to the path so we can import models
sys.path.append("/app")

from app.models import Base

# Alembic Config object provides access to .ini values
config = context.config

# Setup logging from config file if present
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Get DB URL from env or fallback to .ini
def get_url() -> str:
    return os.getenv("DATABASE_URL", config.get_main_option("sqlalchemy.url"))

# Transform async URL (with +asyncpg) to sync URL for Alembic
def make_sync_url(async_url: str) -> str:
    return async_url.replace("+asyncpg", "")

url = get_url()
sync_url = make_sync_url(url)

# Create a synchronous engine for Alembic migrations
connectable = create_engine(sync_url, poolclass=pool.NullPool)

# Import models to register them with Base.metadata
target_metadata = Base.metadata

def run_migrations_offline() -> None:
    """Run migrations in offline mode – generate SQL scripts without DB connection."""
    context.configure(
        url=sync_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in online mode – apply directly to the DB."""
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, render_as_batch=True)
        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()