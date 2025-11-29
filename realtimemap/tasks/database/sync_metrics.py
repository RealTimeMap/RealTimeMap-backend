import logging
from contextlib import contextmanager
from datetime import datetime, timedelta

from sqlalchemy import select, func, and_
from sqlalchemy.dialects.postgresql import insert

from core.celery import app
from database import get_sync_session
from modules.mark.model import Mark
from modules.metrics.model import UserMetric
from modules.user.model import User

session_context = contextmanager(get_sync_session)

logger = logging.getLogger(__name__)


@app.task
def sync_user_metrics():
    """
    Массовое обновление метрик пользователей.
    Использует bulk операции для минимизации нагрузки на БД.

    Одним запросом получаем агрегированную статистику для всех пользователей,
    затем одним upsert обновляем все записи.
    """
    with session_context() as session:
        # 1. Получаем агрегированные данные по меткам для всех активных пользователей
        marks_stats_stmt = (
            select(
                Mark.owner_id.label("user_id"),
                func.count(Mark.id).label("total_marks"),
                func.count(Mark.id)
                .filter(not Mark.is_ended)
                .label("active_marks"),
                func.count(Mark.id).filter(Mark.is_ended).label("ended_marks"),
            )
            .join(User, Mark.owner_id == User.id)
            .where(User.is_active)
            .group_by(Mark.owner_id)
        )

        marks_stats = session.execute(marks_stats_stmt).all()
        print(f"Get mark stat for users: {len(marks_stats)}")

        # 2. Получаем список всех активных пользователей
        all_users_stmt = select(User.id).where(User.is_active)
        all_user_ids = session.execute(all_users_stmt).scalars().all()
        logger.info(f"Total active users: {len(all_user_ids)}")

        # 3. Создаем словарь для быстрого доступа к статистике
        marks_dict = {row.user_id: row for row in marks_stats}

        # 4. Формируем данные для bulk upsert
        metrics_data = []
        for user_id in all_user_ids:
            marks_data = marks_dict.get(user_id)

            metrics_data.append(
                {
                    "user_id": user_id,
                    "total_marks": marks_data.total_marks if marks_data else 0,
                    "active_marks": marks_data.active_marks if marks_data else 0,
                    "ended_marks": marks_data.ended_marks if marks_data else 0,
                    "updated_at": datetime.now(),
                }
            )

        # 5. Выполняем bulk upsert
        if metrics_data:
            stmt = insert(UserMetric).values(metrics_data)
            stmt = stmt.on_conflict_do_update(
                index_elements=["user_id"],
                set_={
                    "total_marks": stmt.excluded.total_marks,
                    "active_marks": stmt.excluded.active_marks,
                    "ended_marks": stmt.excluded.ended_marks,
                    "updated_at": stmt.excluded.updated_at,
                },
            )

            session.execute(stmt)
            session.flush()
            logger.info(f"End updating metrics: {len(metrics_data)} users")
        else:
            logger.info("No such info")

        logger.info("End task: sync_user_metrics")


@app.task
def sync_active_user_metrics():
    """
    Обновление метрик только для пользователей с активностью за последние 24 часа.
    Запускается чаще, чем полная синхронизация для поддержания актуальности данных.

    Использует батч-обработку для эффективного обновления больших объемов данных.
    """
    with session_context() as session:
        # Определяем временной порог (последние 24 часа)
        threshold = datetime.now() - timedelta(hours=24)

        # Получаем пользователей, создавших метки за последние 24ч
        active_users_stmt = (
            select(User.id)
            .distinct()
            .join(Mark, Mark.owner_id == User.id)
            .where(and_(User.is_active, Mark.created_at >= threshold))
        )

        active_user_ids = session.execute(active_users_stmt).scalars().all()

        if not active_user_ids:
            logger.info("Active users not found")
            return

        # Обрабатываем пользователей батчами для контроля памяти
        batch_size = 100
        total_updated = 0

        for i in range(0, len(active_user_ids), batch_size):
            batch_ids = active_user_ids[i : i + batch_size]

            # Получаем статистику для текущего батча
            marks_stats_stmt = (
                select(
                    Mark.owner_id.label("user_id"),
                    func.count(Mark.id).label("total_marks"),
                    func.count(Mark.id)
                    .filter(not Mark.is_ended)
                    .label("active_marks"),
                    func.count(Mark.id)
                    .filter(Mark.is_ended)
                    .label("ended_marks"),
                )
                .where(Mark.owner_id.in_(batch_ids))
                .group_by(Mark.owner_id)
            )

            marks_stats = session.execute(marks_stats_stmt).all()
            marks_dict = {row.user_id: row for row in marks_stats}

            # Формируем данные для upsert
            metrics_data = []
            for user_id in batch_ids:
                marks_data = marks_dict.get(user_id)
                metrics_data.append(
                    {
                        "user_id": user_id,
                        "total_marks": marks_data.total_marks if marks_data else 0,
                        "active_marks": marks_data.active_marks if marks_data else 0,
                        "ended_marks": marks_data.ended_marks if marks_data else 0,
                        "updated_at": datetime.now(),
                    }
                )

            # Bulk upsert для батча
            if metrics_data:
                stmt = insert(UserMetric).values(metrics_data)
                stmt = stmt.on_conflict_do_update(
                    index_elements=["user_id"],
                    set_={
                        "total_marks": stmt.excluded.total_marks,
                        "active_marks": stmt.excluded.active_marks,
                        "ended_marks": stmt.excluded.ended_marks,
                        "updated_at": stmt.excluded.updated_at,
                    },
                )
                session.execute(stmt)
                session.flush()
                total_updated += len(metrics_data)

        logger.info("Sync metrics  ")
