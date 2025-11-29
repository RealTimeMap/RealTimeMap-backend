import pytest

from database.adapter import PgAdapter
from modules.gamefication.repository import PgExpActionRepository


class TestExpActionRepository:
    """Тесты для NewExpActionRepository (ActionRepository)"""

    @pytest.mark.asyncio
    async def test_get_by_id(self, exp_action_adapter: PgAdapter, test_exp_action):
        """Тест получения действия по ID"""
        repo = PgExpActionRepository(adapter=exp_action_adapter)

        action = await repo.get_by_id(test_exp_action.id)

        assert action is not None
        assert action.id == test_exp_action.id
        assert action.action_type == test_exp_action.action_type
        assert action.base_exp == test_exp_action.base_exp

    @pytest.mark.asyncio
    async def test_get_by_id_not_found(self, exp_action_adapter: PgAdapter):
        """Тест получения несуществующего действия"""
        repo = PgExpActionRepository(adapter=exp_action_adapter)

        action = await repo.get_by_id(99999)

        assert action is None

    @pytest.mark.asyncio
    async def test_get_multiple_actions(
        self, exp_action_adapter: PgAdapter, test_exp_actions
    ):
        """Тест получения нескольких действий"""
        repo = PgExpActionRepository(adapter=exp_action_adapter)

        # Получаем действия по типу и проверяем что они есть
        action1 = await repo.get_action_by_type("create_mark")
        action2 = await repo.get_action_by_type("create_comment")
        action3 = await repo.get_action_by_type("verify_email")

        assert action1 is not None
        assert action2 is not None
        assert action3 is not None

    @pytest.mark.asyncio
    async def test_get_action_by_type(
        self, exp_action_adapter: PgAdapter, test_exp_actions
    ):
        """Тест получения действия по типу"""
        repo = PgExpActionRepository(adapter=exp_action_adapter)

        action = await repo.get_action_by_type("create_mark")

        assert action is not None
        assert action.action_type == "create_mark"
        assert action.base_exp == 10
        assert action.is_active is True

    @pytest.mark.asyncio
    async def test_get_action_by_type_another(
        self, exp_action_adapter: PgAdapter, test_exp_actions
    ):
        """Тест получения другого действия по типу"""
        repo = PgExpActionRepository(adapter=exp_action_adapter)

        action = await repo.get_action_by_type("create_comment")

        assert action is not None
        assert action.action_type == "create_comment"
        assert action.base_exp == 5
        assert action.max_per_day == 20

    @pytest.mark.asyncio
    async def test_get_action_by_type_not_found(
        self, exp_action_adapter: PgAdapter, test_exp_actions
    ):
        """Тест получения несуществующего действия по типу"""
        repo = PgExpActionRepository(adapter=exp_action_adapter)

        action = await repo.get_action_by_type("non_existent_action")

        assert action is None

    @pytest.mark.asyncio
    async def test_get_action_by_type_inactive(
        self, exp_action_adapter: PgAdapter, test_exp_actions
    ):
        """Тест что неактивное действие не возвращается"""
        repo = PgExpActionRepository(adapter=exp_action_adapter)

        # inactive_action имеет is_active=False
        action = await repo.get_action_by_type("inactive_action")

        assert action is None

    @pytest.mark.asyncio
    async def test_get_action_by_type_only_active(
        self, exp_action_adapter: PgAdapter, test_exp_actions
    ):
        """Тест что возвращаются только активные действия"""
        repo = PgExpActionRepository(adapter=exp_action_adapter)

        # Проверяем активное действие
        active_action = await repo.get_action_by_type("verify_email")
        assert active_action is not None
        assert active_action.is_active is True

        # Проверяем неактивное действие
        inactive_action = await repo.get_action_by_type("inactive_action")
        assert inactive_action is None

    @pytest.mark.asyncio
    async def test_delete_action(self, exp_action_adapter: PgAdapter, test_exp_action):
        """Тест удаления действия"""
        repo = PgExpActionRepository(adapter=exp_action_adapter)

        result = await repo.delete(test_exp_action.id)

        assert result is not None
        assert result.id == test_exp_action.id

        deleted_action = await repo.get_by_id(test_exp_action.id)
        assert deleted_action is None

    @pytest.mark.asyncio
    async def test_action_properties(
        self, exp_action_adapter: PgAdapter, test_exp_actions
    ):
        """Тест проверки различных свойств действий"""
        repo = PgExpActionRepository(adapter=exp_action_adapter)

        # create_mark - повторяемое
        create_mark = await repo.get_action_by_type("create_mark")
        assert create_mark.is_repeatable is True
        assert create_mark.max_per_day == 10

        # verify_email - не повторяемое
        verify_email = await repo.get_action_by_type("verify_email")
        assert verify_email.is_repeatable is False
        assert verify_email.max_per_day == 1
        assert verify_email.base_exp == 50

    @pytest.mark.asyncio
    async def test_action_with_description(
        self, exp_action_adapter: PgAdapter, test_exp_actions
    ):
        """Тест действий с описанием"""
        repo = PgExpActionRepository(adapter=exp_action_adapter)

        action = await repo.get_action_by_type("create_mark")

        assert action.name == "Create Mark"
        assert action.description == "Experience for creating a mark"

    @pytest.mark.asyncio
    async def test_get_action_by_type_case_sensitive(
        self, exp_action_adapter: PgAdapter, test_exp_actions
    ):
        """Тест что поиск по типу чувствителен к регистру"""
        repo = PgExpActionRepository(adapter=exp_action_adapter)

        # Правильный регистр
        action_lower = await repo.get_action_by_type("create_mark")
        assert action_lower is not None

        # Неправильный регистр
        action_upper = await repo.get_action_by_type("CREATE_MARK")
        assert action_upper is None

    @pytest.mark.asyncio
    async def test_multiple_actions_different_exp(
        self, exp_action_adapter: PgAdapter, test_exp_actions
    ):
        """Тест что разные действия имеют разный опыт"""
        repo = PgExpActionRepository(adapter=exp_action_adapter)

        create_mark = await repo.get_action_by_type("create_mark")
        create_comment = await repo.get_action_by_type("create_comment")
        verify_email = await repo.get_action_by_type("verify_email")

        assert create_mark.base_exp == 10
        assert create_comment.base_exp == 5
        assert verify_email.base_exp == 50

        # Проверяем что все разные
        exp_values = {
            create_mark.base_exp,
            create_comment.base_exp,
            verify_email.base_exp,
        }
        assert len(exp_values) == 3
