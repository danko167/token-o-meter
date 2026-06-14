"""FastAPI dependencies resolving shared services from app state."""

from typing import Annotated

from fastapi import Depends, Request

from app.runners.base import RunnerRegistry
from app.services.demo_progress import DemoExecutionProgress
from app.services.execution import ExecutionService, RunStore
from app.services.scenario_store import ScenarioStore


def get_scenario_store(request: Request) -> ScenarioStore:
    return request.app.state.scenario_store


def get_registry(request: Request) -> RunnerRegistry:
    return request.app.state.registry


def get_run_store(request: Request) -> RunStore:
    return request.app.state.run_store


def get_execution_service(request: Request) -> ExecutionService:
    return request.app.state.execution_service


def get_demo_progress(request: Request) -> DemoExecutionProgress:
    return request.app.state.demo_progress


ScenarioStoreDep = Annotated[ScenarioStore, Depends(get_scenario_store)]
RegistryDep = Annotated[RunnerRegistry, Depends(get_registry)]
RunStoreDep = Annotated[RunStore, Depends(get_run_store)]
ExecutionServiceDep = Annotated[ExecutionService, Depends(get_execution_service)]
DemoProgressDep = Annotated[DemoExecutionProgress, Depends(get_demo_progress)]
