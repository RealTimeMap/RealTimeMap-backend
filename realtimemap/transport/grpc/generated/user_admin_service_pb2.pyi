import datetime

from google.protobuf import timestamp_pb2 as _timestamp_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class User(_message.Message):
    __slots__ = ("id", "username", "email", "phone", "avatar", "is_active", "is_superuser", "is_verified", "level", "current_exp", "total_exp", "created_at", "updated_at", "oauth_providers")
    ID_FIELD_NUMBER: _ClassVar[int]
    USERNAME_FIELD_NUMBER: _ClassVar[int]
    EMAIL_FIELD_NUMBER: _ClassVar[int]
    PHONE_FIELD_NUMBER: _ClassVar[int]
    AVATAR_FIELD_NUMBER: _ClassVar[int]
    IS_ACTIVE_FIELD_NUMBER: _ClassVar[int]
    IS_SUPERUSER_FIELD_NUMBER: _ClassVar[int]
    IS_VERIFIED_FIELD_NUMBER: _ClassVar[int]
    LEVEL_FIELD_NUMBER: _ClassVar[int]
    CURRENT_EXP_FIELD_NUMBER: _ClassVar[int]
    TOTAL_EXP_FIELD_NUMBER: _ClassVar[int]
    CREATED_AT_FIELD_NUMBER: _ClassVar[int]
    UPDATED_AT_FIELD_NUMBER: _ClassVar[int]
    OAUTH_PROVIDERS_FIELD_NUMBER: _ClassVar[int]
    id: int
    username: str
    email: str
    phone: str
    avatar: str
    is_active: bool
    is_superuser: bool
    is_verified: bool
    level: int
    current_exp: int
    total_exp: int
    created_at: _timestamp_pb2.Timestamp
    updated_at: _timestamp_pb2.Timestamp
    oauth_providers: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, id: _Optional[int] = ..., username: _Optional[str] = ..., email: _Optional[str] = ..., phone: _Optional[str] = ..., avatar: _Optional[str] = ..., is_active: bool = ..., is_superuser: bool = ..., is_verified: bool = ..., level: _Optional[int] = ..., current_exp: _Optional[int] = ..., total_exp: _Optional[int] = ..., created_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., updated_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., oauth_providers: _Optional[_Iterable[str]] = ...) -> None: ...

class ListUsersRequest(_message.Message):
    __slots__ = ("page", "page_size", "search", "is_active", "is_superuser")
    PAGE_FIELD_NUMBER: _ClassVar[int]
    PAGE_SIZE_FIELD_NUMBER: _ClassVar[int]
    SEARCH_FIELD_NUMBER: _ClassVar[int]
    IS_ACTIVE_FIELD_NUMBER: _ClassVar[int]
    IS_SUPERUSER_FIELD_NUMBER: _ClassVar[int]
    page: int
    page_size: int
    search: str
    is_active: bool
    is_superuser: bool
    def __init__(self, page: _Optional[int] = ..., page_size: _Optional[int] = ..., search: _Optional[str] = ..., is_active: bool = ..., is_superuser: bool = ...) -> None: ...

class ListUsersResponse(_message.Message):
    __slots__ = ("items", "total")
    ITEMS_FIELD_NUMBER: _ClassVar[int]
    TOTAL_FIELD_NUMBER: _ClassVar[int]
    items: _containers.RepeatedCompositeFieldContainer[User]
    total: int
    def __init__(self, items: _Optional[_Iterable[_Union[User, _Mapping]]] = ..., total: _Optional[int] = ...) -> None: ...

class GetUserRequest(_message.Message):
    __slots__ = ("id",)
    ID_FIELD_NUMBER: _ClassVar[int]
    id: int
    def __init__(self, id: _Optional[int] = ...) -> None: ...

class Ban(_message.Message):
    __slots__ = ("id", "user_id", "reason", "reason_text", "banned_at", "banned_until", "is_permanent", "moderator_id")
    ID_FIELD_NUMBER: _ClassVar[int]
    USER_ID_FIELD_NUMBER: _ClassVar[int]
    REASON_FIELD_NUMBER: _ClassVar[int]
    REASON_TEXT_FIELD_NUMBER: _ClassVar[int]
    BANNED_AT_FIELD_NUMBER: _ClassVar[int]
    BANNED_UNTIL_FIELD_NUMBER: _ClassVar[int]
    IS_PERMANENT_FIELD_NUMBER: _ClassVar[int]
    MODERATOR_ID_FIELD_NUMBER: _ClassVar[int]
    id: int
    user_id: int
    reason: str
    reason_text: str
    banned_at: _timestamp_pb2.Timestamp
    banned_until: _timestamp_pb2.Timestamp
    is_permanent: bool
    moderator_id: int
    def __init__(self, id: _Optional[int] = ..., user_id: _Optional[int] = ..., reason: _Optional[str] = ..., reason_text: _Optional[str] = ..., banned_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., banned_until: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., is_permanent: bool = ..., moderator_id: _Optional[int] = ...) -> None: ...

class GetActiveBansRequest(_message.Message):
    __slots__ = ("user_ids",)
    USER_IDS_FIELD_NUMBER: _ClassVar[int]
    user_ids: _containers.RepeatedScalarFieldContainer[int]
    def __init__(self, user_ids: _Optional[_Iterable[int]] = ...) -> None: ...

class GetActiveBansResponse(_message.Message):
    __slots__ = ("bans",)
    BANS_FIELD_NUMBER: _ClassVar[int]
    bans: _containers.RepeatedCompositeFieldContainer[Ban]
    def __init__(self, bans: _Optional[_Iterable[_Union[Ban, _Mapping]]] = ...) -> None: ...

class ListSessionsRequest(_message.Message):
    __slots__ = ("user_id",)
    USER_ID_FIELD_NUMBER: _ClassVar[int]
    user_id: int
    def __init__(self, user_id: _Optional[int] = ...) -> None: ...

class Session(_message.Message):
    __slots__ = ("session_id", "device_name", "user_agent", "ip_address", "created_at", "last_used_at", "expires_at")
    SESSION_ID_FIELD_NUMBER: _ClassVar[int]
    DEVICE_NAME_FIELD_NUMBER: _ClassVar[int]
    USER_AGENT_FIELD_NUMBER: _ClassVar[int]
    IP_ADDRESS_FIELD_NUMBER: _ClassVar[int]
    CREATED_AT_FIELD_NUMBER: _ClassVar[int]
    LAST_USED_AT_FIELD_NUMBER: _ClassVar[int]
    EXPIRES_AT_FIELD_NUMBER: _ClassVar[int]
    session_id: str
    device_name: str
    user_agent: str
    ip_address: str
    created_at: _timestamp_pb2.Timestamp
    last_used_at: _timestamp_pb2.Timestamp
    expires_at: _timestamp_pb2.Timestamp
    def __init__(self, session_id: _Optional[str] = ..., device_name: _Optional[str] = ..., user_agent: _Optional[str] = ..., ip_address: _Optional[str] = ..., created_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., last_used_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., expires_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class ListSessionsResponse(_message.Message):
    __slots__ = ("sessions",)
    SESSIONS_FIELD_NUMBER: _ClassVar[int]
    sessions: _containers.RepeatedCompositeFieldContainer[Session]
    def __init__(self, sessions: _Optional[_Iterable[_Union[Session, _Mapping]]] = ...) -> None: ...
