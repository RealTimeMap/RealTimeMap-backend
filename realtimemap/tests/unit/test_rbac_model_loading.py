"""Стратегии загрузки связей Role.

Граф ролей разворачивается в RbacService.compute_access уже после того, как
сессия отдала объекты наружу: подгрузить связь там нечем, ленивый запрос в
async-сессии падает с MissingGreenlet. Поэтому связи, которые читает
PgRbacRepository.role_graph, обязаны грузиться заранее.
"""

from sqlalchemy import inspect

import modules  # noqa: F401  регистрирует маппинги до inspect()
from modules.rbac.model import Role

# Связи, которые читает PgRbacRepository.role_graph на уже загруженных ролях.
EAGER_RELATIONSHIPS = ("grants", "parents")


def _relationship(name: str):
    return inspect(Role).relationships[name]


def test_role_graph_relationships_are_eager():
    for name in EAGER_RELATIONSHIPS:
        assert _relationship(name).lazy == "selectin", (
            f"Role.{name} читается вне сессии — ленивая загрузка там невозможна"
        )


def test_self_referential_eager_relationships_declare_join_depth():
    """Без join_depth selectin на связи «сама на себя» не делает ничего.

    SelectInLoader защищается от бесконечной рекурсии: если путь загрузки уже
    содержит тот же маппер, загрузчик молча выходит и связь остаётся пустой —
    ошибка всплывает позже, при первом обращении, и выглядит как MissingGreenlet.
    """
    for name in EAGER_RELATIONSHIPS:
        relationship = _relationship(name)
        if not relationship._is_self_referential:
            continue
        strategy = relationship._get_strategy((("lazy", relationship.lazy),))
        assert strategy.join_depth, (
            f"Role.{name} ссылается на Role: без join_depth selectin не сработает"
        )


def test_role_parents_join_depth_covers_direct_parents():
    """Глубины 1 достаточно: предков выше обходит policy.ancestors в памяти."""
    parents = _relationship("parents")
    strategy = parents._get_strategy((("lazy", parents.lazy),))
    assert strategy.join_depth >= 1
