from typing import Annotated, Optional, TYPE_CHECKING

from fastapi import APIRouter, Response
from fastapi.params import Depends

from core.config import conf
from dependencies.auth.backend import authentication_backend, oauth_backend
from dependencies.auth.optional import get_current_user_optional
from errors.http2 import AuthenticationError
from modules.user.schemas import UserRead, UserCreate
from modules.user.service_depenencies import get_user_service
from modules.user_ban.dependencies import get_user_ban_repository
from .fastapi_users import fastapi_users, get_current_user

if TYPE_CHECKING:
    from modules.user.model import User
    from modules.user.service import UserService
    from modules.user_ban.repository import PgUsersBanRepository


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
    user_ban_repo: Annotated["PgUsersBanRepository", Depends(get_user_ban_repository)],
    response: Response,
):
    """
    Эндпоинт для аутентификации микросервисов.
    Проверять валиден ли токен.
    Проверяет есть ли активный бан.
    Args:
        user: Зависимость на получение пользователя
        user_ban_repo: Зависимость на репозиторий банов
        response: ответ

    Returns: ORJSONResponse

    """

    if not user:
        raise AuthenticationError()

    is_banned = await user_ban_repo.check_active_user_ban(user.id)

    response.headers["X-User-ID"] = str(user.id)
    response.headers["X-User-Name"] = user.username
    response.headers["X-User-Admin"] = "true" if user.is_superuser else "false"
    response.headers["X-User-Ban"] = "true" if is_banned else "false"
    response.headers["X-User-Ban-Reason"] = "Использование уязвимостей приложения в свое благо" if is_banned else ""
    response.headers["X-User-Ban-Detail"] = "Нарушение правил платформы" if is_banned else ""
    response.status_code = 200

    return

@router.get("/token-validate-optional")
async def verify_request_token_optional(
    user: Annotated[Optional["User"], Depends(get_current_user_optional)],
    user_ban_repo: Annotated["PgUsersBanRepository", Depends(get_user_ban_repository)],
    response: Response,
):
    """
    Эндпоинт для аутентификации микросервисов на маршрутах,
    где авторизация необязательна.

    В отличие от verify_request_token всегда отвечает 200:
    отсутствие или невалидность токена не ошибка, а анонимный запрос.
    Gateway ориентируется на заголовок X-User-Anonymous.
    Проверяет есть ли активный бан.
    Args:
        user: Зависимость на опциональное получение пользователя
        user_ban_repo: Зависимость на репозиторий банов
        response: ответ

    Returns: ORJSONResponse

    """

    response.status_code = 200

    if not user:
        response.headers["X-User-Anonymous"] = "true"
        response.headers["X-User-Ban"] = "false"
        return

    is_banned = await user_ban_repo.check_active_user_ban(user.id)

    response.headers["X-User-Anonymous"] = "false"
    response.headers["X-User-ID"] = str(user.id)
    response.headers["X-User-Name"] = user.username
    response.headers["X-User-Admin"] = "true" if user.is_superuser else "false"
    response.headers["X-User-Ban"] = "true" if is_banned else "false"
    response.headers["X-User-Ban-Reason"] = "Использование уязвимостей приложения в свое благо" if is_banned else ""
    response.headers["X-User-Ban-Detail"] = "Нарушение правил платформы" if is_banned else ""
    return
