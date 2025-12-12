__all__ = ["router"]

from fastapi import APIRouter

from core.config import conf
from .auth import router as auth_router
from .category.view import router as category_router
from .gamefication.level_view import router as level_router
from .mark import router as mark_router
from .subscription.view import router as subscription_router
from .users.chat_view import router as users_chat_router
from .users.view import router as users_router

user_router = APIRouter(prefix="/user", tags=["user"])
user_router.include_router(users_router)
user_router.include_router(users_chat_router)

router = APIRouter(prefix=conf.api.v1.prefix)
router.include_router(auth_router)
router.include_router(mark_router)
router.include_router(category_router)
router.include_router(user_router)
router.include_router(subscription_router)
router.include_router(level_router)
