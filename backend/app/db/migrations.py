"""Programmatic Alembic migrations, run automatically on startup."""

from pathlib import Path

from alembic.config import Config

from alembic import command

BACKEND_DIR = Path(__file__).resolve().parents[2]


def run_migrations(database_path: Path) -> None:
    """Upgrade the SQLite database at `database_path` to the latest schema."""
    database_path.parent.mkdir(parents=True, exist_ok=True)
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    config.set_main_option("sqlalchemy.url", f"sqlite:///{database_path}")
    config.attributes["configure_logger"] = False
    command.upgrade(config, "head")
