import uuid
from typing import Annotated, List, TYPE_CHECKING

from fastapi import APIRouter, Depends, Path, status

from core.config import conf
from modules.user_session.dependencies import get_session_service
from modules.user_session.schemas import SessionRead, SessionRevokedResponse
from ..auth.fastapi_users import current_active_user_token

if TYPE_CHECKING:
    from modules.user.model import User
    from modules.user_session.service import SessionService


router = APIRouter(
    prefix="/sessions",
    tags=["Sessions"],
)


@router.get(
    "",
    response_model=List[SessionRead],
    summary="Активные сессии текущего пользователя",
)
async def list_sessions(
    user_token: Annotated[tuple["User", str], Depends(current_active_user_token)],
    service: Annotated["SessionService", Depends(get_session_service)],
):
    """Список устройств, с которых выполнен вход.

    Сессия, из которой пришёл запрос, помечена is_current — клиенту нужно
    отличать её, чтобы не предлагать завершить её наравне с остальными.
    """
    user, token = user_token

    sessions = await service.list_sessions(user.id)

    return [
        SessionRead.from_model(
            session,
            is_current=session.token == token,
            lifetime_seconds=conf.api.v1.auth.token_lifetime_seconds,
        )
        for session in sessions
    ]


@router.delete(
    "/{session_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Завершить сессию",
)
async def revoke_session(
    user_token: Annotated[tuple["User", str], Depends(current_active_user_token)],
    service: Annotated["SessionService", Depends(get_session_service)],
    session_id: Annotated[uuid.UUID, Path(description="Идентификатор сессии")],
):
    """Завершает одну сессию пользователя.

    Текущую сессию завершить можно — это эквивалент выхода с устройства,
    которым пользователь сейчас пользуется.
    """
    user, _ = user_token

    await service.revoke_session(user.id, session_id)

    return


@router.delete(
    "",
    response_model=SessionRevokedResponse,
    summary="Завершить все сессии, кроме текущей",
)
async def revoke_other_sessions(
    user_token: Annotated[tuple["User", str], Depends(current_active_user_token)],
    service: Annotated["SessionService", Depends(get_session_service)],
):
    """Выход со всех остальных устройств.

    Текущая сессия сохраняется: иначе пользователь, нажавший "выйти везде",
    разлогинивал бы и себя.
    """
    user, token = user_token

    revoked = await service.revoke_other_sessions(user.id, token)

    return SessionRevokedResponse(revoked=revoked)
