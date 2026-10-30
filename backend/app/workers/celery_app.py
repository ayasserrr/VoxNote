"""Celery application (used when TASK_BACKEND=celery).

Run a worker with:
    celery -A app.workers.celery_app worker --loglevel=info --concurrency=2
"""

from __future__ import annotations

from celery import Celery

from app.config import settings
from app.logging_setup import setup_logging

setup_logging()

celery = Celery("voxnote", broker=settings.redis_url, backend=settings.redis_url)
celery.conf.update(
    task_acks_late=True,  # a crashed worker's job is redelivered
    worker_prefetch_multiplier=1,  # long jobs: don't hoard tasks
    task_reject_on_worker_lost=True,
    task_default_queue="voxnote",
    broker_connection_retry_on_startup=True,
    timezone="UTC",
)


@celery.task(name="voxnote.process_video")
def process_video_task(video_id: str) -> None:
    from app.pipeline.orchestrator import process_video

    process_video(video_id)


@celery.task(name="voxnote.synthesize_collection")
def synthesize_collection_task(collection_id: str) -> None:
    from app.pipeline.orchestrator import synthesize_collection

    synthesize_collection(collection_id)


# Ensure tables exist when a worker starts before the API.
@celery.on_after_configure.connect
def _init(sender, **kwargs):  # pragma: no cover
    from app.db import init_db

    if settings.db_auto_create:
        init_db()
