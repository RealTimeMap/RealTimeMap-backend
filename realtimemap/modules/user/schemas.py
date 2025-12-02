from enum import Enum
from typing import Optional, List, Annotated

from fastapi import UploadFile
from fastapi_users import schemas
from pydantic import BaseModel, field_validator, Field, ConfigDict, computed_field

from modules.gamefication.schemas.level.crud import LevelRead
from modules.user_ban.schemas import ReadUsersBan
from modules.user_subscription.schemas import ReadUserSubscription
from utils.url_generator import generate_full_image_url


class UserGamefication(BaseModel):
    current_level: Annotated[int, Field(..., description="Current user level")]
    current_exp: Annotated[int, Field(..., description="Current user exp level")]
    current_level_color: Annotated[
        Optional[str], Field(None, description="Current level color")
    ]
    next_level: Annotated[
        Optional[LevelRead], Field(None, description="Next level for")
    ]

    @computed_field
    def exp_for_level_up(self) -> Optional[int]:
        if self.next_level is None:
            return None
        return self.next_level.required_exp - self.current_exp


class UserRelationShip(str, Enum):
    SUBSCRIPTION = "subscription"
    BAN = "ban"
    GAMEFICATION = "gamefication"


class UserRequestParams(BaseModel):
    include: Annotated[
        Optional[List[UserRelationShip]],
        Field(None, description="Attach the relevant data to the response"),
    ]


class UserRead(schemas.BaseUser[int]):
    id: int
    phone: Optional[str] = None
    username: str
    avatar: Optional[str] = None
    _validate_avatar = field_validator("avatar", mode="before")(generate_full_image_url)

    model_config = ConfigDict(from_attributes=True)


class DetailUserRead(UserRead):
    subscription: Optional["ReadUserSubscription"] = None
    ban: Optional["ReadUsersBan"] = None
    gamefication: Optional[UserGamefication] = None


class UserCreate(schemas.BaseUserCreate):
    username: Annotated[str, Field(..., description="Username")]

    @field_validator("password")
    def validate_password(cls, value: str):
        if len(value) < 6:
            raise ValueError("Password must be at least 6 characters")
        return value


class UserUpdate(schemas.BaseUserUpdate):
    @field_validator("password")
    def validate_password(cls, password: str):
        if len(password) < 8:
            raise ValueError("Password must be at least 8 characters long")
        return password

    username: Optional[str] = None
    avatar: Optional[UploadFile] = None


class UserGameFicationUpdate(UserUpdate):
    total_exp: Optional[int] = None
    curent_exp: Optional[int] = None


class UserLogin(BaseModel):
    username: str
    password: str
