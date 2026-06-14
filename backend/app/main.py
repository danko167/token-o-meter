"""Just enough AI API entrypoint.

Run with:  uvicorn app.main:app --reload
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import router as v1_router
from app.core.config import get_settings
from app.core.logging import setup_logging
from app.core.middleware import RequestContextMiddleware
from app.db.migrations import run_migrations
from app.runners import build_registry
from app.services.demo_progress import DemoExecutionProgress
from app.services.execution import ExecutionService, RunStore
from app.services.llm_client import LLMClient
from app.services.scenario_store import ScenarioStore

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    logger.info(
        "startup begin: env=%s database=%s",
        settings.environment,
        settings.database_path,
    )
    run_migrations(settings.database_path)
    logger.info("startup migrations complete")

    registry = build_registry()
    run_store = RunStore(settings.database_path, migrate=False)
    scenario_store = ScenarioStore(settings.scenarios_dir, settings.database_path, migrate=False)
    scenario_store.load()
    logger.info(
        "startup services ready: runners=%d scenarios=%d",
        len(registry.list()),
        len(scenario_store.list()),
    )

    app.state.scenario_store = scenario_store
    app.state.registry = registry
    app.state.run_store = run_store
    app.state.demo_progress = DemoExecutionProgress()
    judge_client = LLMClient(settings=settings) if settings.llm_judge_enabled else None
    app.state.execution_service = ExecutionService(registry, run_store, judge_client=judge_client)

    logger.info(
        "%s started (env=%s, runners=%d, database=%s)",
        settings.app_name,
        settings.environment,
        len(registry.list()),
        settings.database_path,
    )
    yield
    logger.info("%s shutting down", settings.app_name)


def create_app() -> FastAPI:
    settings = get_settings()
    setup_logging(level=settings.log_level, json_logs=settings.log_json)

    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        debug=settings.debug,
        lifespan=lifespan,
    )
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID"],
    )
    app.include_router(v1_router)
    return app


app = create_app()
