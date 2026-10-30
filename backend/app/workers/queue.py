"""Job queue abstraction.

* TASK_BACKEND=thread (default): an in-process thread pool. Zero setup -
  perfect for local/personal use. Unfinished jobs are recovered on startup.
* TASK_BACKEND=celery: Celery workers + Redis broker (docker-compose). Jobs
  survive API restarts and scale horizontally across worker containers.

One job per video, plus one synthesis job per playlist.
"""

from __future__ import annotations

import logging
import threading
from concurrent.futures import ThreadPoolExecutor

from sqlalchemy import select

from app.config import settings
from app.db import session_scope
from app.models import Collection, Course, Stage, Status, Video

log = logging.getLogger(__name__)

_executor: ThreadPoolExecutor | None = None
_executor_lock = threading.Lock()


def _pool() -> ThreadPoolExecutor:
    global _executor
    with _executor_lock:
        if _executor is None:
            _executor = ThreadPoolExecutor(max_workers=max(settings.worker_concurrency, 1),
                                           thread_name_prefix="voxnote-worker")
        return _executor


def _safe(fn, *args):
    try:
        fn(*args)
    except Exception:  # pragma: no cover - logged, never crash the pool
        log.exception("background job %s%s crashed", fn.__name__, args)


def _submit(fn, arg: str, delay: float = 0.0) -> None:
    if delay > 0:
        t = threading.Timer(delay, lambda: _pool().submit(_safe, fn, arg))
        t.daemon = True
        t.start()
    else:
        _pool().submit(_safe, fn, arg)


def enqueue_video(video_id: str, delay: float = 0.0) -> None:
    if settings.task_backend == "celery":
        from app.workers.celery_app import process_video_task

        process_video_task.apply_async(args=[video_id], countdown=int(delay))
        return
    from app.pipeline.orchestrator import process_video

    _submit(process_video, video_id, delay)


def enqueue_synthesis(collection_id: str) -> None:
    if settings.task_backend == "celery":
        from app.workers.celery_app import synthesize_collection_task

        synthesize_collection_task.apply_async(args=[collection_id])
        return
    from app.pipeline.orchestrator import synthesize_collection

    _submit(synthesize_collection, collection_id)


def enqueue_docs(collection_id: str) -> None:
    if settings.task_backend == "celery":
        from app.workers.celery_app import process_docs_task

        process_docs_task.apply_async(args=[collection_id])
        return
    from app.pipeline.docs import process_docs

    _submit(process_docs, collection_id)


def enqueue_course(course_id: str) -> None:
    if settings.task_backend == "celery":
        from app.workers.celery_app import build_course_task

        build_course_task.apply_async(args=[course_id])
        return
    from app.services.learning import build_course

    _submit(build_course, course_id)


def enqueue_lesson(lesson_id: str) -> None:
    """Pre-generate a lesson in the background (best effort)."""
    if not settings.prefetch_next_lesson:
        return
    if settings.task_backend == "celery":
        from app.workers.celery_app import generate_lesson_task

        generate_lesson_task.apply_async(args=[lesson_id])
        return
    from app.services.learning import prefetch_lesson

    _submit(prefetch_lesson, lesson_id)


def recover_pending() -> int:
    """Re-enqueue work interrupted by a restart (thread backend only)."""
    if settings.task_backend != "thread":
        return 0
    with session_scope() as db:
        videos = db.scalars(
            select(Video).where(Video.status.in_([Status.pending.value, Status.queued.value,
                                                  Status.processing.value]))
        ).all()
        ids = [v.id for v in videos]
        for v in videos:
            v.status = Status.queued.value
        stuck = db.scalars(select(Collection).where(Collection.stage.in_(
            [Stage.synthesizing.value, Stage.rendering.value]))).all()
        stuck_ids = [c.id for c in stuck if c.kind != "docs" and all(
            v.status in (Status.completed.value, Status.failed.value) for v in c.videos)]
        docs_ids = [c.id for c in db.scalars(select(Collection).where(
            Collection.kind == "docs",
            Collection.status.in_([Status.queued.value, Status.processing.value]))).all()]
        course_ids = [c.id for c in db.scalars(select(Course).where(
            Course.status.in_([Status.queued.value, Status.processing.value]))).all()
            if c.collection_id not in docs_ids]  # the docs pipeline builds its own course
    for vid in ids:
        enqueue_video(vid)
    for cid in stuck_ids:
        enqueue_synthesis(cid)
    for cid in docs_ids:
        enqueue_docs(cid)
    for cid in course_ids:
        enqueue_course(cid)
    if ids or stuck_ids or docs_ids or course_ids:
        log.info("recovered %d video, %d synthesis, %d docs and %d course job(s)",
                 len(ids), len(stuck_ids), len(docs_ids), len(course_ids))
    return len(ids)


def shutdown() -> None:
    global _executor
    if _executor is not None:
        _executor.shutdown(wait=False, cancel_futures=True)
        _executor = None
