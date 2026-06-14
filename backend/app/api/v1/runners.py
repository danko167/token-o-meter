from fastapi import APIRouter

from app.api.deps import RegistryDep
from app.schemas.run import RunnerInfo

router = APIRouter(prefix="/runners", tags=["runners"])


@router.get("", response_model=list[RunnerInfo])
async def list_runners(registry: RegistryDep) -> list[RunnerInfo]:
    return registry.list()
