from datetime import datetime, timezone, timedelta
from typing import Optional, TYPE_CHECKING

import grpc
from google.protobuf.timestamp_pb2 import Timestamp

from core.config import conf
from database.helper import db_helper
from modules.user.dependencies import get_pg_user_repository
from modules.user.model import AccessToken
from modules.user_ban.dependencies import get_user_ban_repository
from modules.user_session.service import SessionService
from transport.grpc.generated import user_admin_service_pb2 as pb
from transport.grpc.generated.user_admin_service_pb2_grpc import (
    UserAdminServiceServicer,
)

if TYPE_CHECKING:
    from modules import User
    from modules.user_ban.model import UsersBan

MAX_PAGE_SIZE = 100
MAX_BAN_BATCH = 500


def _ts(value: Optional[datetime]) -> Optional[Timestamp]:
    if value is None:
        return None
    # Naive-время в БД хранится в UTC.
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    ts = Timestamp()
    ts.FromDatetime(value)
    return ts


def _avatar_url(user: "User") -> str:
    if not user.avatar:
        return ""
    return f"{conf.server.base_url}/media/{user.avatar.path}"


def _to_user(user: "User") -> pb.User:
    return pb.User(
        id=user.id,
        username=user.username,
        email=user.email,
        phone=user.phone or "",
        avatar=_avatar_url(user),
        is_active=user.is_active,
        is_superuser=user.is_superuser,
        is_verified=user.is_verified,
        level=user.level,
        current_exp=user.current_exp,
        total_exp=user.total_exp,
        created_at=_ts(user.created_at),
        updated_at=_ts(user.updated_at),
        oauth_providers=[a.oauth_name for a in user.oauth_accounts],
    )


def _to_ban(ban: "UsersBan") -> pb.Ban:
    return pb.Ban(
        id=ban.id,
        user_id=ban.user_id,
        reason=str(getattr(ban.reason, "value", ban.reason)),
        reason_text=ban.reason_text or "",
        banned_at=_ts(ban.banned_at),
        banned_until=_ts(ban.banned_until),
        is_permanent=bool(ban.is_permanent),
        moderator_id=ban.moderator_id,
    )


class UserAdminService(UserAdminServiceServicer):
    async def ListUsers(self, request, context):
        page = max(request.page, 1)
        page_size = min(max(request.page_size, 1), MAX_PAGE_SIZE)
        async with db_helper.session_factory() as session:
            repo = get_pg_user_repository(session)
            items, total = await repo.list_for_admin(
                offset=(page - 1) * page_size,
                limit=page_size,
                search=request.search.strip() or None,
                is_active=request.is_active if request.HasField("is_active") else None,
                is_superuser=(
                    request.is_superuser if request.HasField("is_superuser") else None
                ),
            )
            return pb.ListUsersResponse(
                items=[_to_user(u) for u in items], total=total
            )

    async def GetUser(self, request, context):
        async with db_helper.session_factory() as session:
            repo = get_pg_user_repository(session)
            user = await repo.get_by_id(request.id)
            if user is None:
                await context.abort(
                    grpc.StatusCode.NOT_FOUND, f"User with id {request.id} not found"
                )
            return _to_user(user)

    async def GetActiveBans(self, request, context):
        if len(request.user_ids) > MAX_BAN_BATCH:
            await context.abort(
                grpc.StatusCode.INVALID_ARGUMENT,
                f"user_ids must contain at most {MAX_BAN_BATCH} items",
            )
        async with db_helper.session_factory() as session:
            repo = get_user_ban_repository(session)
            bans = await repo.get_active_bans(list(set(request.user_ids)))
            return pb.GetActiveBansResponse(bans=[_to_ban(b) for b in bans])

    async def ListSessions(self, request, context):
        lifetime = conf.api.v1.auth.token_lifetime_seconds
        async with db_helper.session_factory() as session:
            service = SessionService(AccessToken.get_db(session), lifetime)
            tokens = await service.list_sessions(request.user_id)
            sessions = []
            for t in tokens:
                created_at = t.created_at
                if created_at.tzinfo is None:
                    created_at = created_at.replace(tzinfo=timezone.utc)
                sessions.append(
                    pb.Session(
                        session_id=str(t.session_id),
                        device_name=t.device_name or "",
                        user_agent=t.user_agent or "",
                        ip_address=t.ip_address or "",
                        created_at=_ts(created_at),
                        last_used_at=_ts(t.last_used_at),
                        expires_at=_ts(created_at + timedelta(seconds=lifetime)),
                    )
                )
            return pb.ListSessionsResponse(sessions=sessions)
