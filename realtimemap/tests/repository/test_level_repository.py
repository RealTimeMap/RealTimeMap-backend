import pytest

from database.adapter import PgAdapter
from modules.gamefication.repository import PgLevelRepository


class TestLevelRepository:
    """Тесты для NewLevelRepository (LevelRepository)"""

    @pytest.mark.asyncio
    async def test_get_by_id(self, level_adapter: PgAdapter, test_level):
        """Тест получения уровня по ID"""
        repo = PgLevelRepository(adapter=level_adapter)

        level = await repo.get_by_id(test_level.id)

        assert level is not None
        assert level.id == test_level.id
        assert level.level == test_level.level
        assert level.required_exp == test_level.required_exp

    @pytest.mark.asyncio
    async def test_get_by_id_not_found(self, level_adapter: PgAdapter):
        """Тест получения несуществующего уровня"""
        repo = PgLevelRepository(adapter=level_adapter)

        level = await repo.get_by_id(99999)

        assert level is None

    @pytest.mark.asyncio
    async def test_get_levels_count(self, level_adapter: PgAdapter, test_levels):
        """Тест проверки количества созданных уровней"""
        repo = PgLevelRepository(adapter=level_adapter)

        # Проверяем что все уровни созданы
        max_level = await repo.get_max_level()
        assert max_level is not None
        assert max_level.level == 6

    @pytest.mark.asyncio
    async def test_get_next_level(self, level_adapter: PgAdapter, test_levels):
        """Тест получения следующего уровня"""
        repo = PgLevelRepository(adapter=level_adapter)

        next_level = await repo.get_next_level(current_level=1)

        assert next_level is not None
        assert next_level.level == 2
        assert next_level.is_active is True

    @pytest.mark.asyncio
    async def test_get_next_level_from_middle(
        self, level_adapter: PgAdapter, test_levels
    ):
        """Тест получения следующего уровня из середины"""
        repo = PgLevelRepository(adapter=level_adapter)

        # Получаем уровень 4 (следующий после 3)
        next_level = await repo.get_next_level(current_level=3)

        assert next_level is not None
        assert next_level.level == 4
        assert next_level.required_exp == 500

    @pytest.mark.asyncio
    async def test_get_next_level_inactive_skipped(
        self, level_adapter: PgAdapter, test_levels
    ):
        """Тест что неактивный уровень не возвращается"""
        repo = PgLevelRepository(adapter=level_adapter)

        # Уровень 6 неактивен поэтому результат None
        next_level = await repo.get_next_level(current_level=5)

        assert next_level is None

    @pytest.mark.asyncio
    async def test_get_next_level_last_level(
        self, level_adapter: PgAdapter, test_levels
    ):
        """Тест получения следующего уровня когда достигнут максимум"""
        repo = PgLevelRepository(adapter=level_adapter)

        # Вариант для того что уровень был переведен в инактив а следуйщего нету
        next_level = await repo.get_next_level(current_level=6)

        assert next_level is None

    @pytest.mark.asyncio
    async def test_get_next_level_non_existent(
        self, level_adapter: PgAdapter, test_levels
    ):
        """Тест получения следующего уровня для несуществующего текущего уровня"""
        repo = PgLevelRepository(adapter=level_adapter)

        next_level = await repo.get_next_level(current_level=99)

        assert next_level is None

    @pytest.mark.asyncio
    async def test_get_max_level(self, level_adapter: PgAdapter, test_levels):
        """Тест получения максимального уровня"""
        repo = PgLevelRepository(adapter=level_adapter)

        max_level = await repo.get_max_level()

        assert max_level is not None
        assert max_level.level == 6
        assert max_level.required_exp == 2000

    @pytest.mark.asyncio
    async def test_get_max_level_empty(self, level_adapter: PgAdapter):
        """Тест получения максимального уровня когда уровней нет"""
        repo = PgLevelRepository(adapter=level_adapter)

        max_level = await repo.get_max_level()

        assert max_level is None

    @pytest.mark.asyncio
    async def test_get_max_level_single(self, level_adapter: PgAdapter, test_level):
        """Тест получения максимального уровня когда есть только один уровень"""
        repo = PgLevelRepository(adapter=level_adapter)

        max_level = await repo.get_max_level()

        assert max_level is not None
        assert max_level.id == test_level.id
        assert max_level.level == 1

    @pytest.mark.asyncio
    async def test_delete_level(self, level_adapter: PgAdapter, test_level):
        """Тест удаления уровня"""
        repo = PgLevelRepository(adapter=level_adapter)

        result = await repo.delete(test_level.id)

        assert result is not None
        assert result.id == test_level.id

        deleted_level = await repo.get_by_id(test_level.id)
        assert deleted_level is None

    @pytest.mark.asyncio
    async def test_levels_ordered_by_level_number(
        self, level_adapter: PgAdapter, test_levels
    ):
        """Тест что уровни правильно упорядочены по возрастанию"""
        repo = PgLevelRepository(adapter=level_adapter)

        # Проверяем последовательно что уровни идут по возрастанию
        level_1 = await repo.get_by_id(test_levels[0].id)
        level_2 = await repo.get_by_id(test_levels[1].id)
        assert level_1.required_exp < level_2.required_exp

    @pytest.mark.asyncio
    async def test_get_next_level_progression(
        self, level_adapter: PgAdapter, test_levels
    ):
        """Тест последовательного получения следующих уровней"""
        repo = PgLevelRepository(adapter=level_adapter)

        current_level = 1
        expected_levels = [2, 3, 4, 5]

        for expected_level_num in expected_levels:
            next_level = await repo.get_next_level(current_level)
            assert next_level is not None
            assert next_level.level == expected_level_num
            current_level = next_level.level
