"""Вычисление итоговых прав: наследование, deny, scope, сроки, wildcard."""

from datetime import datetime, timedelta, timezone

from modules.rbac.model import PermissionEffect
from modules.rbac.policy import (
    Access,
    DirectGrant,
    Grant,
    RoleAssignment,
    RoleNode,
    creates_cycle,
    expand,
    matches,
    resolve,
    superuser_access,
)

ALLOW = PermissionEffect.allow
DENY = PermissionEffect.deny
NOW = datetime(2026, 10, 2, 12, 0, tzinfo=timezone.utc)

CATALOG = [
    "mark.create",
    "mark.delete",
    "mark.comment.delete",
    "chat.message.delete",
    "chat.ban",
    "rbac.role.read",
]


def role(id_, slug, grants=(), parents=(), priority=0):
    return RoleNode(
        id=id_,
        slug=slug,
        priority=priority,
        grants=tuple(Grant(p, e) for p, e in grants),
        parent_ids=tuple(parents),
    )


ROLES = {
    1: role(1, "user", [("mark.create", ALLOW)]),
    2: role(2, "moderator", [("mark.*", ALLOW), ("mark.delete", DENY)], [1], 50),
    3: role(3, "chat-mod", [("chat.*", ALLOW)], [], 10),
    4: role(4, "admin", [("*", ALLOW)], [2], 100),
}


def run(assignments=(), direct=(), defaults=(1,)):
    return resolve(ROLES, defaults, assignments, direct, CATALOG, NOW)


def test_matches_wildcards():
    assert matches("*", "mark.create")
    assert matches("mark.*", "mark.comment.delete")
    assert not matches("mark.*", "marker.create")
    assert not matches("mark.create", "mark.created")


def test_expand_drops_unknown_codes():
    assert expand(["mark.*", "nope.code"], CATALOG) == {
        "mark.create",
        "mark.delete",
        "mark.comment.delete",
    }


def test_default_role_applies_without_assignment():
    access = run()
    assert access.roles == ["user"]
    assert access.permissions == ["mark.create"]
    assert access.priority == 0


def test_inheritance_and_deny_beats_allow():
    access = run([RoleAssignment(2)])
    assert access.has("mark.comment.delete")
    assert access.has("mark.create")
    assert not access.has("mark.delete")
    assert access.priority == 50


def test_deny_inherited_from_parent_survives_wildcard():
    # admin даёт `*`, но наследует deny mark.delete от moderator.
    access = run([RoleAssignment(4)])
    assert access.has("chat.ban")
    assert not access.has("mark.delete")


def test_scoped_role_produces_scoped_permissions():
    access = run([RoleAssignment(3, scope="chat:12")])
    assert "chat-mod@chat:12" in access.roles
    assert access.has("chat.ban", "chat:12")
    assert not access.has("chat.ban", "chat:13")
    assert not access.has("chat.ban")
    # Scoped-роль не поднимает глобальный ранг.
    assert access.priority == 0


def test_global_deny_blocks_scoped_allow():
    access = run(
        [RoleAssignment(3, scope="chat:12")],
        [DirectGrant("chat.ban", DENY)],
    )
    assert not access.has("chat.ban", "chat:12")
    assert access.has("chat.message.delete", "chat:12")


def test_scoped_duplicate_of_global_is_collapsed():
    access = run(
        [RoleAssignment(3), RoleAssignment(3, scope="chat:12")],
    )
    assert "chat.ban" in access.permissions
    assert "chat.ban@chat:12" not in access.permissions


def test_expired_grants_ignored_and_nearest_expiry_reported():
    soon = NOW + timedelta(hours=1)
    later = NOW + timedelta(days=1)
    access = run(
        [
            RoleAssignment(3, expires_at=NOW - timedelta(seconds=1)),
            RoleAssignment(2, expires_at=later),
        ],
        [DirectGrant("chat.ban", ALLOW, expires_at=soon)],
    )
    assert not access.has("chat.message.delete")
    assert access.has("chat.ban")
    assert access.expires_at == soon


def test_direct_deny_overrides_role():
    access = run([RoleAssignment(2)], [DirectGrant("mark.comment.delete", DENY)])
    assert not access.has("mark.comment.delete")


def test_superuser_has_everything():
    access = superuser_access(run())
    assert access.permissions == ["*"]
    assert access.has("anything.at.all", "chat:1")


def test_cycle_detection():
    assert creates_cycle(1, [4], ROLES)  # admin -> moderator -> user
    assert creates_cycle(2, [2], ROLES)
    assert not creates_cycle(3, [1], ROLES)


def test_cycle_in_data_does_not_hang():
    looped = {
        1: role(1, "a", [("mark.create", ALLOW)], [2]),
        2: role(2, "b", [("chat.ban", ALLOW)], [1]),
    }
    access = resolve(looped, [], [RoleAssignment(1)], [], CATALOG, NOW)
    assert access.permissions == ["chat.ban", "mark.create"]


def test_full_catalog_collapses_to_wildcard():
    roles = {9: role(9, "root", [("*", ALLOW)], [], 100)}
    access = resolve(roles, [], [RoleAssignment(9)], [], CATALOG, NOW)
    assert access.permissions == ["*"]
    assert access.has("chat.ban", "chat:1")


def test_wildcard_with_deny_is_expanded():
    access = run([RoleAssignment(4)])
    assert "*" not in access.permissions
    assert "mark.delete" not in access.permissions


def test_access_roundtrip():
    access = run([RoleAssignment(2, expires_at=NOW + timedelta(hours=1))])
    assert Access.from_dict(access.to_dict()) == access
