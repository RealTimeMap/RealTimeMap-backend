import logging
from typing import TYPE_CHECKING

from fastapi import HTTPException

from errors.http2 import GateWayError, NotFoundError, HaveActiveSubscriptionError
from integrations.payment.yookassa.schemas import (
    CreatePayment,
    ConfirmationPayment,
    AmountPayment,
)
from modules.user_subscription.model import PaymentStatus
from modules.user_subscription.schemas import CreateUserSubscription

if TYPE_CHECKING:
    from modules import User, SubscriptionPlan
    from integrations.payment.yookassa import YookassaClient
    from core.common.repository import (
        SubscriptionPlanRepository,
        UserSubscriptionRepository,
    )

logger = logging.getLogger(__name__)


class SubscriptionService:
    def __init__(
        self,
        user_subscription_repo: "UserSubscriptionRepository",
        subscription_repo: "SubscriptionPlanRepository",
    ):
        self.user_subscription_repo = user_subscription_repo
        self.subscription_repo = subscription_repo

    async def check_active_subscription(self, user_id: int) -> None:
        have_active_subscription = (
            await self.user_subscription_repo.check_active_subscription(user_id)
        )
        if have_active_subscription:
            raise HaveActiveSubscriptionError()

    async def create_subscription_offer(
        self,
        plan_id: int,
        user: "User",
        payment_client: "YookassaClient",
        redirect_url: str,
    ) -> str:
        """

        Args:
            plan_id: Id плана платной подписки
            user: Авторизованный пользователь
            payment_client: Тип платежного клиента
            redirect_url: Страница куда пользователь перейдет после оплаты

        Raises:
            - NotFoundError: Если план не найден
            - GateWayError: Ошибка со стороны платежного шлюза
            - HaveActiveSubscriptionError: Если есть действующая подписка
            - Exception: Неизвестная ошибка

        Returns: Возвращает url строку для оплаты счета

        """
        try:
            # Проверка активной подписки
            await self.check_active_subscription(user.id)
            subscription_info: "SubscriptionPlan" = (
                await self.subscription_repo.get_by_id(plan_id)
            )
            if subscription_info is None:
                raise NotFoundError()

            # Формирования запроса к сервису оплаты
            try:
                payment_request = CreatePayment(
                    metadata={
                        "user_id": user.id,
                        "plan_id": subscription_info.id,
                    },
                    capture=True,
                    description=f"Order for confirm {subscription_info.name}",
                    confirmation=ConfirmationPayment(
                        type="redirect", return_url=redirect_url
                    ),
                    amount=AmountPayment(value=subscription_info.price, currency="RUB"),
                )
                # Запрос на создание счета
                payment = payment_client.create_payment(payment_request)
            except Exception:
                logger.error("Failed to create payment", exc_info=True)
                raise GateWayError()

            # TODO мб сначала создать запись бех payment_id сделать счет и позже обновить?
            create_data = CreateUserSubscription(
                user_id=user.id,
                plan_id=subscription_info.id,
                expires_at=subscription_info.expires_at,
                payment_provider_id=payment.id,
                payment_status=PaymentStatus.waiting_for_capture,
                is_active=False,
            )
            # Создаем пустышку для активной подписки пользователя. Если пользователь не оплатит, то мы ее позже удалим
            await self.user_subscription_repo.create_user_subscription(create_data)

            # Возвращаем url для переадресации юзера на оплату
            return payment.confirmation["confirmation_url"]

        except NotFoundError:
            logger.info("Subscription does not exist, %v", plan_id)
            raise
        except GateWayError:
            logger.error("Payment service error", exc_info=True)
            raise
        except HaveActiveSubscriptionError:
            logger.info("User alredy has active subscription, %v", user.id)
            raise
        except Exception as e:
            logger.error("Failed to create subscription offer", e)
            raise HTTPException(status_code=500, detail=str(e))
