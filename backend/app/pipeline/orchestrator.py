"""Processing pipeline orchestration.

Per video (independent lifecycle, retried on its own):

    metadata → transcribing → language → extracting → assembling
             → verifying → rendering → done

Per collection (runs once every video reached a terminal state):

    synthesizing (cross-video knowledge) → rendering (playlist book) → done

Every stage updates the database immediately so the UI can show live progress,
and is timed into Prometheus metrics.
"""

from __future__ import annotations

import logging
import re
import time
import traceback
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select, update
from sqlalchemy.orm import selectinload

from app.config import settings
from app.db import session_scope
from app.metrics import DOCUMENTS_GENERATED, STAGE_SECONDS, TRANSCRIPT_SOURCE, VIDEOS_PROCESSED
from app.models import (
    Collection,
    CollectionKind,
    Document,
    ExtractedKnowledge,
    ProcessingJob,
    ProcessingLog,
    Stage,
    Status,
    Transcript,
    TranscriptSegment,
    Video,
)
from app.services import transcripts as tx
from app.services.chunking import fmt_ts
from app.services.knowledge import build_collection_synthesis, build_video_knowledge
from app.services.language import detect_language, resolve_output_language
from app.services.llm import LLMClient, NoProviderConfigured, UsageTracker
from app.services.markdown import collection_markdown, video_markdown
from app.services.pdf.renderer import RenderOptions, VideoInput, render_collection_pdf, render_video_pdf
from app.services.storage import get_storage
from app.services.youtube import YouTubeError, fetch_video_metadata

log = logging.getLogger(__name__)

TERMINAL = {Status.completed.value, Status.failed.value, Status.cancelled.value}


class NonRetryableError(Exception):
    """Errors where retrying cannot help (no captions + no STT, bad config...)."""


def now() -> datetime:
    return datetime.now(UTC)


# ------------------------------------------------------------------ helpers
def _log(collection_id: str | None, video_id: str | None, message: str, level: str = "info",
         stage: str | None = None) -> None:
    getattr(log, "warning" if level == "warning" else "error" if level == "error" else "info")(
        "[%s/%s] %s", collection_id, video_id, message
    )
    with session_scope() as db:
        db.add(ProcessingLog(collection_id=collection_id, video_id=video_id, level=level, stage=stage,
                             message=message[:4000]))


def _update_video(video_id: str, **fields) -> None:
    with session_scope() as db:
        db.execute(update(Video).where(Video.id == video_id).values(**fields, updated_at=now()))


@contextmanager
def _stage(video_id: str, collection_id: str, stage: Stage, progress: float):
    _update_video(video_id, stage=stage.value, progress=progress)
    t0 = time.monotonic()
    try:
        yield
    finally:
        STAGE_SECONDS.labels(stage.value).observe(time.monotonic() - t0)


def _safe_filename(title: str, ext: str) -> str:
    base = re.sub(r"[^\w\-؀-ۿ ]+", "", title).strip().replace(" ", "_")[:80] or "document"
    return f"{base}.{ext}"


def _save_document(db, *, collection_id: str, video_id: str | None, kind: str, fmt: str, title: str,
                   data: bytes, pages: int | None, language: str) -> Document:
    # Replace any previous document of the same kind/format (re-processing).
    old = db.scalars(
        select(Document).where(
            Document.collection_id == collection_id,
            Document.video_id.is_(None) if video_id is None else Document.video_id == video_id,
            Document.kind == kind,
            Document.format == fmt,
        )
    ).all()
    storage = get_storage()
    for d in old:
        try:
            storage.delete(d.storage_key)
        except Exception:  # pragma: no cover
            pass
        db.delete(d)
    key = f"documents/{collection_id}/{video_id or 'collection'}/{_safe_filename(title, fmt)}"
    storage.save_bytes(key, data, "application/pdf" if fmt == "pdf" else "text/markdown")
    doc = Document(collection_id=collection_id, video_id=video_id, kind=kind, format=fmt, title=title,
                   storage_key=key, size_bytes=len(data), pages=pages, language=language)
    db.add(doc)
    DOCUMENTS_GENERATED.labels(kind, fmt).inc()
    return doc


def _cached_transcript(db, video: Video) -> Transcript | None:
    """Idempotency: reuse a transcript already fetched for the same YouTube id."""
    if not video.youtube_id:
        return None
    return db.scalars(
        select(Transcript)
        .join(Video, Video.id == Transcript.video_id)
        .where(Video.youtube_id == video.youtube_id, Video.id != video.id)
        .options(selectinload(Transcript.segments))
        .limit(1)
    ).first()


def _video_input(v: Video, position: int | None = None) -> VideoInput:
    k = v.knowledge
    tr = v.transcript
    return VideoInput(
        title=v.title,
        youtube_id=v.youtube_id,
        url=v.url,
        channel=v.channel,
        duration_seconds=v.duration_seconds,
        published_at=v.published_at,
        language=v.language,
        transcript_source=tr.source if tr else None,
        model=f"{k.llm_provider}/{k.llm_model}" if k and k.llm_provider else None,
        knowledge=k.data if k else {},
        quality=k.quality if k else {},
        segments=list(tr.segments) if tr else [],
        position=position or v.position + 1,
    )


# ------------------------------------------------------------- video stages
def _stage_metadata(video_id: str) -> None:
    with session_scope() as db:
        v = db.get(Video, video_id)
        if not v.youtube_id or v.published_at:
            return
        try:
            meta = fetch_video_metadata(v.youtube_id)
        except YouTubeError as exc:
            _log(v.collection_id, v.id, f"metadata lookup failed (continuing): {exc}", "warning", "metadata")
            return
        v.title = meta.title or v.title
        v.channel = meta.channel or v.channel
        v.duration_seconds = meta.duration_seconds or v.duration_seconds
        v.published_at = meta.published_at
        v.thumbnail_url = meta.thumbnail_url or v.thumbnail_url
        v.description = meta.description


def _stage_transcript(video_id: str) -> None:
    with session_scope() as db:
        v = db.get(Video, video_id)
        if v.transcript and v.transcript.segments:
            return  # already transcribed in a previous attempt
        cached = _cached_transcript(db, v)
        if cached:
            segs = [tx.Segment(s.start, s.end, s.text) for s in cached.segments]
            result = tx.TranscriptResult(source=cached.source, language_code=cached.language_code, segments=segs)
            _log(v.collection_id, v.id, "reused cached transcript", stage="transcribing")
        else:
            youtube_id, upload_key, collection_id = v.youtube_id, v.upload_path, v.collection_id
            result = None

    if not cached:
        try:
            if upload_key:
                path = get_storage().local_path(upload_key)
                if path is None:
                    raise NonRetryableError("uploaded media file is missing")
                result = tx.transcribe_media(Path(path), source="upload")
            elif youtube_id:
                result = tx.get_youtube_transcript(youtube_id)
            else:
                raise NonRetryableError("video has neither a YouTube id nor an uploaded file")
        except tx.TranscriptUnavailable as exc:
            raise NonRetryableError(
                f"No transcript available: {exc}. Tip: configure GROQ_API_KEY for Whisper transcription, "
                "set YOUTUBE_PROXY_URL if YouTube blocks your server IP, or upload the audio file."
            ) from exc
        _log(collection_id, video_id, f"transcript via {result.source} ({len(result.segments)} segments)",
             stage="transcribing")

    TRANSCRIPT_SOURCE.labels(result.source).inc()
    with session_scope() as db:
        v = db.get(Video, video_id)
        if v.transcript:
            db.delete(v.transcript)
            db.flush()
        text = result.text
        tr = Transcript(video_id=v.id, source=result.source, language_code=result.language_code,
                        full_text=text, word_count=len(text.split()))
        tr.segments = [TranscriptSegment(idx=i, start=s.start, end=s.end, text=s.text)
                       for i, s in enumerate(result.segments)]
        db.add(tr)
        if not v.duration_seconds and result.segments:
            v.duration_seconds = result.segments[-1].end


def _stage_language(video_id: str) -> str:
    with session_scope() as db:
        v = db.get(Video, video_id)
        tr = v.transcript
        lang = detect_language(tr.full_text[:20000], tr.language_code)
        tr.language = lang
        v.language = lang
        return lang


def _stage_knowledge(video_id: str, collection_settings: dict) -> None:
    with session_scope() as db:
        v = db.get(Video, video_id)
        segments = [tx.Segment(s.start, s.end, s.text) for s in v.transcript.segments]
        title, channel, lang, collection_id = v.title, v.channel, v.language, v.collection_id

    out_lang = resolve_output_language(collection_settings.get("output_language", "auto"), lang)
    usage = UsageTracker()
    llm = LLMClient(usage=usage)

    def progress(frac: float, stage: str) -> None:
        stage_enum = {"extracting": Stage.extracting, "assembling": Stage.assembling,
                      "verifying": Stage.verifying}[stage]
        _update_video(video_id, stage=stage_enum.value, progress=round(0.35 + 0.5 * frac, 3))

    vk, quality = build_video_knowledge(
        llm,
        segments,
        title=title,
        channel=channel,
        output_language=out_lang,
        detail_level=collection_settings.get("detail_level", "comprehensive"),
        max_tokens=settings.chunk_max_tokens,
        overlap=settings.chunk_overlap_segments,
        progress=progress,
    )
    quality["llm_calls"] = usage.calls
    for w in quality.get("warnings", []):
        _log(collection_id, video_id, w, "warning", "verifying")
    with session_scope() as db:
        v = db.get(Video, video_id)
        if v.knowledge:
            db.delete(v.knowledge)
            db.flush()
        db.add(ExtractedKnowledge(
            video_id=video_id, output_language=out_lang, data=vk.model_dump(), quality=quality,
            llm_provider=usage.last_provider, llm_model=usage.last_model,
            prompt_tokens=usage.prompt_tokens, completion_tokens=usage.completion_tokens,
        ))
    _log(collection_id, video_id,
         f"extracted {quality['concepts']} concepts with {usage.calls} LLM calls "
         f"({usage.prompt_tokens + usage.completion_tokens} tokens via {usage.last_provider})",
         stage="extracting")


def _stage_render_video(video_id: str, collection_settings: dict) -> None:
    with session_scope() as db:
        v = db.scalars(
            select(Video).where(Video.id == video_id).options(
                selectinload(Video.transcript).selectinload(Transcript.segments), selectinload(Video.knowledge))
        ).one()
        out_lang = v.knowledge.output_language
        opts = RenderOptions(
            output_language=out_lang,
            include_transcript=collection_settings.get("include_transcript", True),
            include_timestamps=collection_settings.get("include_timestamps", True),
        )
        vi = _video_input(v)
        pdf, pages = render_video_pdf(vi, opts)
        _save_document(db, collection_id=v.collection_id, video_id=v.id, kind="video", fmt="pdf",
                       title=v.title, data=pdf, pages=pages, language=out_lang)
        md = video_markdown(
            v.title, v.youtube_id,
            {"channel": v.channel, "duration": fmt_ts(v.duration_seconds) if v.duration_seconds else None,
             "language": v.language, "url": v.url},
            vi.knowledge, vi.segments, opts.include_transcript,
        )
        _save_document(db, collection_id=v.collection_id, video_id=v.id, kind="video", fmt="md",
                       title=v.title, data=md.encode("utf-8"), pages=None, language=out_lang)


def process_video(video_id: str) -> None:
    """Run the full pipeline for one video. Safe to call again (idempotent stages)."""
    with session_scope() as db:
        v = db.get(Video, video_id)
        if v is None:
            return
        if v.status in (Status.completed.value, Status.cancelled.value):
            return
        col = v.collection
        collection_id = col.id
        col_settings = dict(col.settings or {})
        v.status = Status.processing.value
        v.attempts += 1
        v.error = None
        v.started_at = v.started_at or now()
        attempt = v.attempts
        job = ProcessingJob(kind="video", video_id=v.id, collection_id=collection_id,
                            status=Status.processing.value, attempt=attempt, started_at=now())
        db.add(job)
        if col.status in (Status.pending.value, Status.queued.value):
            col.status = Status.processing.value
        db.flush()
        job_id = job.id

    t0 = time.monotonic()
    try:
        with _stage(video_id, collection_id, Stage.metadata, 0.05):
            _stage_metadata(video_id)
        with _stage(video_id, collection_id, Stage.transcribing, 0.15):
            _stage_transcript(video_id)
        with _stage(video_id, collection_id, Stage.language, 0.3):
            lang = _stage_language(video_id)
            _log(collection_id, video_id, f"detected language: {lang}", stage="language")
        with _stage(video_id, collection_id, Stage.extracting, 0.35):
            _stage_knowledge(video_id, col_settings)
        if col_settings.get("per_video_documents", True):
            with _stage(video_id, collection_id, Stage.rendering, 0.9):
                _stage_render_video(video_id, col_settings)
        _update_video(video_id, status=Status.completed.value, stage=Stage.done.value, progress=1.0,
                      finished_at=now(), error=None)
        _finish_job(job_id, Status.completed.value, None, time.monotonic() - t0)
        VIDEOS_PROCESSED.labels("completed").inc()
        _log(collection_id, video_id, f"completed in {time.monotonic() - t0:.1f}s", stage="done")
    except Exception as exc:  # noqa: BLE001 - we want to record every failure
        retryable = not isinstance(exc, (NonRetryableError, NoProviderConfigured))
        msg = str(exc) or exc.__class__.__name__
        _finish_job(job_id, Status.failed.value, msg, time.monotonic() - t0)
        _log(collection_id, video_id, f"attempt {attempt} failed: {msg}", "error")
        log.debug(traceback.format_exc())
        if retryable and attempt < settings.max_retries:
            delay = settings.retry_base_delay * (2 ** (attempt - 1))
            _update_video(video_id, status=Status.queued.value, error=f"Retrying in {delay:.0f}s: {msg}")
            from app.workers.queue import enqueue_video

            enqueue_video(video_id, delay=delay)
            return
        _update_video(video_id, status=Status.failed.value, error=msg, finished_at=now())
        VIDEOS_PROCESSED.labels("failed").inc()
    check_collection(collection_id)


def _finish_job(job_id: str, status: str, error: str | None, seconds: float) -> None:
    with session_scope() as db:
        job = db.get(ProcessingJob, job_id)
        if job:
            job.status = status
            job.error = error
            job.finished_at = now()
            job.metrics = {**(job.metrics or {}), "seconds": round(seconds, 2)}


# --------------------------------------------------------- collection level
def recompute_collection_status(db, col: Collection) -> None:
    states = [v.status for v in col.videos]
    if not states:
        return
    if any(s not in TERMINAL for s in states):
        if col.status not in (Status.processing.value,) and any(
                s in (Status.processing.value, Status.completed.value, Status.failed.value) for s in states):
            col.status = Status.processing.value
        return
    done = states.count(Status.completed.value)
    if done == len(states):
        col.status = Status.completed.value
    elif done == 0:
        col.status = Status.failed.value
    else:
        col.status = Status.partial.value


def check_collection(collection_id: str) -> None:
    """Called after each video finishes; triggers synthesis exactly once."""
    with session_scope() as db:
        col = db.get(Collection, collection_id)
        if col is None:
            return
        states = [v.status for v in col.videos]
        if any(s not in TERMINAL for s in states):
            return
        completed = states.count(Status.completed.value)
        wants_book = (col.kind == CollectionKind.playlist.value and completed > 0
                      and (col.settings or {}).get("combined_document", True))
        if not wants_book:
            col.stage = Stage.done.value
            recompute_collection_status(db, col)
            if completed == 0:
                col.error = "All videos failed"
            return
        # Atomic claim so concurrent workers don't start synthesis twice.
        claimed = db.execute(
            update(Collection)
            .where(Collection.id == collection_id, Collection.stage != Stage.synthesizing.value)
            .values(stage=Stage.synthesizing.value, status=Status.processing.value)
        ).rowcount
    if claimed:
        from app.workers.queue import enqueue_synthesis

        enqueue_synthesis(collection_id)


def synthesize_collection(collection_id: str) -> None:
    t0 = time.monotonic()
    with session_scope() as db:
        col = db.scalars(
            select(Collection).where(Collection.id == collection_id).options(
                selectinload(Collection.videos).selectinload(Video.knowledge),
                selectinload(Collection.videos).selectinload(Video.transcript).selectinload(Transcript.segments),
            )
        ).one()
        cs = dict(col.settings or {})
        videos = [v for v in col.videos if v.status == Status.completed.value and v.knowledge]
        langs = [v.knowledge.output_language for v in videos]
        out_lang = max(set(langs), key=langs.count) if langs else "en"
        items = [(i + 1, v.title, v.knowledge.data) for i, v in enumerate(videos)]
        inputs = [_video_input(v, i + 1) for i, v in enumerate(videos)]
        title, channel = col.title, col.channel
        job = ProcessingJob(kind="synthesis", collection_id=collection_id, status=Status.processing.value,
                            started_at=now())
        db.add(job)
        db.flush()
        job_id = job.id

    synthesis: dict = {}
    try:
        if len(items) > 1:
            syn = build_collection_synthesis(LLMClient(), items, out_lang, title)
            synthesis = syn.model_dump()
        _log(collection_id, None, "cross-video synthesis complete", stage="synthesizing")
    except Exception as exc:  # noqa: BLE001
        _log(collection_id, None, f"cross-video synthesis failed, building book without it: {exc}", "warning",
             "synthesizing")

    try:
        opts = RenderOptions(output_language=out_lang, include_transcript=cs.get("include_transcript", True),
                             include_timestamps=cs.get("include_timestamps", True))
        with session_scope() as db:
            db.execute(update(Collection).where(Collection.id == collection_id).values(stage=Stage.rendering.value))
        pdf, pages = render_collection_pdf(title, channel, synthesis, inputs, opts)
        blocks = [
            video_markdown(f"{vi.position:02d}. {vi.title}", vi.youtube_id, {"channel": vi.channel, "url": vi.url},
                           vi.knowledge, vi.segments, opts.include_transcript, heading="##")
            for vi in inputs
        ]
        md = collection_markdown(title, synthesis, blocks)
        with session_scope() as db:
            col = db.get(Collection, collection_id)
            col.synthesis = synthesis or None
            _save_document(db, collection_id=collection_id, video_id=None, kind="collection", fmt="pdf",
                           title=title, data=pdf, pages=pages, language=out_lang)
            _save_document(db, collection_id=collection_id, video_id=None, kind="collection", fmt="md",
                           title=title, data=md.encode("utf-8"), pages=None, language=out_lang)
            col.stage = Stage.done.value
            recompute_collection_status(db, col)
        _finish_job(job_id, Status.completed.value, None, time.monotonic() - t0)
        _log(collection_id, None, f"playlist book generated ({pages} pages)", stage="rendering")
    except Exception as exc:  # noqa: BLE001
        _finish_job(job_id, Status.failed.value, str(exc), time.monotonic() - t0)
        _log(collection_id, None, f"playlist book failed: {exc}", "error", "rendering")
        with session_scope() as db:
            col = db.get(Collection, collection_id)
            col.stage = Stage.done.value
            col.error = f"Combined document failed: {exc}"
            recompute_collection_status(db, col)
