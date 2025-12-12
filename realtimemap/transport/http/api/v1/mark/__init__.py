__all__ = ["router"]


from .view import router

from .comment_view import router as comment_router

router.include_router(comment_router)
