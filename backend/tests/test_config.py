from app.core.config import BACKEND_DIR, Settings


def test_default_database_path_lives_next_to_backend() -> None:
    settings = Settings()

    assert settings.database_path == BACKEND_DIR.parent / "data" / "just_enough_ai.sqlite3"
