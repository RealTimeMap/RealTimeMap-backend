from typing import Annotated

from fastapi import APIRouter, Depends, Form, Request
from fastapi_pagination import Page, Params
from fastapi_pagination.ext.sqlalchemy import apaginate
from sqlalchemy.ext.asyncio import AsyncSession

from core.common.repository.category import CategoryRepository
from database import get_session
from modules.category import get_pg_category_repository
from modules.category.schemas import ReadCategory, CreateCategory
from utils.cache.decorator import custom_cache

router = APIRouter(prefix="/category", tags=["Category"])


@router.get("/", response_model=Page[ReadCategory])
@custom_cache(expire=3600, namespace="category")
async def get_all_sql(
    repo: Annotated["CategoryRepository", Depends(get_pg_category_repository)],
    session: Annotated["AsyncSession", Depends(get_session)],
    _: Request,
    params: Params = Depends(),  # noqa Need for cache builder
):
    result = await apaginate(session, repo.get_select_all())
    return result


@router.post("/", response_model=ReadCategory)
async def create_category(
    category_data: Annotated[CreateCategory, Form(media_type="multipart/form-data")],
    repo: Annotated["CategoryRepository", Depends(get_pg_category_repository)],
):
    result = await repo.create(category_data)
    return result
