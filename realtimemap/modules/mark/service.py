import logging
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

from fastapi import HTTPException
from sqlalchemy.orm import joinedload

from errors.http2 import (
    NotFoundError,
    TimeOutError,
    UserPermissionError,
    ValidationError,
)
from modules.geo_service import GeoService
from modules.user.model import User
from .filters import MarkFilter
from .model import Mark
from .schemas import (
    CreateMarkRequest,
    MarkRequestParams,
    UpdateMarkRequest,
    CreateMark,
    UpdateMark,
    MarkCreateDataResponse,
    allowed_duration,
)

if TYPE_CHECKING:
    from core.common.repository import (
        MarkRepository,
        CategoryRepository,
        MarkCommentRepository,
    )
logger = logging.getLogger(__name__)


class MarkService:
    __slots__ = (
        "mark_repo",
        "category_repo",
        "mark_comment_repo",
        "geo_service",
    )

    def __init__(
        self,
        mark_repo: "MarkRepository",
        category_repo: "CategoryRepository",
        mark_comment_repo: "MarkCommentRepository",
        geo_service: "GeoService",
    ):
        self.mark_repo = mark_repo
        self.category_repo = category_repo
        self.mark_comment_repo = mark_comment_repo
        self.geo_service = geo_service

    async def create_mark(self, mark_data: CreateMarkRequest, user: User) -> Mark:
        category_exist = await self.category_repo.exist(mark_data.category_id)
        if not category_exist:
            raise NotFoundError()
        create_data = self._validate_create_data(mark_data, user)
        mark = await self.mark_repo.create_mark(create_data)
        return mark

    async def get_mark_by_id(self, mark_id: int) -> Mark:
        result = await self.mark_repo.get_by_id(
            mark_id, join_related=["owner", "category"], load_strategy=joinedload
        )
        if not result:
            raise NotFoundError()
        return result

    async def get_marks(self, params: MarkRequestParams):
        filters = MarkFilter.from_request(params, self.geo_service)
        result = await self.mark_repo.get_marks(filters)
        return result

    async def delete_mark(self, mark_id: int, user: User):
        mark = await self.mark_repo.get_by_id(mark_id)
        await self._check_mark_ownership(mark, user)
        result = await self.mark_repo.delete_mark(mark.id)  # noqa: ignore
        return result

    async def get_data_for_create_mark(self):
        """
        Метод возвращает данные необходимые для создания метки

        Returns:

        """
        categories = await self.category_repo.get_active_categories()

        response = MarkCreateDataResponse(
            categories=categories, allowed_duration=allowed_duration
        )

        return response

    def _validate_create_data(
        self, data: CreateMarkRequest, user: "User"
    ) -> CreateMark:
        geom = None
        if data.longitude and data.latitude:
            geom = self.geo_service.create_geometry_point(data)
        return CreateMark(
            **data.model_dump(exclude={"latitude", "longitude"}),
            owner_id=user.id,
            geom=geom,
            geohash=(
                self.geo_service.get_geohash(data)
                if data.longitude and data.latitude
                else None
            ),
        )

    async def update_mark(
        self, mark_id: int, update_data: UpdateMarkRequest, user: User
    ) -> Mark:
        """
        Метод сервиса для обновления метки
        :param mark_id: id метки
        :param update_data: Данные для обновления
        :param user: Пользователь кто меняет данные
        :return: объект Mark
        :raises NotFoundError: если запись не найдена
        :raises TimeOutError: Если время изменения истекло
        :raises UserPermissionError: Если текущий пользователь не владелец записи
        """
        try:
            mark = await self.mark_repo.get_by_id(
                mark_id, join_related=["category"], load_strategy=joinedload
            )
            if not mark:
                raise NotFoundError()

            if mark.check_ended:
                raise TimeOutError()

            await self._before_update_mark(mark, user, update_data)
            valid_data = self._validate_update_data(update_data)
            return await self.mark_repo.update_mark(mark_id, valid_data)
        except NotFoundError:
            logger.info("Record not found: %d", mark_id)
            raise
        except TimeOutError:
            logger.info("Update time out: %d", mark_id)
            raise
        except UserPermissionError:
            logger.info("User permission error: %d %d", mark_id, user.id)
            raise
        except ValidationError:
            logger.info("Category does not exist: %d", update_data.category_id)
            raise
        except ValueError:
            logger.error("Update data error: %d %v", mark_id, update_data)
            raise HTTPException(status_code=400, detail="Update data error")

    def _validate_update_data(self, update_data: UpdateMarkRequest) -> UpdateMark:
        """
        метод для преоброзования сырых данных в валидные для обновления метки.
        Метод автоматически сформирует геометрию и ее geohash, на основе новых координат
        :param update_data: Сырые данные
        :return: UpdateMark
        """
        try:
            geom = None
            geohash = None
            if update_data.longitude is not None and update_data.latitude is not None:
                coords = self.geo_service.create_coordinates(update_data)
                geom = self.geo_service.create_geometry_point(coords)
                geohash = self.geo_service.get_geohash(coords)

            valid_data = UpdateMark(
                **update_data.model_dump(exclude={"latitude", "longitude"}),
                geom=geom,
                geohash=geohash,
            )
            return valid_data
        except ValueError:
            logger.info("Update data in not valid: %s", update_data)
            raise

    async def _before_update_mark(
        self, mark: Mark, user: User, update_data: UpdateMarkRequest
    ) -> None:
        """
        Метод вызывается перед тем как обновить данные
        :param mark: Объект метки из БД
        :param user: Текущий пользователь
        :param update_data: Сырые данные для обновления
        :return: None
        """
        await self._check_category_exist(update_data)
        await self._check_mark_ownership(mark, user)
        self._check_timeout(mark, 2)

    @staticmethod
    async def _check_mark_ownership(mark: Mark, user: User) -> None:
        """
        Проверяет являться ли пользователь автором данной метки
        :param mark: Метка для проверки
        :param user: Текщий пользователь
        :return: None
        """
        if mark.owner_id != user.id:
            raise UserPermissionError()

    async def _check_category_exist(self, update_data: UpdateMarkRequest) -> None:
        """
        Метод проверяет, существует ли указанная категория
        :param update_data: Сырые данные
        :return: None
        :raises NotFoundError: Если указанная категория не найдена
        """
        if not update_data.category_id:
            return

        category_exist = await self.category_repo.exist(update_data.category_id)
        if not category_exist:
            raise ValidationError(
                field="category_id",
                user_input=update_data.category_id,
                input_type="number",
                detail="Category does not exist",
            )

    @staticmethod
    def _check_timeout(mark: Mark, duration: int = 1) -> None:
        """
        Метод для проверки на время редактирования записи
        :param mark: Метка
        :param duration: Длительность в часах, в течении которых можно редактировать запись
        :return: None
        :raises TimeOutError: Если время редактирования вышло
        """
        passed_time = datetime.now(timezone.utc) - mark.created_at
        if passed_time > timedelta(hours=duration):
            raise TimeOutError()
