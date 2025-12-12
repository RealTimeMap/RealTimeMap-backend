from typing import TYPE_CHECKING, Annotated

from fastapi import Depends

from database import get_session
from database.adapter import PgAdapter
from modules import UserSubscription
from modules.user_subscription.repository import PgUserSubscriptionRepository
from modules.user_subscription.schemas import (
    UpdateUserSubscription,
    CreateUserSubscription,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession
    from core.common.repository import UserSubscriptionRepository


def get_user_subscription_repository(
    session: Annotated["AsyncSession", Depends(get_session)],
) -> "UserSubscriptionRepository":
    adapter = PgAdapter[
        UserSubscription, CreateUserSubscription, UpdateUserSubscription
    ](session, UserSubscription)
    return PgUserSubscriptionRepository(adapter=adapter)
