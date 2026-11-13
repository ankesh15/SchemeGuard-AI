from typing import Any

from celery import Celery  # type: ignore[import-untyped]
from celery.signals import setup_logging  # type: ignore[import-untyped]
from kombu.entity import Queue

from app.core.config import get_settings
from app.core.logging import configure_logging

settings = get_settings()
celery_app = Celery(
    "schemeguard",
    broker=settings.redis_url,
    include=["app.workers.monitoring_tasks", "app.workers.document_tasks", "app.workers.comparison_tasks"],
)
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    task_ignore_result=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    worker_concurrency=2,
    worker_max_tasks_per_child=50,
    worker_cancel_long_running_tasks_on_connection_loss=True,
    task_soft_time_limit=420,
    task_time_limit=480,
    broker_connection_retry_on_startup=True,
    broker_transport_options={"visibility_timeout": 900, "socket_timeout": 5, "socket_connect_timeout": 5},
    broker_connection_max_retries=10,
    task_publish_retry_policy={"max_retries": 2, "interval_start": 0, "interval_step": 1, "interval_max": 2},
    task_queues=(Queue("monitoring", routing_key="monitoring"), Queue("documents", routing_key="documents")),  # type: ignore[no-untyped-call]
    task_default_queue="monitoring",
    beat_schedule={
        "dispatch-durable-monitoring": {
            "task": "schemeguard.dispatch",
            "schedule": settings.monitoring_dispatch_seconds,
        }
    },
    timezone="UTC",
    enable_utc=True,
    worker_hijack_root_logger=False,
)


@setup_logging.connect  # type: ignore[untyped-decorator]
def configure_worker_logs(**kwargs: Any) -> None:
    configure_logging(settings.log_level)
