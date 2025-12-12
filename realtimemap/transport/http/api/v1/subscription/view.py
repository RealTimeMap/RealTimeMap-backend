from typing import Annotated, List, TYPE_CHECKING

from fastapi import APIRouter, Depends, Request
from fastapi.responses import ORJSONResponse

from dependencies.payment import get_yookassa_client
from integrations.payment.yookassa import YookassaClient
from modules.subscription.dependencies import (
    get_pg_subscription_plan_repository,
    get_subscription_service,
)
from modules.subscription.repository import PgSubscriptionPlanRepository
from modules.subscription.schemas import ReadSubscriptionPlan
from modules.subscription.service import SubscriptionService
from modules.user_subscription.schemas import CreateSubscriptionRequest
from transport.http.api.v1.auth.fastapi_users import get_current_user_without_ban

if TYPE_CHECKING:
    from modules import User


router = APIRouter(
    prefix="/subscription",
    tags=["subscription"],
)

get_sub_repo = Annotated[
    PgSubscriptionPlanRepository, Depends(get_pg_subscription_plan_repository)
]


@router.get("/", response_model=List[ReadSubscriptionPlan])
async def get_subscription_plans(repo: get_sub_repo):
    result = await repo.get_subscription_plans()
    return result


@router.post(
    "/",
    status_code=200,
    responses={
        200: {
            "description": "Purchase subscription",
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "properties": {"payment_url": {"type": "string"}},
                    }
                }
            },
        },
        400: {
            "description": "Already have active subscription",
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "properties": {"detail": {"type": "string"}},
                    }
                }
            },
        },
        502: {
            "description": "Payment service unavailable",
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "properties": {"detail": {"type": "string"}},
                    }
                }
            },
        },
    },
)
async def purchase_subscription(
    data: CreateSubscriptionRequest,
    user: Annotated["User", Depends(get_current_user_without_ban)],
    service: Annotated["SubscriptionService", Depends(get_subscription_service)],
    payment_client: Annotated["YookassaClient", Depends(get_yookassa_client)],
    request: Request,
):
    payment_url = await service.create_subscription_offer(
        data.plan_id, user, payment_client, str(request.url)
    )
    return ORJSONResponse({"payment_url": payment_url})
