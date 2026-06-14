"""Application settings, loaded from environment variables / .env file."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]


def _default_database_path() -> Path:
    """Keep dev SQLite writes outside the watched backend source tree.

    Uvicorn's `--reload` watches the backend directory. If the SQLite file lives
    under that tree, every run history write can trigger another reload.
    """
    return BACKEND_DIR.parent / "data" / "just_enough_ai.sqlite3"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="JEAI_",
        extra="ignore",
    )

    app_name: str = "Just enough AI API"
    environment: str = "development"
    debug: bool = False

    # Logging
    log_level: str = "INFO"
    log_json: bool = False  # plain text for dev consoles, JSON for production

    # CORS — Vite dev server defaults
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    # Where scenario YAML files live
    scenarios_dir: Path = BACKEND_DIR / "scenarios"

    # SQLite file used for durable run history and pending approvals.
    database_path: Path = _default_database_path()

    # OpenRouter (OpenAI-compatible API) — used by LLM-backed runners.
    # Leave openrouter_api_key unset to disable LLM-based runners.
    openrouter_api_key: str | None = None
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_model: str = "nex-agi/nex-n2-pro:free"
    # Pricing in USD per 1M tokens, used for estimated_cost_usd.
    # Adjust these if you change the OpenRouter model or route.
    openrouter_input_cost_per_million: float = 0.0
    openrouter_output_cost_per_million: float = 0.0

    # Direct OpenAI API support. Optional: when unset, OpenAI models are shown
    # for cost context but not selectable.
    openai_api_key: str | None = None
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4.1-mini"

    @property
    def llm_api_key(self) -> str | None:
        return self.openrouter_api_key

    @property
    def llm_base_url(self) -> str:
        return self.openrouter_base_url

    @property
    def llm_model(self) -> str:
        return self.openrouter_model

    @property
    def llm_input_cost_per_million(self) -> float:
        return self.openrouter_input_cost_per_million

    @property
    def llm_output_cost_per_million(self) -> float:
        return self.openrouter_output_cost_per_million

    @property
    def llm_provider_name(self) -> str:
        return "OpenRouter"

    # Optional subjective evaluation. Disabled by default so local tests and
    # demos stay fast/deterministic unless explicitly requested.
    llm_judge_enabled: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
