from typing import AsyncGenerator, Annotated, Any, TYPE_CHECKING

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_session
from database.adapter import PgAdapter
from modules.user_subscription.dependencies import get_user_subscription_repository
from .model import SubscriptionPlan
from .repository import PgSubscriptionPlanRepository
from .schemas import CreateSubscriptionPlan, UpdateSubscriptionPlan
from .service import SubscriptionService

if TYPE_CHECKING:
    from core.common.repository import SubscriptionPlanRepository, UserSubscriptionRepository


async def get_pg_subscription_plan_repository(
    session: Annotated["AsyncSession", Depends(get_session)],
) -> "SubscriptionPlanRepository":
    adapter = PgAdapter[
        SubscriptionPlan, CreateSubscriptionPlan, UpdateSubscriptionPlan
    ](session, SubscriptionPlan)
    return PgSubscriptionPlanRepository(adapter=adapter)


async def get_subscription_service(
    user_subscription_repo: Annotated[
        "UserSubscriptionRepository", Depends(get_user_subscription_repository)
    ],
    subscription_repo: Annotated[
        "SubscriptionPlanRepository", Depends(get_pg_subscription_plan_repository)
    ],
) -> AsyncGenerator[SubscriptionService, Any]:
    yield SubscriptionService(user_subscription_repo, subscription_repo)
