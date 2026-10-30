"""Collections = processing requests (YouTube video, playlist, or upload)."""

from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.config import settings
from app.db import get_db
from app.deps import get_current_user, get_owned_collection
from app.models import Collection, CollectionKind, DocPage, ProcessingLog, Stage, Status, User, Video
from app.pipeline.orchestrator import recompute_collection_status
from app.schemas.api import (
    CollectionCreate,
    CollectionOut,
    CollectionSummary,
    LogOut,
    PageDetailOut,
    ProcessingSettings,
    UrlPreviewIn,
    UrlPreviewOut,
)
from app.schemas.learning import DocsCreate
from app.services.crawler import normalize_url
from app.services.storage import get_storage
from app.services.youtube import (
    YouTubeError,
    fetch_playlist_metadata,
    fetch_video_metadata,
    parse_youtube_url,
    video_url,
)
from app.workers.queue import enqueue_docs, enqueue_video

router = APIRouter(prefix="/collections", tags=["collections"])

ALLOWED_MEDIA = {".mp3", ".wav", ".m4a", ".mp4", ".webm", ".ogg", ".opus", ".flac", ".mkv", ".mov", ".aac"}


def summary_fields(col: Collection) -> dict:
    videos = col.videos
    n = len(videos)
    done = sum(1 for v in videos if v.status == Status.completed.value)
    failed = sum(1 for v in videos if v.status == Status.failed.value)
    if col.kind == CollectionKind.docs.value:
        progress = col.progress or 0.0
    else:
        progress = sum(v.progress if v.status != Status.failed.value else 1.0 for v in videos) / n if n else 0.0
    return {"video_count": n, "completed_count": done, "failed_count": failed, "progress": round(progress, 3),
            "page_count": len(col.pages), "course_id": col.course.id if col.course else None}


_summary = summary_fields


def _collection_out(col: Collection) -> CollectionOut:
    base = CollectionOut.model_validate(col, from_attributes=True)
    return base.model_copy(update=_summary(col))


@router.post("/preview", response_model=UrlPreviewOut)
async def preview(body: UrlPreviewIn, user: User = Depends(get_current_user)) -> UrlPreviewOut:
    try:
        parsed = parse_youtube_url(body.url)
        if parsed.kind == "playlist":
            meta = await run_in_threadpool(fetch_playlist_metadata, parsed.playlist_id, settings.max_playlist_videos)
            return UrlPreviewOut(kind="playlist", playlist_id=meta.playlist_id, title=meta.title,
                                 channel=meta.channel, thumbnail_url=meta.thumbnail_url,
                                 video_count=len(meta.videos),
                                 duration_seconds=sum(v.duration_seconds or 0 for v in meta.videos) or None)
        vm = await run_in_threadpool(fetch_video_metadata, parsed.video_id)
        return UrlPreviewOut(kind="video", video_id=vm.video_id, title=vm.title, channel=vm.channel,
                             thumbnail_url=vm.thumbnail_url, video_count=1, duration_seconds=vm.duration_seconds)
    except YouTubeError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc


@router.post("", response_model=CollectionOut, status_code=201)
async def create_collection(body: CollectionCreate, user: User = Depends(get_current_user),
                            db: Session = Depends(get_db)) -> CollectionOut:
    try:
        parsed = parse_youtube_url(body.url)
    except YouTubeError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc

    cs = body.settings.model_dump()
    if parsed.kind == "playlist":
        limit = min(body.settings.max_videos or settings.max_playlist_videos, settings.max_playlist_videos)
        try:
            meta = await run_in_threadpool(fetch_playlist_metadata, parsed.playlist_id, limit)
        except YouTubeError as exc:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
        col = Collection(user_id=user.id, kind=CollectionKind.playlist.value, source_url=body.url,
                         youtube_playlist_id=meta.playlist_id, title=meta.title, channel=meta.channel,
                         description=meta.description, thumbnail_url=meta.thumbnail_url,
                         status=Status.queued.value, settings=cs)
        for i, vm in enumerate(meta.videos):
            col.videos.append(Video(position=i, youtube_id=vm.video_id, url=video_url(vm.video_id),
                                    title=vm.title, channel=vm.channel, duration_seconds=vm.duration_seconds,
                                    thumbnail_url=vm.thumbnail_url, status=Status.queued.value))
    else:
        title, channel, thumb, duration, published, desc = (
            "YouTube video", None, f"https://i.ytimg.com/vi/{parsed.video_id}/hqdefault.jpg", None, None, None)
        try:
            vm = await run_in_threadpool(fetch_video_metadata, parsed.video_id)
            title, channel, thumb = vm.title, vm.channel, vm.thumbnail_url or thumb
            duration, published, desc = vm.duration_seconds, vm.published_at, vm.description
        except YouTubeError:
            pass  # metadata is retried inside the pipeline
        col = Collection(user_id=user.id, kind=CollectionKind.video.value, source_url=body.url, title=title,
                         channel=channel, thumbnail_url=thumb, status=Status.queued.value, settings=cs)
        col.videos.append(Video(position=0, youtube_id=parsed.video_id, url=video_url(parsed.video_id),
                                title=title, channel=channel, duration_seconds=duration, published_at=published,
                                description=desc, thumbnail_url=thumb, status=Status.queued.value))
    db.add(col)
    db.commit()
    for v in col.videos:
        enqueue_video(v.id)
    db.refresh(col)
    return _collection_out(col)


@router.post("/docs", response_model=CollectionOut, status_code=201)
def create_docs_collection(body: DocsCreate, user: User = Depends(get_current_user),
                           db: Session = Depends(get_db)) -> CollectionOut:
    """Learn from a documentation website: crawl it, then build an interactive course."""
    url = body.url.strip()
    if not re.match(r"^https?://", url):
        url = "https://" + url
    if not normalize_url(url) or not urlparse(url).netloc or "." not in urlparse(url).netloc.split(":")[0]:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Please enter a valid documentation URL")
    try:
        parse_youtube_url(url)
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "This is a YouTube link - use the YouTube tab instead")
    except YouTubeError:
        pass
    host = urlparse(url).netloc
    col = Collection(user_id=user.id, kind=CollectionKind.docs.value, source_url=url, title=host,
                     status=Status.queued.value, stage=Stage.waiting.value,
                     thumbnail_url=f"https://www.google.com/s2/favicons?domain={host}&sz=128",
                     settings=body.model_dump())
    db.add(col)
    db.commit()
    enqueue_docs(col.id)
    db.refresh(col)
    return _collection_out(col)


@router.post("/{collection_id}/recrawl", response_model=CollectionOut)
def recrawl(collection_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    col = get_owned_collection(collection_id, user, db)
    if col.kind != CollectionKind.docs.value:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Only documentation collections can be re-crawled")
    if col.status in (Status.queued.value, Status.processing.value):
        raise HTTPException(status.HTTP_409_CONFLICT, "Already processing")
    col.status, col.stage, col.error, col.progress = Status.queued.value, Stage.waiting.value, None, 0.0
    db.commit()
    enqueue_docs(col.id)
    db.refresh(col)
    return _collection_out(col)


@router.get("/{collection_id}/pages/{page_id}", response_model=PageDetailOut)
def get_page(collection_id: str, page_id: str, user: User = Depends(get_current_user),
             db: Session = Depends(get_db)):
    get_owned_collection(collection_id, user, db)
    page = db.get(DocPage, page_id)
    if not page or page.collection_id != collection_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Page not found")
    return page


@router.post("/upload", response_model=CollectionOut, status_code=201)
async def upload_media(
    file: UploadFile = File(...),
    title: str | None = Form(default=None),
    settings_json: str | None = Form(default=None, alias="settings"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CollectionOut:
    """Authorized-content route: upload your own audio/video recording."""
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_MEDIA:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Unsupported file type {ext or '(none)'}")
    try:
        cs = ProcessingSettings.model_validate(json.loads(settings_json)) if settings_json else ProcessingSettings()
    except (ValueError, TypeError) as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"Invalid settings: {exc}") from exc

    data = await file.read()
    if len(data) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "File too large")
    name = title or Path(file.filename or "upload").stem
    col = Collection(user_id=user.id, kind=CollectionKind.upload.value, title=name, status=Status.queued.value,
                     settings=cs.model_dump())
    video = Video(position=0, title=name, status=Status.queued.value)
    col.videos.append(video)
    db.add(col)
    db.flush()
    safe = re.sub(r"[^\w.\-]", "_", file.filename or f"media{ext}")
    key = f"uploads/{col.id}/{safe}"
    get_storage().save_bytes(key, data)
    video.upload_path = key
    db.commit()
    enqueue_video(video.id)
    db.refresh(col)
    return _collection_out(col)


@router.get("", response_model=list[CollectionSummary])
def list_collections(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    cols = db.scalars(
        select(Collection).where(Collection.user_id == user.id)
        .options(selectinload(Collection.videos), selectinload(Collection.pages), selectinload(Collection.course))
        .order_by(Collection.created_at.desc())
    ).all()
    return [CollectionSummary.model_validate(c, from_attributes=True).model_copy(update=_summary(c)) for c in cols]


@router.get("/{collection_id}", response_model=CollectionOut)
def get_collection(collection_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _collection_out(get_owned_collection(collection_id, user, db))


@router.delete("/{collection_id}", status_code=204)
def delete_collection(collection_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    col = get_owned_collection(collection_id, user, db)
    storage = get_storage()
    for d in col.documents:
        try:
            storage.delete(d.storage_key)
        except Exception:  # pragma: no cover
            pass
    for v in col.videos:
        if v.status in (Status.queued.value, Status.processing.value):
            v.status = Status.cancelled.value
        if v.upload_path:
            try:
                storage.delete(v.upload_path)
            except Exception:  # pragma: no cover
                pass
    db.delete(col)
    db.commit()


@router.post("/{collection_id}/retry", response_model=CollectionOut)
def retry_failed(collection_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Retry only the failed videos - completed ones are never re-processed."""
    col = get_owned_collection(collection_id, user, db)
    if col.kind == CollectionKind.docs.value:
        return recrawl(collection_id, user, db)
    failed = [v for v in col.videos if v.status in (Status.failed.value, Status.cancelled.value)]
    if not failed:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No failed videos to retry")
    for v in failed:
        v.status, v.error, v.attempts, v.progress, v.stage = Status.queued.value, None, 0, 0.0, Stage.waiting.value
    col.status, col.stage, col.error = Status.processing.value, Stage.waiting.value, None
    db.commit()
    for v in failed:
        enqueue_video(v.id)
    db.refresh(col)
    return _collection_out(col)


@router.post("/{collection_id}/regenerate", response_model=CollectionOut)
def regenerate(collection_id: str, body: ProcessingSettings, user: User = Depends(get_current_user),
               db: Session = Depends(get_db)):
    """Re-run AI extraction + documents with new settings (transcripts are reused)."""
    col = get_owned_collection(collection_id, user, db)
    if any(v.status in (Status.queued.value, Status.processing.value) for v in col.videos):
        raise HTTPException(status.HTTP_409_CONFLICT, "Collection is still processing")
    col.settings = body.model_dump()
    col.status, col.stage, col.error = Status.processing.value, Stage.waiting.value, None
    for v in col.videos:
        v.status, v.error, v.attempts, v.progress, v.stage = Status.queued.value, None, 0, 0.0, Stage.waiting.value
    db.commit()
    for v in col.videos:
        enqueue_video(v.id)
    db.refresh(col)
    return _collection_out(col)


@router.get("/{collection_id}/logs", response_model=list[LogOut])
def get_logs(collection_id: str, limit: int = 200, user: User = Depends(get_current_user),
             db: Session = Depends(get_db)):
    get_owned_collection(collection_id, user, db)
    return db.scalars(
        select(ProcessingLog).where(ProcessingLog.collection_id == collection_id)
        .order_by(ProcessingLog.id.desc()).limit(min(limit, 1000))
    ).all()


@router.post("/{collection_id}/refresh-status", response_model=CollectionOut)
def refresh_status(collection_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    col = get_owned_collection(collection_id, user, db)
    recompute_collection_status(db, col)
    db.commit()
    return _collection_out(col)
