from celery import Celery
from celery.schedules import crontab

from core.config import conf

app = Celery(
    "core.celery.celery_app",
    broker=conf.celery.broker,
    backend=conf.celery.backend,
    include=["tasks"],
)

# Redis connection resilience settings
app.conf.update(
    # Broker settings for better Redis connection handling
    broker_connection_retry=True,
    broker_connection_retry_on_startup=True,
    broker_connection_max_retries=10,
    broker_pool_limit=50,

    # Transport options for Redis
    broker_transport_options={
        'visibility_timeout': 3600,
        'max_connections': 50,
        'health_check_interval': 30,
        'retry_on_timeout': True,
        'socket_connect_timeout': 5,
        'socket_timeout': 5,
    },

    # Result backend settings
    result_backend_transport_options={
        'retry_on_timeout': True,
        'max_connections': 50,
        'health_check_interval': 30,
        'socket_timeout': 5,
    },

    # Task execution settings
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,

    # Retry policy
    task_default_retry_delay=30,
    task_max_retries=3,
)

app.conf.beat_schedule = {
    # Переодическая задача для проверки меток
    "end_check": {
        "task": "tasks.database.check_ended.check_mark_ended",
        "schedule": crontab(minute=30),
    },
    # Полная синхронизация пользователей и их статистики
    "sync_all_metrics": {
        "task": "tasks.database.sync_metrics.sync_user_metrics",
        "schedule": crontab(hour=12),
    },
    # Синхронизация только активных пользователей за 24 часа
    "sync_active_metrics": {
        "task": "tasks.database.sync_metrics.sync_active_user_metrics",
        "schedule": crontab(minute=15),
    },
}
