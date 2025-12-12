import logging
import os
import sys

from fastapi import FastAPI
from fastapi.responses import ORJSONResponse
from fastapi_pagination import add_pagination
from libcloud.storage.drivers.local import LocalStorageDriver
from sqlalchemy_file.storage import StorageManager
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.staticfiles import StaticFiles

from admin import setup_admin
from core.config import conf
from middleware import ProcessTimeMiddleware
from transport.http.api.v1 import router as v1_router
from .exception_handler import register_exception_handler
from .lifespan import lifespan
from .socket import sio_app

logger = logging.getLogger(__name__)

LOG_DIR = conf.root_dir / "logs"


# Интеграция и настройка пагинации
def setup_pagination(app: FastAPI) -> None:
    add_pagination(app)


# Функция для настрйоки логов
def setup_logging() -> None:
    os.makedirs(LOG_DIR, exist_ok=True)
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)

    formatter = logging.Formatter(fmt=conf.log.log_format, datefmt=conf.log.date_format)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(conf.log.log_level)
    console_handler.setFormatter(formatter)

    error_file_handler = logging.FileHandler(
        str(LOG_DIR / conf.log.error_log_filename), mode="a", encoding="utf-8"
    )
    error_file_handler.setLevel(logging.ERROR)
    error_file_handler.setFormatter(formatter)

    if root_logger.hasHandlers():
        root_logger.handlers.clear()

    root_logger.addHandler(console_handler)
    root_logger.addHandler(error_file_handler)


# Настройки Хэдеров
def add_header_middleware(app: FastAPI) -> None:
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=[conf.server.domains])


# Добавление роутеров для эндпоинтов
def add_routers(app: FastAPI):
    app.include_router(v1_router)


# Интеграция Socket.io
def mount_socket_io(app: FastAPI) -> None:
    app.mount("/socket.io", app=sio_app)


# Настройка структуры для хранения медиа файлов пользователей (Можно интегрировать удаленное хранилище. См доку по sqlalchemy-file)
def setup_file_storage():
    os.makedirs("static", exist_ok=True)
    os.makedirs("uploads/default", exist_ok=True)
    os.makedirs("uploads/marks", exist_ok=True)
    os.makedirs("uploads/users", exist_ok=True)
    os.makedirs("uploads/category", exist_ok=True)

    default_container = LocalStorageDriver("uploads").get_container("default")
    category_container = LocalStorageDriver("uploads").get_container("category")
    mark_container = LocalStorageDriver("uploads").get_container("marks")
    users_container = LocalStorageDriver("uploads").get_container("users")

    StorageManager.add_storage("default", default_container)
    StorageManager.add_storage("category", category_container)
    StorageManager.add_storage("marks", mark_container)
    StorageManager.add_storage("users", users_container)


# Создание настроенного класса приложения
def create_app() -> FastAPI:
    setup_file_storage()
    setup_logging()
    app = FastAPI(lifespan=lifespan, default_response_class=ORJSONResponse)
    app.mount(
        "/static", StaticFiles(directory=conf.root_dir / conf.static), name="static"
    )

    add_header_middleware(app)
    add_routers(app)
    mount_socket_io(app)
    setup_pagination(app)
    setup_admin(app)
    app.add_middleware(ProcessTimeMiddleware)
    register_exception_handler(app)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    return app
