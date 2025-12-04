import logging
from decimal import Decimal
from typing import TYPE_CHECKING, Optional, Tuple

from pydantic import BaseModel, Field

from modules.gamefication.schemas import LevelCreate
from modules.user.schemas import UserGameFicationUpdate
from .model import ExpAction, UserExpHistory
from .schemas import CreateUserExpHistory

if TYPE_CHECKING:
    from core.common.repository import (
        UserExpHistoryRepository,
        ExpActionRepository,
        LevelRepository,
        UserSubscriptionRepository,
    )
    from modules import User
    from core.common.repository import UserRepository

logger = logging.getLogger(__name__)


class ExpCalculation(BaseModel):
    base_exp: int
    multiplier: Decimal = Field(Decimal(1.0))
    final_exp: int
    subscription_plan_id: Optional[int] = None


class GameFicationService:
    """
    Сервисный класс Геймификации

    Начисляет опыт/Повышает уровень пользователя на основе конфигурации уровней и конфигов из БД

    При любой ошибке не остонваливает выполнение десвия откуда она была вызвана

    # P.S Может требовтаь доработки!
    """

    def __init__(
        self,
        history_repo: "UserExpHistoryRepository",
        action_repo: "ExpActionRepository",
        level_repo: "LevelRepository",
        user_repo: "UserRepository",
        user_subs_repo: "UserSubscriptionRepository",
    ):
        self.user_repo = user_repo
        self.history_repo = history_repo
        self.action_repo = action_repo
        self.level_repo = level_repo
        self.user_subs_repo = user_subs_repo

    async def great_user_exp(
        self, user: "User", action_type: str
    ) -> Optional[UserExpHistory]:
        logger.info(f"Great user exp action: {action_type} for user: {user.id}")
        try:
            # Получение конфига из бд
            action = await self._get_action(action_type)
            if not action:
                logger.info("Not found active action")
                return None

            can_grant, reason = await self._check_all_limits(user.id, action)
            if not can_grant:
                logger.info(f"Exp grant denied: user_id: {user.id} reason: {reason}")
                return None

            current_level = await self.level_repo.get_level(user.level)
            next_level_exists = await self.level_repo.exist(user.level + 1, "level")
            if not next_level_exists:
                logger.info(f"{user.id} user achieved max level, create new")
                new_level_data = LevelCreate(
                    level=current_level.level + 1 if current_level else 1,
                    required_exp=current_level.required_exp if current_level else None,
                )
                await self.level_repo.create(new_level_data)
            exp_calculation = await self._calculate_final_exp(user, action)
            level_before = user.level
            exp_before = user.current_exp

            await self._update_user_experience(user, exp_calculation.final_exp)
            level_after = await self.user_repo.get_level_up(user.id)

            history = await self._create_history_record(
                user,
                action,
                exp_calculation,
                level_before,
                level_after,
                exp_before,
            )
            return history
        except Exception as e:
            logger.error("GameFicationService.great_user_exp", e)
            return None

    async def _calculate_final_exp(
        self, user: "User", action: "ExpAction"
    ) -> ExpCalculation:
        base_exp = action.base_exp
        multiplier = Decimal("1.0")
        subscription_plan_id = None
        user_sub = await self.user_subs_repo.get_active_subscription(user.id)
        if user_sub:
            exp_multiplier = user_sub.plan.features.get("exp_multiplier")
            if exp_multiplier:
                try:
                    multiplier = Decimal(exp_multiplier)
                    subscription_plan_id = user_sub.plan_id

                except (ValueError, TypeError):
                    logger.error(
                        f"Invalid exp_multiplier: {multiplier}. Using default exp_multiplier: 1"
                    )
                    multiplier = Decimal("1.0")

        final_exp = int(base_exp * multiplier)

        return ExpCalculation(
            base_exp=base_exp,
            multiplier=multiplier,
            final_exp=final_exp,
            subscription_plan_id=subscription_plan_id,
        )

    async def _check_all_limits(
        self, user_id: int, action: "ExpAction"
    ) -> Tuple[bool, Optional[str]]:
        if not action.is_repeatable:
            already_granted = await self._check_if_already_granted(user_id, action.id)
            if already_granted:
                return False, "not_repeatable"

        if action.max_per_day:
            can_grant = await self._check_daily_limits(
                user_id, action.id, action.max_per_day
            )
            if not can_grant:
                return False, "daily_limit_reached"

        # TODO Можно сделать события на недельный/временной лимит

        return True, None

    async def _create_history(self, data: CreateUserExpHistory):
        history = await self.history_repo.create(data)
        return history

    async def _get_action(self, action_type: str) -> Optional[ExpAction]:
        action = await self.action_repo.get_action_by_type(action_type)
        return action

    async def _check_if_already_granted(self, user_id: int, action_id: int) -> bool:
        result = await self.history_repo.check_if_user_alredy_granted(
            user_id, action_id
        )
        return result

    async def _check_daily_limits(
        self, user_id: int, action_id: int, daily_limits: int
    ) -> bool:
        """
        Проверка на дневные лимиты начисления опыта. Возвращает Fasle если дневные лимиты на данное событие превышены
        :param user_id: Айди пользователя
        :param action_id: Айди действия
        :param daily_limits: Дневные лимиты
        :return: False если лимиты превышены
        """
        try:
            user_limits = await self.history_repo.get_user_daily_limit_by_action(
                user_id, action_id
            )
            if user_limits >= daily_limits:
                return False
            return True
        except Exception as e:
            logger.error("GameFicationService._check_daily_limits", e)
            return False

    async def _update_user_experience(self, user: "User", final_exp: int) -> None:
        update_data = UserGameFicationUpdate(
            total_exp=user.total_exp + final_exp,
            curent_exp=user.current_exp,  # Временное значение
        )

        await self.user_repo.update(user.id, update_data)

    async def _create_history_record(
        self,
        user: "User",
        action: "ExpAction",
        exp_calculation: "ExpCalculation",
        level_before: int,
        level_after: int,
        exp_before: int,
        source_type: Optional[str] = None,
        source_id: Optional[int] = None,
        *args,
        **kwargs,
    ):
        history_data = CreateUserExpHistory(
            **exp_calculation.model_dump(exclude={"final_exp"}),
            user_id=user.id,
            action_id=action.id,
            total_exp=exp_calculation.final_exp,
            level_before=level_before,
            level_after=level_after,
            exp_before=exp_before,
            source_type=source_type,
            source_id=source_id,
        )
        history = await self.history_repo.create(history_data)
        return history
