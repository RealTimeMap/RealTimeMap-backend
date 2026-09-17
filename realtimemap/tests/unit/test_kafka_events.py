"""Формат событий и разбор входящих сообщений.

Формат — контракт с Go-сервисами: переименование ключа здесь молча ломает
разбор на той стороне, и поймать это можно только такой проверкой.
"""

import orjson
import pytest

from integrations.kafka.consumer import _extract
from integrations.kafka.events import (
    PROFILE_UPDATED,
    USER_UPDATED,
    make_envelope,
    user_registered_payload,
    user_updated_payload,
)


def test_registered_payload_carries_admin_flag():
    """social-service заводит профиль из этого события и спросить права не может."""
    plain = user_registered_payload(
        user_id=1,
        username="bob",
        email="bob@example.com",
        phone=None,
        is_verified=True,
        oauth=False,
    )
    assert plain["is_admin"] is False, "обычная регистрация не поднимает админку"

    admin = user_registered_payload(
        user_id=2,
        username="root",
        email="root@example.com",
        phone=None,
        is_verified=True,
        oauth=False,
        is_admin=True,
    )
    assert admin["is_admin"] is True


def test_updated_payload_always_has_admin_key():
    """Потребитель отличает явный False (админка снята) от отсутствия ключа."""
    revoked = user_updated_payload(user_id=7, is_admin=False)
    assert revoked == {"user_id": 7, "is_admin": False}
    assert "is_admin" in revoked

    granted = user_updated_payload(user_id=7, is_admin=True)
    assert granted["is_admin"] is True


def test_envelope_shape_matches_go_contract():
    """Конверт разбирается Go-потребителем: type и payload на верхнем уровне."""
    envelope = make_envelope(USER_UPDATED, user_updated_payload(7, True))

    assert envelope["type"] == USER_UPDATED
    assert envelope["payload"] == {"user_id": 7, "is_admin": True}
    assert envelope["id"], "id нужен потребителям для дедупликации"
    assert envelope["timestamp"]


@pytest.mark.parametrize(
    "raw, case",
    [
        (
            {
                "id": "abc",
                "type": PROFILE_UPDATED,
                "timestamp": "2026-09-17T00:00:00Z",
                "payload": {"user_id": 7, "username": "newname"},
            },
            "конверт",
        ),
        (
            {"event_type": PROFILE_UPDATED, "user_id": 7, "username": "newname"},
            "плоский формат",
        ),
    ],
)
def test_extract_reads_both_formats(raw, case):
    """Тип берётся из тела: headers может потерять промежуточный компонент."""
    event_type, payload = _extract(orjson.dumps(raw))

    assert event_type == PROFILE_UPDATED, case
    assert payload["user_id"] == 7, case
    assert payload["username"] == "newname", case


def test_extract_rejects_non_object():
    """Битое сообщение должно отбраковываться, а не валить цикл чтения."""
    with pytest.raises(ValueError):
        _extract(orjson.dumps([1, 2, 3]))
