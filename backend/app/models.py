"""ORM models.

Design note: a collection (single video, playlist or upload) never holds the
processing state of its videos. Each `Video` owns an independent lifecycle
(status, stage, attempts) so videos can be retried, processed in parallel and
scaled independently.
"""

from __future__ import annotations

import enum
import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


def new_id() -> str:
    return uuid.uuid4().hex


class CollectionKind(str, enum.Enum):
    video = "video"
    playlist = "playlist"
    upload = "upload"
    docs = "docs"


class Status(str, enum.Enum):
    pending = "pending"
    queued = "queued"
    processing = "processing"
    completed = "completed"
    partial = "partial"  # collection: some videos failed
    failed = "failed"
    cancelled = "cancelled"


class Stage(str, enum.Enum):
    waiting = "waiting"
    metadata = "metadata"
    transcribing = "transcribing"
    language = "language"
    extracting = "extracting"
    assembling = "assembling"
    verifying = "verifying"
    rendering = "rendering"
    synthesizing = "synthesizing"
    crawling = "crawling"
    structuring = "structuring"
    done = "done"


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    full_name: Mapped[str | None] = mapped_column(String(255))
    hashed_password: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    collections: Mapped[list[Collection]] = relationship(back_populates="user", cascade="all, delete-orphan")


class Collection(Base):
    """A processing request: one YouTube video, a playlist, or an uploaded file."""

    __tablename__ = "collections"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(16), default=CollectionKind.video.value)
    source_url: Mapped[str | None] = mapped_column(Text)
    youtube_playlist_id: Mapped[str | None] = mapped_column(String(64), index=True)
    title: Mapped[str] = mapped_column(String(500), default="Untitled")
    channel: Mapped[str | None] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    thumbnail_url: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), default=Status.pending.value, index=True)
    stage: Mapped[str] = mapped_column(String(16), default=Stage.waiting.value)
    error: Mapped[str | None] = mapped_column(Text)
    settings: Mapped[dict] = mapped_column(JSON, default=dict)
    synthesis: Mapped[dict | None] = mapped_column(JSON)  # cross-video knowledge
    progress: Mapped[float] = mapped_column(Float, default=0.0)  # used by docs crawling
    meta: Mapped[dict] = mapped_column(JSON, default=dict)  # crawl stats, warnings
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    user: Mapped[User] = relationship(back_populates="collections")
    videos: Mapped[list[Video]] = relationship(
        back_populates="collection", cascade="all, delete-orphan", order_by="Video.position"
    )
    documents: Mapped[list[Document]] = relationship(
        back_populates="collection", cascade="all, delete-orphan"
    )
    pages: Mapped[list[DocPage]] = relationship(
        back_populates="collection", cascade="all, delete-orphan", order_by="DocPage.position"
    )
    course: Mapped[Course | None] = relationship(
        back_populates="collection", cascade="all, delete-orphan", uselist=False
    )


class Video(Base):
    __tablename__ = "videos"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    collection_id: Mapped[str] = mapped_column(ForeignKey("collections.id", ondelete="CASCADE"), index=True)
    position: Mapped[int] = mapped_column(Integer, default=0)
    youtube_id: Mapped[str | None] = mapped_column(String(32), index=True)
    url: Mapped[str | None] = mapped_column(Text)
    upload_path: Mapped[str | None] = mapped_column(Text)  # storage key for uploaded media
    title: Mapped[str] = mapped_column(String(500), default="Untitled video")
    channel: Mapped[str | None] = mapped_column(String(255))
    duration_seconds: Mapped[float | None] = mapped_column(Float)
    published_at: Mapped[str | None] = mapped_column(String(32))
    thumbnail_url: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    language: Mapped[str | None] = mapped_column(String(16))  # en | ar | mixed
    status: Mapped[str] = mapped_column(String(16), default=Status.pending.value, index=True)
    stage: Mapped[str] = mapped_column(String(16), default=Stage.waiting.value)
    progress: Mapped[float] = mapped_column(Float, default=0.0)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    collection: Mapped[Collection] = relationship(back_populates="videos")
    transcript: Mapped[Transcript | None] = relationship(
        back_populates="video", cascade="all, delete-orphan", uselist=False
    )
    knowledge: Mapped[ExtractedKnowledge | None] = relationship(
        back_populates="video", cascade="all, delete-orphan", uselist=False
    )
    jobs: Mapped[list[ProcessingJob]] = relationship(back_populates="video", cascade="all, delete-orphan")


class ProcessingJob(Base):
    """One execution attempt of a pipeline (per video or per collection synthesis)."""

    __tablename__ = "processing_jobs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    kind: Mapped[str] = mapped_column(String(16), default="video")  # video | synthesis
    video_id: Mapped[str | None] = mapped_column(ForeignKey("videos.id", ondelete="CASCADE"), index=True)
    collection_id: Mapped[str | None] = mapped_column(
        ForeignKey("collections.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[str] = mapped_column(String(16), default=Status.queued.value)
    attempt: Mapped[int] = mapped_column(Integer, default=1)
    error: Mapped[str | None] = mapped_column(Text)
    metrics: Mapped[dict] = mapped_column(JSON, default=dict)  # timings, tokens, provider
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    video: Mapped[Video | None] = relationship(back_populates="jobs")


class Transcript(Base):
    __tablename__ = "transcripts"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    video_id: Mapped[str] = mapped_column(ForeignKey("videos.id", ondelete="CASCADE"), unique=True)
    source: Mapped[str] = mapped_column(String(32))  # captions | auto_captions | whisper | upload
    language: Mapped[str | None] = mapped_column(String(16))
    language_code: Mapped[str | None] = mapped_column(String(16))  # raw code from source
    full_text: Mapped[str] = mapped_column(Text, default="")
    word_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    video: Mapped[Video] = relationship(back_populates="transcript")
    segments: Mapped[list[TranscriptSegment]] = relationship(
        back_populates="transcript", cascade="all, delete-orphan", order_by="TranscriptSegment.idx"
    )


class TranscriptSegment(Base):
    __tablename__ = "transcript_segments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    transcript_id: Mapped[str] = mapped_column(ForeignKey("transcripts.id", ondelete="CASCADE"), index=True)
    idx: Mapped[int] = mapped_column(Integer)
    start: Mapped[float] = mapped_column(Float)
    end: Mapped[float] = mapped_column(Float)
    text: Mapped[str] = mapped_column(Text)

    transcript: Mapped[Transcript] = relationship(back_populates="segments")


class ExtractedKnowledge(Base):
    __tablename__ = "extracted_knowledge"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    video_id: Mapped[str] = mapped_column(ForeignKey("videos.id", ondelete="CASCADE"), unique=True)
    output_language: Mapped[str] = mapped_column(String(16), default="en")
    data: Mapped[dict] = mapped_column(JSON, default=dict)  # VideoKnowledge schema
    quality: Mapped[dict] = mapped_column(JSON, default=dict)  # verification report
    llm_provider: Mapped[str | None] = mapped_column(String(64))
    llm_model: Mapped[str | None] = mapped_column(String(128))
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    video: Mapped[Video] = relationship(back_populates="knowledge")


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    collection_id: Mapped[str] = mapped_column(ForeignKey("collections.id", ondelete="CASCADE"), index=True)
    video_id: Mapped[str | None] = mapped_column(ForeignKey("videos.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(16))  # video | collection
    format: Mapped[str] = mapped_column(String(8), default="pdf")  # pdf | md
    title: Mapped[str] = mapped_column(String(500))
    storage_key: Mapped[str] = mapped_column(Text)
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    pages: Mapped[int | None] = mapped_column(Integer)
    language: Mapped[str | None] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    collection: Mapped[Collection] = relationship(back_populates="documents")


class ProcessingLog(Base):
    __tablename__ = "processing_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    collection_id: Mapped[str | None] = mapped_column(
        ForeignKey("collections.id", ondelete="CASCADE"), index=True
    )
    video_id: Mapped[str | None] = mapped_column(ForeignKey("videos.id", ondelete="CASCADE"), index=True)
    level: Mapped[str] = mapped_column(String(8), default="info")
    stage: Mapped[str | None] = mapped_column(String(16))
    message: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class DocPage(Base):
    """One crawled documentation page (cleaned main content as Markdown-like text)."""

    __tablename__ = "doc_pages"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    collection_id: Mapped[str] = mapped_column(ForeignKey("collections.id", ondelete="CASCADE"), index=True)
    position: Mapped[int] = mapped_column(Integer, default=0)
    url: Mapped[str] = mapped_column(Text)
    title: Mapped[str] = mapped_column(String(500), default="Untitled page")
    headings: Mapped[list] = mapped_column(JSON, default=list)
    content: Mapped[str] = mapped_column(Text, default="")
    word_count: Mapped[int] = mapped_column(Integer, default=0)
    language: Mapped[str | None] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    collection: Mapped[Collection] = relationship(back_populates="pages")


class Course(Base):
    """An interactive learning path generated from a collection (docs, video or playlist)."""

    __tablename__ = "courses"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    collection_id: Mapped[str] = mapped_column(
        ForeignKey("collections.id", ondelete="CASCADE"), unique=True, index=True
    )
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(500), default="Course")
    description: Mapped[str] = mapped_column(Text, default="")
    level: Mapped[str] = mapped_column(String(16), default="beginner")  # beginner|intermediate|advanced
    language: Mapped[str] = mapped_column(String(16), default="auto")
    status: Mapped[str] = mapped_column(String(16), default=Status.queued.value)  # queued|processing|completed|failed
    error: Mapped[str | None] = mapped_column(Text)
    outcomes: Mapped[list] = mapped_column(JSON, default=list)  # what the learner will be able to do
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    last_opened_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    collection: Mapped[Collection] = relationship(back_populates="course")
    lessons: Mapped[list[Lesson]] = relationship(
        back_populates="course", cascade="all, delete-orphan", order_by="Lesson.position"
    )


class Lesson(Base):
    __tablename__ = "lessons"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    course_id: Mapped[str] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"), index=True)
    position: Mapped[int] = mapped_column(Integer, default=0)  # global order in the course
    module_index: Mapped[int] = mapped_column(Integer, default=0)
    module_title: Mapped[str] = mapped_column(String(500), default="")
    kind: Mapped[str] = mapped_column(String(16), default="lesson")  # lesson | exam (final course exam)
    title: Mapped[str] = mapped_column(String(500))
    objectives: Mapped[list] = mapped_column(JSON, default=list)
    estimated_minutes: Mapped[int] = mapped_column(Integer, default=10)
    source_refs: Mapped[list] = mapped_column(JSON, default=list)  # pages / video ranges
    status: Mapped[str] = mapped_column(String(16), default="locked")  # locked|available|completed
    content: Mapped[dict | None] = mapped_column(JSON)  # explanation, key points, example...
    quiz: Mapped[list | None] = mapped_column(JSON)  # questions WITH answers (never sent before submit)
    simplicity: Mapped[int] = mapped_column(Integer, default=0)  # 0 normal, 1+ "explain simpler"
    generating_since: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))  # lock for generation
    best_score: Mapped[float | None] = mapped_column(Float)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notes: Mapped[str | None] = mapped_column(Text)  # the learner's personal notes

    course: Mapped[Course] = relationship(back_populates="lessons")
    quiz_attempts: Mapped[list[QuizAttempt]] = relationship(
        back_populates="lesson", cascade="all, delete-orphan", order_by="QuizAttempt.created_at"
    )


class QuizAttempt(Base):
    __tablename__ = "quiz_attempts"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    lesson_id: Mapped[str] = mapped_column(ForeignKey("lessons.id", ondelete="CASCADE"), index=True)
    answers: Mapped[dict] = mapped_column(JSON, default=dict)
    results: Mapped[list] = mapped_column(JSON, default=list)
    score: Mapped[float] = mapped_column(Float, default=0.0)
    passed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    lesson: Mapped[Lesson] = relationship(back_populates="quiz_attempts")


class ReviewItem(Base):
    """A quiz question the learner got wrong, scheduled for spaced repetition (Leitner boxes)."""

    __tablename__ = "review_items"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    course_id: Mapped[str] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"), index=True)
    lesson_id: Mapped[str] = mapped_column(ForeignKey("lessons.id", ondelete="CASCADE"), index=True)
    question_key: Mapped[str] = mapped_column(String(40), index=True)  # hash of the question text
    question: Mapped[dict] = mapped_column(JSON)  # full question incl. answer + explanation
    box: Mapped[int] = mapped_column(Integer, default=0)  # 0..5, 5 = mastered
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    reviews: Mapped[int] = mapped_column(Integer, default=0)
    correct_count: Mapped[int] = mapped_column(Integer, default=0)
    last_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    mastered: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    lesson: Mapped[Lesson] = relationship()
    course: Mapped[Course] = relationship()
