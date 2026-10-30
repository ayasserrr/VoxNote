"""Documentation pipeline: crawl → store pages → build the learning course."""

from __future__ import annotations

import logging
import time
from urllib.parse import urlparse

from sqlalchemy import update

from app.config import settings
from app.db import session_scope
from app.metrics import STAGE_SECONDS
from app.models import Collection, Course, DocPage, ProcessingLog, Stage, Status
from app.services.crawler import Crawler, CrawlError
from app.services.language import detect_language

log = logging.getLogger(__name__)

# Tests inject a fake HTTP client here.
http_client_factory = None


def _log(collection_id: str, message: str, level: str = "info", stage: str | None = None) -> None:
    getattr(log, "warning" if level == "warning" else "error" if level == "error" else "info")(
        "[%s] %s", collection_id, message)
    with session_scope() as db:
        db.add(ProcessingLog(collection_id=collection_id, level=level, stage=stage, message=message[:4000]))


def process_docs(collection_id: str) -> None:
    with session_scope() as db:
        col = db.get(Collection, collection_id)
        if col is None or col.status == Status.cancelled.value:
            return
        cfg = dict(col.settings or {})
        url = col.source_url
        col.status = Status.processing.value
        col.stage = Stage.crawling.value
        col.progress = 0.02
        col.error = None

    def progress(done: int, total: int, page_url: str) -> None:
        with session_scope() as db:
            db.execute(update(Collection).where(Collection.id == collection_id).values(
                progress=round(min(0.05 + 0.85 * done / max(total, 1), 0.9), 3),
                meta={"pages_found": done, "current_url": page_url}))

    t0 = time.monotonic()
    try:
        crawler = Crawler(
            url,
            max_pages=min(int(cfg.get("max_pages", 40)), settings.crawl_max_pages),
            same_path_only=bool(cfg.get("same_path_only", True)),
            delay=settings.crawl_delay,
            client=http_client_factory() if http_client_factory else None,
            progress=progress,
        )
        result = crawler.crawl()
    except CrawlError as exc:
        _log(collection_id, f"crawl failed: {exc}", "error", "crawling")
        with session_scope() as db:
            col = db.get(Collection, collection_id)
            col.status, col.stage, col.error, col.progress = Status.failed.value, Stage.done.value, str(exc), 1.0
        return
    except Exception as exc:  # noqa: BLE001
        log.exception("crawl crashed")
        with session_scope() as db:
            col = db.get(Collection, collection_id)
            col.status, col.stage, col.error = Status.failed.value, Stage.done.value, f"Crawl failed: {exc}"
        return
    STAGE_SECONDS.labels("crawling").observe(time.monotonic() - t0)

    words = sum(p.word_count for p in result.pages)
    with session_scope() as db:
        col = db.get(Collection, collection_id)
        for old in list(col.pages):
            db.delete(old)
        db.flush()
        for i, p in enumerate(result.pages):
            db.add(DocPage(collection_id=col.id, position=i, url=p.url, title=p.title[:500], headings=p.headings,
                           content=p.content, word_count=p.word_count,
                           language=detect_language(p.content[:3000])))
        first = result.pages[0]
        host = urlparse(col.source_url or "").netloc
        if not col.title or col.title in {host, "Documentation"}:
            col.title = (f"{first.title} ({host})" if host and host not in first.title else first.title)[:500]
        col.stage = Stage.structuring.value
        col.progress = 0.92
        col.meta = {"pages": len(result.pages), "words": words, "visited": result.visited,
                    "skipped": result.skipped, "warnings": result.warnings}
        course = col.course
        if course is None:
            course = Course(collection_id=col.id, user_id=col.user_id, title=col.title,
                            level=cfg.get("level", "beginner"), language=cfg.get("language", "auto"))
            db.add(course)
            db.flush()
        course.status = Status.processing.value
        course_id = course.id
    _log(collection_id, f"crawled {len(result.pages)} pages ({words:,} words) in {time.monotonic() - t0:.0f}s",
         stage="crawling")
    for w in result.warnings:
        _log(collection_id, w, "warning", "crawling")

    from app.services.learning import build_course

    t1 = time.monotonic()
    build_course(course_id)
    STAGE_SECONDS.labels("structuring").observe(time.monotonic() - t1)
    with session_scope() as db:
        col = db.get(Collection, collection_id)
        course = db.get(Course, course_id)
        ok = course is not None and course.status == Status.completed.value
        col.status = Status.completed.value if ok else Status.failed.value
        col.error = None if ok else (course.error if course else "Course creation failed")
        col.stage = Stage.done.value
        col.progress = 1.0
        n = len(course.lessons) if course else 0
    _log(collection_id, f"course ready with {n} lessons" if ok else "course creation failed",
         "info" if ok else "error", "structuring")
