"""Изоляция unit-тестов от общих фикстур.

Корневой tests/conftest.py требует mode=test и живой Postgres: его autouse-
фикстуры проверяют расширения и пересоздают схему. Тестам формата событий не
нужно ни то, ни другое — они разбирают словари. Одноимённые фикстуры здесь
перекрывают родительские для этого каталога.
"""

from typing import Iterator

import pytest


@pytest.fixture(scope="session", autouse=True)
def check_conf() -> None:
    """Заглушка: проверка режима относится к интеграционным тестам."""
    return None


@pytest.fixture(scope="session", autouse=True)
def db_extension() -> Iterator[None]:
    """Заглушка: расширения Postgres этим тестам не нужны."""
    yield


@pytest.fixture(scope="session", autouse=True)
def setup_db() -> None:
    """Заглушка: схема не нужна, обращений к БД в этих тестах нет."""
    return None
