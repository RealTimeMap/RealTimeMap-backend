from typing import Annotated, TYPE_CHECKING

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_session
from database.adapter import PgAdapter
from modules.gamefication.repository import (
    PgLevelRepository,
    PgUserExpHistoryRepository,
    PgExpActionRepository,
)
from modules.gamefication.service import GameFicationService
from modules.user.dependencies import get_pg_user_repository
from modules.user_subscription.dependencies import get_user_subscription_repository
from modules.user_subscription.repository import PgUserSubscriptionRepository
from .model import Level, UserExpHistory, ExpAction
from .schemas import CreateUserExpHistory, UpdateUserExpHistory

if TYPE_CHECKING:
    from core.common.repository import (
        LevelRepository,
        ExpActionRepository,
        UserExpHistoryRepository,
        UserRepository,
    )

DBSession = Annotated[AsyncSession, Depends(get_session)]


def get_pg_level_repository(
    session: DBSession,
) -> "LevelRepository":
    adapter = PgAdapter[Level, None, None](session, Level)
    return PgLevelRepository(adapter=adapter)


async def get_pg_exp_action_repository(
    session: DBSession,
) -> "ExpActionRepository":
    adapter = PgAdapter[ExpAction, None, None](session, ExpAction)
    return PgExpActionRepository(adapter=adapter)


async def get_pg_user_exp_history_repository(
    session: DBSession,
) -> "UserExpHistoryRepository":
    adapter = PgAdapter[UserExpHistory, CreateUserExpHistory, UpdateUserExpHistory](
        session, UserExpHistory
    )
    return PgUserExpHistoryRepository(adapter=adapter)


async def get_game_fication_service(
    history_repo: Annotated[
        "UserExpHistoryRepository", Depends(get_pg_user_exp_history_repository)
    ],
    action_repo: Annotated[
        "ExpActionRepository", Depends(get_pg_exp_action_repository)
    ],
    level_repo: Annotated["LevelRepository", Depends(get_pg_level_repository)],
    user_repo: Annotated["UserRepository", Depends(get_pg_user_repository)],
    user_subs_repo: Annotated[
        "PgUserSubscriptionRepository", Depends(get_user_subscription_repository)
    ],
) -> "GameFicationService":
    return GameFicationService(
        history_repo, action_repo, level_repo, user_repo, user_subs_repo
    )


async def get_gamefication_service(session: DBSession) -> "GameFicationService":
    history_repo = await get_pg_user_exp_history_repository(session)
    action_repo = await get_pg_exp_action_repository(session)
    level_repo = await get_pg_level_repository(session)
    user_repo = await get_pg_user_repository(session)
    user_subs_repo = await get_user_subscription_repository(session)
    return GameFicationService(
        history_repo, action_repo, level_repo, user_repo, user_subs_repo
    )
