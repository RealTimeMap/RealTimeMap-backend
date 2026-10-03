from datetime import datetime, timezone
from typing import Annotated, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .model import PermissionEffect
from .policy import (
    PERMISSION_CODE_RE,
    PERMISSION_PATTERN_RE,
    ROLE_SLUG_RE,
    SCOPE_RE,
)


def _check(regex, value: Optional[str], what: str) -> Optional[str]:
    if value is not None and not regex.match(value):
        raise ValueError(f"Invalid {what}: {value!r}")
    return value


def _future(value: Optional[datetime]) -> Optional[datetime]:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    if value <= datetime.now(timezone.utc):
        raise ValueError("expires_at must be in the future")
    return value


# --- Каталог


class PermissionCreate(BaseModel):
    code: Annotated[str, Field(max_length=128, examples=["mark.comment.delete"])]
    service: Annotated[str, Field(max_length=64, examples=["mark-service"])]
    description: Annotated[Optional[str], Field(None, max_length=512)]

    @field_validator("code")
    @classmethod
    def validate_code(cls, v):
        return _check(PERMISSION_CODE_RE, v, "permission code")


class PermissionUpdate(BaseModel):
    description: Annotated[Optional[str], Field(None, max_length=512)]


class PermissionRead(BaseModel):
    id: int
    code: str
    service: str
    description: Optional[str]
    is_system: bool

    model_config = ConfigDict(from_attributes=True)


# --- Роли


class GrantItem(BaseModel):
    permission: Annotated[str, Field(max_length=128, examples=["mark.*"])]
    effect: PermissionEffect = PermissionEffect.allow

    @field_validator("permission")
    @classmethod
    def validate_permission(cls, v):
        return _check(PERMISSION_PATTERN_RE, v, "permission pattern")

    model_config = ConfigDict(from_attributes=True)


class RoleCreate(BaseModel):
    slug: Annotated[str, Field(max_length=64, examples=["chat-moderator"])]
    title: Annotated[str, Field(max_length=128)]
    description: Annotated[Optional[str], Field(None, max_length=512)]
    priority: Annotated[int, Field(0, ge=0, le=10_000)]
    is_default: bool = False
    grants: List[GrantItem] = []
    parents: Annotated[List[str], Field([], description="Слаги ролей-родителей")]

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, v):
        return _check(ROLE_SLUG_RE, v, "role slug")


class RoleUpdate(BaseModel):
    title: Annotated[Optional[str], Field(None, max_length=128)]
    description: Annotated[Optional[str], Field(None, max_length=512)]
    priority: Annotated[Optional[int], Field(None, ge=0, le=10_000)]
    is_default: Optional[bool] = None


class RoleGrantsUpdate(BaseModel):
    grants: List[GrantItem]


class RoleParentsUpdate(BaseModel):
    parents: List[str]


class RoleRead(BaseModel):
    id: int
    slug: str
    title: str
    description: Optional[str]
    priority: int
    is_system: bool
    is_default: bool
    grants: List[GrantItem]
    parents: List[str]

    @classmethod
    def from_model(cls, role) -> "RoleRead":
        return cls(
            id=role.id,
            slug=role.slug,
            title=role.title,
            description=role.description,
            priority=role.priority,
            is_system=role.is_system,
            is_default=role.is_default,
            grants=[GrantItem.model_validate(g) for g in role.grants],
            parents=sorted(p.slug for p in role.parents),
        )


# --- Назначения


class UserRoleAssign(BaseModel):
    role: Annotated[str, Field(description="Слаг роли")]
    scope: Annotated[
        Optional[str],
        Field(None, max_length=128, description="Ресурс, например chat:12"),
    ]
    expires_at: Optional[datetime] = None
    reason: Annotated[Optional[str], Field(None, max_length=256)]

    @field_validator("scope")
    @classmethod
    def validate_scope(cls, v):
        return _check(SCOPE_RE, v, "scope")

    @field_validator("expires_at")
    @classmethod
    def validate_expires_at(cls, v):
        return _future(v)


class UserRoleRead(BaseModel):
    id: int
    role: str
    scope: Optional[str]
    expires_at: Optional[datetime]
    reason: Optional[str]
    granted_at: datetime
    granted_by: Optional[int]

    @classmethod
    def from_model(cls, item) -> "UserRoleRead":
        return cls(
            id=item.id,
            role=item.role.slug,
            scope=item.scope,
            expires_at=item.expires_at,
            reason=item.reason,
            granted_at=item.granted_at,
            granted_by=item.granted_by,
        )


class UserPermissionAssign(BaseModel):
    permission: Annotated[str, Field(max_length=128)]
    effect: PermissionEffect = PermissionEffect.allow
    scope: Annotated[Optional[str], Field(None, max_length=128)]
    expires_at: Optional[datetime] = None
    reason: Annotated[Optional[str], Field(None, max_length=256)]

    @field_validator("permission")
    @classmethod
    def validate_permission(cls, v):
        return _check(PERMISSION_PATTERN_RE, v, "permission pattern")

    @field_validator("scope")
    @classmethod
    def validate_scope(cls, v):
        return _check(SCOPE_RE, v, "scope")

    @field_validator("expires_at")
    @classmethod
    def validate_expires_at(cls, v):
        return _future(v)


class UserPermissionRead(BaseModel):
    id: int
    permission: str
    effect: PermissionEffect
    scope: Optional[str]
    expires_at: Optional[datetime]
    reason: Optional[str]
    granted_at: datetime
    granted_by: Optional[int]

    model_config = ConfigDict(from_attributes=True)


class AccessRead(BaseModel):
    user_id: int
    is_superuser: bool
    roles: List[str]
    permissions: List[str]
    priority: int


class PermissionCheckRead(BaseModel):
    permission: str
    scope: Optional[str]
    allowed: bool
