import hashlib
import logging
from typing import Callable, Any, Tuple, Dict

from fastapi import Request, Response

logger = logging.getLogger(__name__)


def custom_key_builder(
    func: Callable[..., Any],
    namespace: str = "",
    *,
    request: Request,
    response: Response,
    args: Tuple[Any, ...],
    kwargs: Dict[str, Any],
) -> str:
    path_key = f"{request.method.lower()}:{request.url.path}"

    # Добавляем query параметры
    if request.query_params:
        query_string = "&".join(
            f"{k}={v}" for k, v in sorted(request.query_params.items())
        )
        path_key += f"?{query_string}"

    # Хэшируем для краткости
    key_hash = hashlib.md5(path_key.encode()).hexdigest()[:12]

    return f"{namespace}:{request.method.lower()}:{request.url.path.replace('/', ':')}:{key_hash}"
