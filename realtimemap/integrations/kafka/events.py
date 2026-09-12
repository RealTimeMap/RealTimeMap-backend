"""Формат доменных событий, общий с Go-сервисами.

Событие едет в Kafka конвертом:

    {"id": "...", "type": "user.registered", "timestamp": "...", "payload": {...}}

Та же мета дублируется в headers (event_type, user_id, source_id, timestamp).
Дублирование намеренное: headers позволяют отфильтровать событие, не разбирая
тело, а тело остаётся самодостаточным — сообщение из дампа топика читается без
заголовков.

Зеркало pkg/transport/kafka/events в Go-репозитории. Менять формат нужно с
двух сторон одновременно.
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

# Типы событий. Значения обязаны совпадать с константами в
# pkg/transport/kafka/events/user.go.
USER_REGISTERED = "user.registered"
USER_UPDATED = "user.updated"
USER_DELETED = "user.deleted"

# События, по которым smtp-service отправляет письма аккаунта.
#
# Ссылки и токены кладутся в payload: подписаны они секретом этого сервиса, и
# восстановить их на стороне smtp-service нельзя. Адрес получателя тоже едет в
# событии — письмо о смене пароля или входе должно уйти даже когда gRPC
# UserService недоступен.
USER_VERIFY_REQUESTED = "user.verify_requested"
USER_PASSWORD_FORGOTTEN = "user.password_forgotten"
USER_PASSWORD_CHANGED = "user.password_changed"
USER_LOGGED_IN = "user.logged_in"


def make_envelope(event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Собирает конверт события.

    id нужен потребителям для дедупликации: Kafka даёт at-least-once, и после
    ребаланса группы одно и то же событие может приехать дважды.
    """
    return {
        "id": str(uuid.uuid4()),
        "type": event_type,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "payload": payload,
    }


def make_headers(
    event_type: str,
    user_id: Optional[int] = None,
    source_id: Optional[int] = None,
) -> list[tuple[str, bytes]]:
    """Собирает headers сообщения.

    aiokafka ждёт список пар (ключ, bytes) — не dict и не str в значении.
    Ключи совпадают с pkg/transport/kafka/headers.go.
    """
    headers: list[tuple[str, bytes]] = [
        ("event_type", event_type.encode("utf-8")),
        ("timestamp", datetime.now(timezone.utc).isoformat().encode("utf-8")),
    ]
    if user_id is not None:
        headers.append(("user_id", str(user_id).encode("utf-8")))
    if source_id is not None:
        headers.append(("source_id", str(source_id).encode("utf-8")))
    return headers


def user_registered_payload(
    user_id: int,
    username: str,
    email: str,
    phone: Optional[str],
    is_verified: bool,
    oauth: bool,
) -> dict[str, Any]:
    """Payload события регистрации.

    Ключи совпадают с UserRegisteredPayload в Go — переименование поля здесь
    молча ломает разбор на стороне smtp-service.
    """
    return {
        "user_id": user_id,
        "username": username,
        "email": email,
        "phone": phone,
        "is_verified": is_verified,
        "oauth": oauth,
        "registered_at": datetime.now(timezone.utc).isoformat(),
    }


def verify_requested_payload(
    user_id: int,
    username: str,
    email: str,
    verify_url: str,
    code: str = "",
    ttl_minutes: int = 30,
) -> dict[str, Any]:
    """Payload запроса подтверждения адреса."""
    return {
        "user_id": user_id,
        "username": username,
        "email": email,
        "verify_url": verify_url,
        "code": code,
        "ttl_minutes": ttl_minutes,
    }


def password_forgotten_payload(
    user_id: int,
    username: str,
    email: str,
    reset_url: str,
    ttl_minutes: int = 60,
    device: Optional[str] = None,
    ip_address: Optional[str] = None,
) -> dict[str, Any]:
    """Payload запроса на сброс пароля."""
    return {
        "user_id": user_id,
        "username": username,
        "email": email,
        "reset_url": reset_url,
        "ttl_minutes": ttl_minutes,
        "requested_at": datetime.now(timezone.utc).isoformat(),
        "device": device or "",
        "ip_address": ip_address or "",
    }


def password_changed_payload(
    user_id: int,
    username: str,
    email: str,
    device: Optional[str] = None,
    ip_address: Optional[str] = None,
) -> dict[str, Any]:
    """Payload уже состоявшейся смены пароля."""
    return {
        "user_id": user_id,
        "username": username,
        "email": email,
        "changed_at": datetime.now(timezone.utc).isoformat(),
        "device": device or "",
        "ip_address": ip_address or "",
    }


def logged_in_payload(
    user_id: int,
    username: str,
    email: str,
    device: Optional[str] = None,
    ip_address: Optional[str] = None,
    location: Optional[str] = None,
) -> dict[str, Any]:
    """Payload входа в аккаунт."""
    return {
        "user_id": user_id,
        "username": username,
        "email": email,
        "signed_in_at": datetime.now(timezone.utc).isoformat(),
        "device": device or "",
        "ip_address": ip_address or "",
        "location": location or "",
    }
