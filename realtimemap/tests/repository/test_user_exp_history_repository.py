from decimal import Decimal

import pytest

from database.adapter import PgAdapter
from modules.gamefication.model import UserExpHistory
from modules.gamefication.repository import PgUserExpHistoryRepository
from modules.gamefication.schemas import CreateUserExpHistory


class TestUserExpHistoryRepository:
    """Тесты для NewUserExpHistoryRepository (UserExpHistoryRepository)"""

    @pytest.mark.asyncio
    async def test_create_exp_history(
        self, user_exp_history_adapter: PgAdapter, test_user, test_exp_action
    ):
        """Тест создания записи истории опыта"""
        repo = PgUserExpHistoryRepository(adapter=user_exp_history_adapter)

        history_data = CreateUserExpHistory(
            user_id=test_user.id,
            action_id=test_exp_action.id,
            is_revoked=False,
            base_exp=10,
            multiplier=Decimal("1.0"),
            total_exp=10,
            source_type="marks",
            source_id=1,
            level_before=1,
            level_after=1,
            exp_before=0,
            subscription_plan_id=None,
        )

        created_history = await repo.create(history_data)

        assert created_history.id is not None
        assert created_history.user_id == test_user.id
        assert created_history.action_id == test_exp_action.id
        assert created_history.total_exp == 10
        assert created_history.is_revoked is False

    @pytest.mark.asyncio
    async def test_get_by_id(
        self, user_exp_history_adapter: PgAdapter, test_user, test_exp_action
    ):
        """Тест получения записи истории по ID"""
        repo = PgUserExpHistoryRepository(adapter=user_exp_history_adapter)

        # Создаем запись
        history_data = CreateUserExpHistory(
            user_id=test_user.id,
            action_id=test_exp_action.id,
            is_revoked=False,
            base_exp=10,
            multiplier=Decimal("1.0"),
            total_exp=10,
            level_before=1,
            level_after=1,
            exp_before=0,
        )
        created = await repo.create(history_data)

        # Получаем по ID
        history = await repo.get_by_id(created.id)

        assert history is not None
        assert history.id == created.id
        assert history.user_id == test_user.id

    @pytest.mark.asyncio
    async def test_get_user_daily_limit_by_action(
        self, user_exp_history_adapter: PgAdapter, test_user, test_exp_action
    ):
        """Тест подсчета дневного лимита пользователя по действию"""
        repo = PgUserExpHistoryRepository(adapter=user_exp_history_adapter)

        # Создаем 3 записи за сегодня
        for _ in range(3):
            history_data = CreateUserExpHistory(
                user_id=test_user.id,
                action_id=test_exp_action.id,
                is_revoked=False,
                base_exp=10,
                multiplier=Decimal("1.0"),
                total_exp=10,
                level_before=1,
                level_after=1,
                exp_before=0,
            )
            await repo.create(history_data)

        # Проверяем количество
        count = await repo.get_user_daily_limit_by_action(
            user_id=test_user.id, action_id=test_exp_action.id
        )

        assert count == 3

    @pytest.mark.asyncio
    async def test_get_user_daily_limit_by_action_zero(
        self, user_exp_history_adapter: PgAdapter, test_user, test_exp_action
    ):
        """Тест подсчета дневного лимита когда записей нет"""
        repo = PgUserExpHistoryRepository(adapter=user_exp_history_adapter)

        count = await repo.get_user_daily_limit_by_action(
            user_id=test_user.id, action_id=test_exp_action.id
        )

        assert count == 0

    @pytest.mark.asyncio
    async def test_get_user_daily_limit_different_actions(
        self, user_exp_history_adapter: PgAdapter, test_user, test_exp_actions
    ):
        """Тест что дневной лимит считается отдельно для разных действий"""
        repo = PgUserExpHistoryRepository(adapter=user_exp_history_adapter)

        # Создаем 2 записи для первого действия
        for _ in range(2):
            history_data = CreateUserExpHistory(
                user_id=test_user.id,
                action_id=test_exp_actions[0].id,
                is_revoked=False,
                base_exp=10,
                multiplier=Decimal("1.0"),
                total_exp=10,
                level_before=1,
                level_after=1,
                exp_before=0,
            )
            await repo.create(history_data)

        # Создаем 3 записи для второго действия
        for _ in range(3):
            history_data = CreateUserExpHistory(
                user_id=test_user.id,
                action_id=test_exp_actions[1].id,
                is_revoked=False,
                base_exp=5,
                multiplier=Decimal("1.0"),
                total_exp=5,
                level_before=1,
                level_after=1,
                exp_before=0,
            )
            await repo.create(history_data)

        # Проверяем количество для каждого действия
        count1 = await repo.get_user_daily_limit_by_action(
            user_id=test_user.id, action_id=test_exp_actions[0].id
        )
        count2 = await repo.get_user_daily_limit_by_action(
            user_id=test_user.id, action_id=test_exp_actions[1].id
        )

        assert count1 == 2
        assert count2 == 3

    @pytest.mark.asyncio
    async def test_check_if_user_already_granted_false(
        self, user_exp_history_adapter: PgAdapter, test_user, test_exp_action
    ):
        """Тест проверки что пользователь еще не получал опыт"""
        repo = PgUserExpHistoryRepository(adapter=user_exp_history_adapter)

        is_granted = await repo.check_if_user_alredy_granted(
            user_id=test_user.id, action_id=test_exp_action.id
        )

        assert is_granted is False

    @pytest.mark.asyncio
    async def test_check_if_user_already_granted_true(
        self, user_exp_history_adapter: PgAdapter, test_user, test_exp_action
    ):
        """Тест проверки что пользователь уже получал опыт"""
        repo = PgUserExpHistoryRepository(adapter=user_exp_history_adapter)

        # Создаем запись
        history_data = CreateUserExpHistory(
            user_id=test_user.id,
            action_id=test_exp_action.id,
            is_revoked=False,
            base_exp=10,
            multiplier=Decimal("1.0"),
            total_exp=10,
            level_before=1,
            level_after=1,
            exp_before=0,
        )
        await repo.create(history_data)

        # Проверяем
        is_granted = await repo.check_if_user_alredy_granted(
            user_id=test_user.id, action_id=test_exp_action.id
        )

        assert is_granted is True

    @pytest.mark.asyncio
    async def test_check_if_user_already_granted_revoked_ignored(
        self, user_exp_history_adapter: PgAdapter, test_user, test_exp_action
    ):
        """Тест что отозванные записи не учитываются"""
        repo = PgUserExpHistoryRepository(adapter=user_exp_history_adapter)

        # Создаем отозванную запись
        history_data = CreateUserExpHistory(
            user_id=test_user.id,
            action_id=test_exp_action.id,
            is_revoked=True,
            base_exp=10,
            multiplier=Decimal("1.0"),
            total_exp=10,
            level_before=1,
            level_after=1,
            exp_before=0,
        )
        await repo.create(history_data)

        # Проверяем - должна вернуться False, так как запись отозвана
        is_granted = await repo.check_if_user_alredy_granted(
            user_id=test_user.id, action_id=test_exp_action.id
        )

        assert is_granted is False

    @pytest.mark.asyncio
    async def test_check_if_user_already_granted_multiple_users(
        self, user_exp_history_adapter: PgAdapter, test_exp_action
    ):
        """Тест что проверка работает независимо для разных пользователей"""
        repo = PgUserExpHistoryRepository(adapter=user_exp_history_adapter)

        # Создаем двух пользователей
        from modules.user.model import User

        user1 = User(
            email="user1@example.com",
            username="user1",
            hashed_password="pass",
            is_active=True,
            is_superuser=False,
            is_verified=False,
        )
        user2 = User(
            email="user2@example.com",
            username="user2",
            hashed_password="pass",
            is_active=True,
            is_superuser=False,
            is_verified=False,
        )
        user_exp_history_adapter.session.add(user1)
        user_exp_history_adapter.session.add(user2)
        await user_exp_history_adapter.session.flush()

        # Создаем запись только для первого пользователя
        history_data = CreateUserExpHistory(
            user_id=user1.id,
            action_id=test_exp_action.id,
            is_revoked=False,
            base_exp=10,
            multiplier=Decimal("1.0"),
            total_exp=10,
            level_before=1,
            level_after=1,
            exp_before=0,
        )
        await repo.create(history_data)

        # Проверяем
        is_granted_user1 = await repo.check_if_user_alredy_granted(
            user_id=user1.id, action_id=test_exp_action.id
        )
        is_granted_user2 = await repo.check_if_user_alredy_granted(
            user_id=user2.id, action_id=test_exp_action.id
        )

        assert is_granted_user1 is True
        assert is_granted_user2 is False

    @pytest.mark.asyncio
    async def test_delete_exp_history(
        self, user_exp_history_adapter: PgAdapter, test_user, test_exp_action
    ):
        """Тест удаления записи истории опыта"""
        repo = PgUserExpHistoryRepository(adapter=user_exp_history_adapter)

        # Создаем запись
        history_data = CreateUserExpHistory(
            user_id=test_user.id,
            action_id=test_exp_action.id,
            is_revoked=False,
            base_exp=10,
            multiplier=Decimal("1.0"),
            total_exp=10,
            level_before=1,
            level_after=1,
            exp_before=0,
        )
        created = await repo.create(history_data)

        # Удаляем
        result = await repo.delete(created.id)

        assert result is not None
        assert result.id == created.id

        deleted = await repo.get_by_id(created.id)
        assert deleted is None

    @pytest.mark.asyncio
    async def test_exp_history_with_multiplier(
        self,
        user_exp_history_adapter: PgAdapter,
        test_user,
        test_exp_action,
        test_subscription_plan,
    ):
        """Тест записи истории с множителем от подписки"""
        repo = PgUserExpHistoryRepository(adapter=user_exp_history_adapter)

        history_data = CreateUserExpHistory(
            user_id=test_user.id,
            action_id=test_exp_action.id,
            is_revoked=False,
            base_exp=10,
            multiplier=Decimal("1.2"),
            total_exp=12,
            level_before=1,
            level_after=1,
            exp_before=0,
            subscription_plan_id=test_subscription_plan.id,
        )

        created = await repo.create(history_data)

        assert created.base_exp == 10
        assert created.multiplier == Decimal("1.2")
        assert created.total_exp == 12
        assert created.subscription_plan_id == test_subscription_plan.id

    @pytest.mark.asyncio
    async def test_exp_history_with_level_change(
        self, user_exp_history_adapter: PgAdapter, test_user, test_exp_action
    ):
        """Тест записи истории с изменением уровня"""
        repo = PgUserExpHistoryRepository(adapter=user_exp_history_adapter)

        history_data = CreateUserExpHistory(
            user_id=test_user.id,
            action_id=test_exp_action.id,
            is_revoked=False,
            base_exp=100,
            multiplier=Decimal("1.0"),
            total_exp=100,
            level_before=1,
            level_after=2,
            exp_before=90,
        )

        created = await repo.create(history_data)

        assert created.level_before == 1
        assert created.level_after == 2
        assert created.exp_before == 90
        assert created.total_exp == 100

    @pytest.mark.asyncio
    async def test_multiple_exp_history_records(
        self, user_exp_history_adapter: PgAdapter, test_user, test_exp_action
    ):
        """Тест создания нескольких записей истории"""
        repo = PgUserExpHistoryRepository(adapter=user_exp_history_adapter)

        # Создаем несколько записей
        created_ids = []
        for i in range(5):
            history_data = CreateUserExpHistory(
                user_id=test_user.id,
                action_id=test_exp_action.id,
                is_revoked=False,
                base_exp=10,
                multiplier=Decimal("1.0"),
                total_exp=10,
                level_before=1,
                level_after=1,
                exp_before=i * 10,
            )
            created = await repo.create(history_data)
            created_ids.append(created.id)

        # Проверяем что все записи созданы
        assert len(created_ids) == 5

        # Проверяем что можем получить каждую запись
        for record_id in created_ids:
            record = await repo.get_by_id(record_id)
            assert record is not None
            assert isinstance(record, UserExpHistory)
