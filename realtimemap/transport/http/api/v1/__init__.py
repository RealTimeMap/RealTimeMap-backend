__all__ = ["router"]

from fastapi import APIRouter

from core.config import conf
from .auth import router as auth_router
from .bans import router as bans_router
from .rbac import router as rbac_router
from .sessions import router as sessions_router


router = APIRouter(prefix=conf.api.v1.prefix)
router.include_router(auth_router)
router.include_router(sessions_router)
router.include_router(rbac_router)
router.include_router(bans_router)
