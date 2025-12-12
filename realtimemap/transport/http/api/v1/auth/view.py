from typing import Annotated, TYPE_CHECKING

from fastapi import APIRouter, Response
from fastapi.params import Depends

from core.config import conf
from dependencies.auth.backend import authentication_backend, oauth_backend
from errors.http2 import AuthenticationError
from modules.user.schemas import UserRead, UserCreate
from modules.user.service_depenencies import get_user_service
from .fastapi_users import fastapi_users, get_current_user

if TYPE_CHECKING:
    from modules.user.model import User
    from modules.user.service import UserService


router = APIRouter(
    prefix="/auth",
    tags=["Auth"],
)


router.include_router(
    router=fastapi_users.get_auth_router(
        authentication_backend,
    )
)

router.include_router(
    router=fastapi_users.get_register_router(
        UserRead,
        UserCreate,
    ),
)

if conf.api.v1.auth.activate_google_auth:
    from auth.oauth import google_oauth_client

    router.include_router(
        fastapi_users.get_oauth_router(
            google_oauth_client,
            oauth_backend,
            conf.api.v1.auth.verification_token_secret,
        ),
        prefix="/google",
        tags=["Auth"],
    )

router.include_router(
    fastapi_users.get_verify_router(UserRead),
    tags=["Auth"],
)

router.include_router(
    fastapi_users.get_reset_password_router(),
    tags=["Auth"],
)


@router.get("/token-validate")
async def verify_request_token(
    user: Annotated["User", Depends(get_current_user)],
    service: Annotated["UserService", Depends(get_user_service)],
    response: Response,
):
    """
    Эндпоинт для аутентификации микросервисов.
    Проверять валиден ли токен.
    Проверяет есть ли активный бан.
    Args:
        service: Зависимость для пользовательского сервиса
        user: Зависимость на получение пользователя
        response: ответ

    Returns: ORJSONResponse

    """

    if not user:
        raise AuthenticationError()

    active_ban = await service.is_ban(user.id)

    response.headers["X-User-ID"] = str(user.id)
    response.headers["X-User-Email"] = user.email
    response.headers["X-User-Ban"] = "true" if active_ban else "false"
    response.headers["X-User-Admin"] = "true" if user.is_superuser else "false"
    response.status_code = 200

    return
