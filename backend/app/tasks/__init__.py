"""Celery tasks module."""

from celery import Celery
from celery.schedules import crontab

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
    task_time_limit=600,  # 10 minutes max (literature scans can be slow)
    task_soft_time_limit=540,  # 9 minutes soft limit
    worker_prefetch_multiplier=1,  # Process one task at a time
    beat_schedule={
        "daily-literature-scan": {
            "task": "app.tasks.literature.scheduled_literature_scan",
            "schedule": crontab(hour=2, minute=0),  # 2 AM UTC daily
        },
    },
)

# Import tasks to register them
from app.tasks import (
    agents,  # noqa: F401, E402
    distill,  # noqa: F401, E402
    literature,  # noqa: F401, E402
)
