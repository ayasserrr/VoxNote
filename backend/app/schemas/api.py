"""Request / response models for the REST API."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ------------------------------------------------------------------- auth
class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)
    full_name: str | None = None


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(ORM):
    id: str
    email: str
    full_name: str | None
    created_at: datetime


# -------------------------------------------------------------- processing
OutputLanguage = Literal["auto", "en", "ar", "bilingual"]
DetailLevel = Literal["standard", "comprehensive"]


class ProcessingSettings(BaseModel):
    output_language: OutputLanguage = "auto"
    detail_level: DetailLevel = "comprehensive"
    include_transcript: bool = True
    include_timestamps: bool = True
    per_video_documents: bool = True
    combined_document: bool = True
    max_videos: int | None = Field(default=None, ge=1, le=1000)


class CollectionCreate(BaseModel):
    url: str = Field(min_length=5, max_length=2000)
    settings: ProcessingSettings = Field(default_factory=ProcessingSettings)


class UrlPreviewIn(BaseModel):
    url: str


class UrlPreviewOut(BaseModel):
    kind: Literal["video", "playlist"]
    video_id: str | None = None
    playlist_id: str | None = None
    title: str | None = None
    channel: str | None = None
    thumbnail_url: str | None = None
    video_count: int | None = None
    duration_seconds: float | None = None


class DocumentOut(ORM):
    id: str
    kind: str
    format: str
    title: str
    size_bytes: int
    pages: int | None
    language: str | None
    video_id: str | None
    created_at: datetime


class VideoOut(ORM):
    id: str
    position: int
    youtube_id: str | None
    url: str | None
    title: str
    channel: str | None
    duration_seconds: float | None
    published_at: str | None
    thumbnail_url: str | None
    language: str | None
    status: str
    stage: str
    progress: float
    attempts: int
    error: str | None
    started_at: datetime | None
    finished_at: datetime | None


class CollectionSummary(ORM):
    id: str
    kind: str
    title: str
    channel: str | None
    thumbnail_url: str | None
    source_url: str | None
    status: str
    stage: str
    created_at: datetime
    updated_at: datetime
    video_count: int = 0
    completed_count: int = 0
    failed_count: int = 0
    page_count: int = 0
    progress: float = 0.0
    course_id: str | None = None


class PageOut(ORM):
    id: str
    position: int
    url: str
    title: str
    headings: list[str]
    word_count: int
    language: str | None


class PageDetailOut(PageOut):
    content: str


class CollectionOut(CollectionSummary):
    description: str | None
    error: str | None
    settings: dict[str, Any]
    synthesis: dict[str, Any] | None
    meta: dict[str, Any] = {}
    videos: list[VideoOut]
    documents: list[DocumentOut]
    pages: list[PageOut] = []


class SegmentOut(ORM):
    idx: int
    start: float
    end: float
    text: str


class TranscriptOut(ORM):
    source: str
    language: str | None
    language_code: str | None
    word_count: int
    segments: list[SegmentOut]


class VideoDetailOut(VideoOut):
    collection_id: str
    description: str | None
    knowledge: dict[str, Any] | None = None
    quality: dict[str, Any] | None = None
    llm_provider: str | None = None
    llm_model: str | None = None
    documents: list[DocumentOut] = []


class LogOut(ORM):
    id: int
    video_id: str | None
    level: str
    stage: str | None
    message: str
    created_at: datetime


# ----------------------------------------------------------- ask / search
class AskIn(BaseModel):
    question: str = Field(min_length=2, max_length=2000)
    collection_id: str | None = None  # None = whole library
    video_id: str | None = None
    top_k: int = Field(default=8, ge=1, le=20)


class SourceRef(BaseModel):
    ref: int
    kind: Literal["video", "page"] = "video"
    video_id: str  # video id, or page id for documentation pages
    video_title: str
    youtube_id: str | None
    start: float
    end: float
    text: str
    url: str | None


class AskOut(BaseModel):
    answer: str
    sources: list[SourceRef]
    provider: str | None = None
    model: str | None = None


class SearchHit(SourceRef):
    score: float
    collection_id: str


class SystemStatus(BaseModel):
    app: str
    version: str
    task_backend: str
    llm_providers: list[dict[str, Any]]
    stt_provider: str
    stt_available: bool
    ffmpeg_available: bool
    storage_backend: str


# ---------------------------------------------------------- learning hub
class LessonSummary(ORM):
    id: str
    position: int
    module_index: int
    module_title: str
    kind: str = "lesson"
    title: str
    objectives: list[str]
    estimated_minutes: int
    status: str
    best_score: float | None
    attempts: int
    has_content: bool = False


class CourseProgress(BaseModel):
    lesson_count: int = 0
    completed_count: int = 0
    progress: float = 0.0
    average_score: float | None = None
    xp: int = 0
    next_lesson_id: str | None = None
    next_lesson_title: str | None = None
    minutes_total: int = 0
    exam_lesson_id: str | None = None
    exam_status: str | None = None
    exam_score: float | None = None
    certified: bool = False
    certified_at: datetime | None = None


class CourseSummary(ORM):
    id: str
    collection_id: str
    collection_kind: str = ""
    source_url: str | None = None
    thumbnail_url: str | None = None
    title: str
    description: str
    level: str
    language: str
    status: str
    error: str | None
    created_at: datetime
    updated_at: datetime
    last_opened_at: datetime | None
    stats: CourseProgress = CourseProgress()


class CourseOut(CourseSummary):
    outcomes: list[str]
    lessons: list[LessonSummary]


class LessonSource(BaseModel):
    kind: str
    title: str
    url: str | None = None
    page_id: str | None = None
    video_id: str | None = None
    youtube_id: str | None = None
    start: float | None = None
    end: float | None = None


class AttemptOut(ORM):
    id: str
    score: float
    passed: bool
    results: list[dict[str, Any]]
    created_at: datetime


class LessonOut(LessonSummary):
    course_id: str
    course_title: str
    language: str
    content: dict[str, Any] | None
    quiz: list[dict[str, Any]]
    sources: list[LessonSource]
    generating: bool
    simplicity: int
    prev_lesson_id: str | None
    next_lesson_id: str | None
    last_attempt: AttemptOut | None = None
    pass_score: float
    notes: str | None = None


class SubmitOut(BaseModel):
    attempt: AttemptOut
    lesson: LessonSummary
    next_lesson_id: str | None
    course_completed: bool


class TutorOut(BaseModel):
    answer: str
    provider: str | None = None
    model: str | None = None


class DashboardOut(BaseModel):
    collections: int
    videos_processed: int
    pages_read: int
    documents: int
    courses: int
    lessons_completed: int
    quizzes_taken: int
    average_score: float | None
    xp: int
    streak_days: int = 0
    due_reviews: int = 0
    certificates: int = 0
    continue_learning: list[CourseSummary]
    recent: list[CollectionSummary]


class NotesIn(BaseModel):
    notes: str = Field(default="", max_length=20000)


class ReviewQuestion(BaseModel):
    id: str
    type: str
    question: str
    options: list[str] | None = None
    difficulty: str | None = None


class ReviewCard(BaseModel):
    id: str
    box: int
    reviews: int
    course_id: str
    course_title: str
    lesson_id: str
    lesson_title: str
    question: ReviewQuestion


class ReviewQueue(BaseModel):
    cards: list[ReviewCard]
    due: int
    upcoming: int
    mastered: int
    total: int


class ReviewAnswerIn(BaseModel):
    answer: Any = None


class ReviewAnswerOut(BaseModel):
    result: dict[str, Any]
    box: int
    mastered: bool
    next_due_at: datetime
