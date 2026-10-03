from datetime import datetime, timezone
from typing import TYPE_CHECKING, Annotated, List, Optional

from fastapi import APIRouter, Depends, Path, status

from errors.http2 import IntegrityError, NotFoundError, UserPermissionError
from modules.rbac.catalog import USER_BAN_MANAGE, USER_BAN_READ, USER_SESSION_MANAGE
from modules.rbac.dependencies import get_rbac_service
from modules.rbac.service import RbacService
from modules.user_ban.dependencies import get_user_ban_repository
from modules.user_session.dependencies import get_session_service
from modules.user_ban.repository import PgUsersBanRepository
from modules.user_ban.schemas import (
    BanCreateRequest,
    BanRead,
    UpdateUsersBan,
    UsersBanCreate,
)
from ..auth.permissions import require_permission

if TYPE_CHECKING:
    from modules.user.model import User
    from modules.user_session.service import SessionService


router = APIRouter(prefix="/bans", tags=["Bans"])

UserId = Annotated[int, Path(description="ID пользователя")]
BanRepo = Annotated[PgUsersBanRepository, Depends(get_user_ban_repository)]
Rbac = Annotated[RbacService, Depends(get_rbac_service)]
Sessions = Annotated["SessionService", Depends(get_session_service)]


def _to_naive_utc(value: Optional[datetime]) -> Optional[datetime]:
    """Снимает таймзону, приведя время к UTC.

    Колонки UsersBan объявлены как DateTime без timezone=True, а фронт
    присылает ISO с суффиксом Z — asyncpg такой datetime в naive-колонку
    не пишет и падает с 500.
    """
    if value is None:
        return None
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


async def _ensure_can_moderate(
    actor: "User", target_id: int, rbac: RbacService
) -> None:
    """Блокировать можно только тех, кто ниже рангом.

    Без этой проверки модератор забанил бы администратора или сам себя —
    тот же принцип, что в RbacService._ensure_target для выдачи ролей.
    """
    if actor.id == target_id:
        raise UserPermissionError(detail="Нельзя заблокировать самого себя")

    # get_user сам бросает NotFoundError, если пользователя нет.
    target = await rbac.get_user(target_id)

    actor_access = await rbac.get_access(actor)
    target_access = await rbac.get_access(target)

    # Суперпользователь неприкосновенен для всех, кроме суперпользователя.
    if target.is_superuser and not actor.is_superuser:
        raise UserPermissionError(detail="Недостаточно прав для этого пользователя")

    if not actor.is_superuser and target_access.priority >= actor_access.priority:
        raise UserPermissionError(detail="Недостаточно прав для этого пользователя")


@router.get(
    "/users/{user_id}",
    response_model=List[BanRead],
    summary="История банов пользователя",
    dependencies=[Depends(require_permission(USER_BAN_READ))],
)
async def list_user_bans(user_id: UserId, bans: BanRepo):
    return [BanRead.model_validate(b) for b in await bans.get_user_bans(user_id)]


@router.post(
    "/users/{user_id}",
    response_model=BanRead,
    status_code=status.HTTP_201_CREATED,
    summary="Заблокировать пользователя",
)
async def ban_user(
    user_id: UserId,
    data: BanCreateRequest,
    bans: BanRepo,
    rbac: Rbac,
    actor: Annotated["User", Depends(require_permission(USER_BAN_MANAGE))],
):
    await _ensure_can_moderate(actor, user_id, rbac)

    if await bans.get_active_user_ban(user_id) is not None:
        raise IntegrityError(detail="Пользователь уже заблокирован")

    ban = await bans.ban_user(
        UsersBanCreate(
            user_id=user_id,
            moderator_id=actor.id,
            reason=data.reason,
            reason_text=data.reason_text,
            is_permanent=data.is_permanent,
            banned_until=_to_naive_utc(data.banned_until),
        )
    )
    return BanRead.model_validate(ban)


@router.delete(
    "/users/{user_id}",
    response_model=BanRead,
    summary="Снять блокировку",
)
async def unban_user(
    user_id: UserId,
    bans: BanRepo,
    rbac: Rbac,
    actor: Annotated["User", Depends(require_permission(USER_BAN_MANAGE))],
):
    await _ensure_can_moderate(actor, user_id, rbac)

    if await bans.get_active_user_ban(user_id) is None:
        raise NotFoundError(detail="Активная блокировка не найдена")

    ban = await bans.unban_user(
        user_id,
        UpdateUsersBan(
            unbanned_at=_to_naive_utc(datetime.now(timezone.utc)),
            unbanned_by=actor.id,
        ),
    )
    return BanRead.model_validate(ban)


@router.get(
    "/users/{user_id}/active",
    response_model=Optional[BanRead],
    summary="Действующая блокировка пользователя",
    dependencies=[Depends(require_permission(USER_BAN_READ))],
)
async def active_ban(user_id: UserId, bans: BanRepo):
    ban = await bans.get_active_user_ban(user_id)
    return BanRead.model_validate(ban) if ban else None


@router.delete(
    "/users/{user_id}/sessions",
    summary="Завершить все сессии пользователя",
)
async def revoke_user_sessions(
    user_id: UserId,
    sessions: Sessions,
    rbac: Rbac,
    actor: Annotated["User", Depends(require_permission(USER_SESSION_MANAGE))],
):
    """Выкидывает пользователя со всех устройств.

    Отдельно от бана: иногда нужно прервать сессии (угнанный аккаунт),
    не блокируя сам аккаунт. Ограничение по рангу то же, что у бана —
    модератор не может разлогинить администратора.
    """
    await _ensure_can_moderate(actor, user_id, rbac)

    revoked = await sessions.revoke_all_sessions(user_id)
    return {"revoked": revoked}
