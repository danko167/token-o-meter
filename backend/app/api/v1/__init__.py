from fastapi import APIRouter

from app.api.v1 import (
    demo_data,
    health,
    human_metrics,
    pricing,
    recommendations,
    runners,
    runs,
    scenarios,
)

router = APIRouter(prefix="/api/v1")
router.include_router(health.router)
router.include_router(scenarios.router)
router.include_router(runners.router)
router.include_router(runs.router)
router.include_router(recommendations.router)
router.include_router(human_metrics.router)
router.include_router(demo_data.router)
router.include_router(pricing.router)
