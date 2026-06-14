import logging

import pytest

from app.core.logging import setup_logging
from app.db.migrations import run_migrations
from app.runners.base import RunnerRegistry
from app.schemas.run import RunnerInfo
from app.schemas.scenario import Scenario
from app.services.execution import ExecutionService, RunStore


def test_setup_logging_emits_app_namespace_to_stdout(capsys) -> None:
    root = logging.getLogger()
    app_logger = logging.getLogger("app")
    old_root_handlers = list(root.handlers)
    old_app_handlers = list(app_logger.handlers)
    old_root_level = root.level
    old_app_level = app_logger.level
    old_app_propagate = app_logger.propagate
    old_app_disabled = app_logger.disabled

    try:
        setup_logging(level="INFO", json_logs=False)
        logging.getLogger("app.test").info("hello from app logger")

        captured = capsys.readouterr()
        assert "app.test: hello from app logger" in captured.out
    finally:
        root.handlers.clear()
        root.handlers.extend(old_root_handlers)
        root.setLevel(old_root_level)
        app_logger.handlers.clear()
        app_logger.handlers.extend(old_app_handlers)
        app_logger.setLevel(old_app_level)
        app_logger.propagate = old_app_propagate
        app_logger.disabled = old_app_disabled


def test_programmatic_migrations_do_not_disable_app_logging(tmp_path, capsys) -> None:
    root = logging.getLogger()
    app_logger = logging.getLogger("app")
    old_root_handlers = list(root.handlers)
    old_app_handlers = list(app_logger.handlers)
    old_root_level = root.level
    old_app_level = app_logger.level
    old_app_propagate = app_logger.propagate
    old_app_disabled = app_logger.disabled

    try:
        setup_logging(level="INFO", json_logs=False)
        run_migrations(tmp_path / "runs.sqlite3")
        logging.getLogger("app.test").info("still alive after migrations")

        captured = capsys.readouterr()
        assert "app.test: still alive after migrations" in captured.out
        assert logging.getLogger("app").disabled is False
    finally:
        root.handlers.clear()
        root.handlers.extend(old_root_handlers)
        root.setLevel(old_root_level)
        app_logger.handlers.clear()
        app_logger.handlers.extend(old_app_handlers)
        app_logger.setLevel(old_app_level)
        app_logger.propagate = old_app_propagate
        app_logger.disabled = old_app_disabled


@pytest.mark.anyio
async def test_provider_rate_limit_logs_are_sanitized(tmp_path, capsys) -> None:
    root = logging.getLogger()
    app_logger = logging.getLogger("app")
    old_root_handlers = list(root.handlers)
    old_app_handlers = list(app_logger.handlers)
    old_root_level = root.level
    old_app_level = app_logger.level
    old_app_propagate = app_logger.propagate
    old_app_disabled = app_logger.disabled

    try:
        setup_logging(level="INFO", json_logs=False)
        registry = RunnerRegistry()
        registry.register(RateLimitedRunner())
        service = ExecutionService(registry, RunStore(tmp_path / "runs.sqlite3"))

        await service.run(
            Scenario(id="rate-limit", name="Rate limit", input="hello"),
            "llm",
        )

        captured = capsys.readouterr()
        assert "LLM provider rate limit exceeded" in captured.out
        assert "user_secret_123" not in captured.out
        assert "Traceback" not in captured.out
    finally:
        root.handlers.clear()
        root.handlers.extend(old_root_handlers)
        root.setLevel(old_root_level)
        app_logger.handlers.clear()
        app_logger.handlers.extend(old_app_handlers)
        app_logger.setLevel(old_app_level)
        app_logger.propagate = old_app_propagate
        app_logger.disabled = old_app_disabled


class RateLimitedRunner:
    name = "llm"
    level = 2
    description = "fake rate-limited runner"

    def info(self) -> RunnerInfo:
        return RunnerInfo(name=self.name, level=self.level, description=self.description)

    async def execute(self, scenario: Scenario, run_id: str):
        raise RuntimeError(
            "RateLimitError: Error code: 429 - {'user_id': 'user_secret_123'}"
        )
