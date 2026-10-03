from typing import Annotated, Optional, TYPE_CHECKING
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Request, Response, status
from fastapi.params import Depends
from fastapi_users import exceptions as fastapi_users_exceptions

from auth.user_manager import UserManager
from core.config import conf
from dependencies.auth.backend import authentication_backend, oauth_backend
from dependencies.auth.manager import get_user_manager
from dependencies.auth.optional import get_current_user_optional
from modules.rbac.dependencies import get_rbac_service
from modules.user.schemas import UserDeleteRequest, UserRead, UserCreate
from modules.user.service_depenencies import get_user_service
from modules.user_ban.dependencies import get_user_ban_repository
from modules.user_ban.model import BanReason
from .fastapi_users import (
    fastapi_users,
    get_current_user,
    get_current_user_without_ban,
)

if TYPE_CHECKING:
    from modules.rbac.policy import Access
    from modules.rbac.service import RbacService
    from modules.user.model import User
    from modules.user.service import UserService
    from modules.user_ban.model import UsersBan
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


def _set_user_headers(
    response: Response,
    user: "User",
    ban: Optional["UsersBan"],
    access: "Access",
) -> None:
    """
    Проставить заголовки пользователя для gateway.

    Значения, которые могут содержать не-ASCII (username, текст причины),
    percent-кодируются: заголовки в ASGI кодируются в latin-1, и кириллица
    в них приводит к UnicodeEncodeError уже на этапе отправки ответа.
    Gateway обязан раскодировать их (decodeURIComponent / url.QueryUnescape).

    Args:
        response: ответ, в который проставляются заголовки
        user: пользователь
        ban: активный бан или None
        access: итоговые роли и права
    """

    response.headers["X-User-ID"] = str(user.id)
    response.headers["X-User-Name"] = quote(user.username)
    response.headers["X-User-Admin"] = "true" if user.is_superuser else "false"
    response.headers["X-User-Ban"] = "true" if ban else "false"
    _set_access_headers(response, access.roles, access.permissions)

    if not ban:
        return

    # Машинно-читаемый код причины (abuse / spam / other),
    # человекочитаемый текст подставляет gateway.
    reason = ban.reason.value if isinstance(ban.reason, BanReason) else str(ban.reason)
    response.headers["X-User-Ban-Reason"] = reason
    response.headers["X-User-Ban-Detail"] = quote(ban.reason_text or "")
    response.headers["X-User-Ban-Time"] = (
        "permanent" if ban.is_permanent else ban.banned_until.isoformat()
    )


def _set_access_headers(
    response: Response, roles: list[str], permissions: list[str]
) -> None:
    """Ставятся всегда, даже пустыми, — чтобы gateway не пропустил клиентские."""
    response.headers["X-User-Roles"] = ",".join(roles)
    response.headers["X-User-Permissions"] = ",".join(permissions)


@router.get("/token-validate")
async def verify_request_token(
    user: Annotated["User", Depends(get_current_user)],
    user_ban_repo: Annotated["PgUsersBanRepository", Depends(get_user_ban_repository)],
    rbac: Annotated["RbacService", Depends(get_rbac_service)],
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

    ban = await user_ban_repo.get_active_user_ban(user.id)

    _set_user_headers(response, user, ban, await rbac.get_access(user))

    return


@router.get("/token-validate-optional")
async def verify_request_token_optional(
    user: Annotated[Optional["User"], Depends(get_current_user_optional)],
    user_ban_repo: Annotated["PgUsersBanRepository", Depends(get_user_ban_repository)],
    rbac: Annotated["RbacService", Depends(get_rbac_service)],
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

    if not user:
        response.headers["X-User-Anonymous"] = "true"
        response.headers["X-User-Ban"] = "false"
        _set_access_headers(response, [], [])
        return

    ban = await user_ban_repo.get_active_user_ban(user.id)

    response.headers["X-User-Anonymous"] = "false"
    _set_user_headers(response, user, ban, await rbac.get_access(user))

    return


@router.delete(
    "/me",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить свой аккаунт",
    responses={
        status.HTTP_400_BAD_REQUEST: {"description": "Неверный пароль"},
        status.HTTP_403_FORBIDDEN: {"description": "На аккаунте активный бан"},
    },
)
async def delete_me(
    body: UserDeleteRequest,
    user: Annotated["User", Depends(get_current_user_without_ban)],
    user_manager: Annotated[UserManager, Depends(get_user_manager)],
    request: Request,
):
    """Необратимо удаляет аккаунт текущего пользователя.

    Здесь стираются учётная запись, сессии и OAuth-привязки. Данные в
    остальных сервисах (профиль, метки, прогресс, push-токены, письма)
    удаляются или обезличиваются по событию user.deleted.

    Пока бан активен, удаление запрещено: иначе им можно было бы обнулить
    санкции и зарегистрироваться заново на тот же адрес.
    """
    try:
        await user_manager.delete_account(user, body.password, request)
    except fastapi_users_exceptions.InvalidPasswordException:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="DELETE_ACCOUNT_BAD_PASSWORD",
        )

    return
