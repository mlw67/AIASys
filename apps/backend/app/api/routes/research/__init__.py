"""科研相关 API 路由聚合。"""

from fastapi import APIRouter

from .papervault import router as papervault_router

router = APIRouter(prefix="/research")
router.include_router(papervault_router)
