"""Celery tasks module."""

from celery import Celery

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "phosphor",
    broker=str(settings.redis_url),
    backend=str(settings.redis_url),
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=300,  # 5 minutes max
    task_soft_time_limit=240,  # 4 minutes soft limit
    worker_prefetch_multiplier=1,  # Process one task at a time
)

# Import tasks to register them
from app.tasks import distill  # noqa: F401, E402
