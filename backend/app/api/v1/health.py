from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from fastapi import APIRouter
from sqlalchemy import create_engine

from app.core.config import BACKEND_DIR, get_settings

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@router.get("/health/db")
async def db_health() -> dict:
    settings = get_settings()
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    script = ScriptDirectory.from_config(config)
    head_revision = script.get_current_head()

    engine = create_engine(f"sqlite:///{settings.database_path}")
    try:
        with engine.connect() as connection:
            context = MigrationContext.configure(connection)
            current_revision = context.get_current_revision()
    finally:
        engine.dispose()

    return {
        "status": "ok" if current_revision == head_revision else "migration_pending",
        "database_path": str(settings.database_path),
        "current_revision": current_revision,
        "head_revision": head_revision,
    }
