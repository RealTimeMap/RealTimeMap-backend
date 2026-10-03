"""Удаление аккаунта: проверка пароля, порядок удаления и публикации.

Событие user.deleted стирает данные во всех остальных сервисах, поэтому
важны две вещи: оно не уходит, если удаление не состоялось, и его формат
совпадает с UserDeletedPayload в Go.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi_users import exceptions
from fastapi_users.password import PasswordHelper

from auth import user_manager as user_manager_module
from auth.user_manager import UserManager
from integrations.kafka.events import USER_DELETED, user_deleted_payload

PASSWORD = "CorrectHorse1"


@pytest.fixture
def calls(monkeypatch):
    """Журнал обращений к БД и шине — по нему проверяется порядок."""
    log: list[str] = []

    async def send(**kwargs):
        log.append("publish")
        log.append(kwargs)

    monkeypatch.setattr(user_manager_module.kafka_producer, "send", send)
    return log


@pytest.fixture
def manager(calls):
    user_db = MagicMock()

    async def delete(_user):
        calls.append("db.delete")

    user_db.delete = AsyncMock(side_effect=delete)
    return UserManager(user_db)


@pytest.fixture
def user():
    return SimpleNamespace(
        id=7,
        email="bob@example.com",
        hashed_password=PasswordHelper().hash(PASSWORD),
    )


def test_deleted_payload_matches_go_contract():
    """Ключи совпадают с UserDeletedPayload в pkg/transport/kafka/events."""
    payload = user_deleted_payload(user_id=7, email="bob@example.com")
    assert set(payload) == {"user_id", "email", "deleted_at"}
    assert payload["user_id"] == 7
    assert payload["email"] == "bob@example.com"


@pytest.mark.asyncio
async def test_wrong_password_deletes_nothing(manager, user, calls):
    with pytest.raises(exceptions.InvalidPasswordException):
        await manager.delete_account(user, "wrong-password")

    assert calls == [], "ни удаления, ни события при неверном пароле"


@pytest.mark.asyncio
async def test_event_is_published_after_delete(manager, user, calls):
    await manager.delete_account(user, PASSWORD)

    assert calls[:2] == ["db.delete", "publish"], "событие — только после удаления"

    sent = calls[2]
    assert sent["key"] == "7", "ключ — user_id: порядок событий одного пользователя"
    assert sent["value"]["type"] == USER_DELETED
    assert sent["value"]["payload"]["user_id"] == 7
    assert sent["value"]["payload"]["email"] == "bob@example.com"


@pytest.mark.asyncio
async def test_failed_delete_publishes_nothing(manager, user, calls):
    """Упавшее удаление не должно стирать данные живого пользователя."""
    manager.user_db.delete = AsyncMock(side_effect=RuntimeError("db down"))

    with pytest.raises(RuntimeError):
        await manager.delete_account(user, PASSWORD)

    assert "publish" not in calls
