"""Structured-output schemas for the AI knowledge engine.

Every LLM response is validated against these Pydantic models instead of
accepting free-form text. Fields are lenient (defaults everywhere, coercing
validators) because free models occasionally omit keys or return a number as
a string; anything that cannot be coerced is dropped rather than crashing the
pipeline.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _to_seconds(v: Any) -> float | None:
    """Accept 125, "125", "02:05", "1:02:05" -> seconds."""
    if v is None or v == "":
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip()
    try:
        return float(s)
    except ValueError:
        pass
    parts = s.replace(".", ":").split(":")
    try:
        nums = [float(p) for p in parts if p != ""]
    except ValueError:
        return None
    total = 0.0
    for n in nums[:3]:
        total = total * 60 + n
    return total


def _to_int_list(v: Any) -> list[int]:
    """Accept [1, "2", "#3", "Video 4"] -> [1, 2, 3, 4]."""
    if not isinstance(v, list):
        v = [v] if v not in (None, "") else []
    out: list[int] = []
    for x in v:
        try:
            out.append(int(str(x).strip().lstrip("#").split()[-1]))
        except (ValueError, IndexError):
            continue
    return out


class _Lenient(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)


class TimeRef(_Lenient):
    start: float | None = None
    end: float | None = None

    @field_validator("start", "end", mode="before")
    @classmethod
    def _secs(cls, v: Any) -> float | None:
        return _to_seconds(v)


class Concept(TimeRef):
    name: str
    definition: str = ""
    explanation: str = ""
    instructor_points: list[str] = Field(default_factory=list)
    ai_clarification: str = ""  # explicitly marked as AI-added explanation
    examples: list[str] = Field(default_factory=list)
    related: list[str] = Field(default_factory=list)


class TechnicalItem(TimeRef):
    kind: Literal["code", "equation", "algorithm", "tool", "architecture", "command", "other"] = "other"
    title: str = ""
    content: str = ""
    language: str = ""
    explanation: str = ""

    @field_validator("kind", mode="before")
    @classmethod
    def _kind(cls, v: Any) -> str:
        allowed = {"code", "equation", "algorithm", "tool", "architecture", "command", "other"}
        v = str(v or "other").lower().strip()
        aliases = {"library": "tool", "framework": "tool", "formula": "equation", "math": "equation"}
        v = aliases.get(v, v)
        return v if v in allowed else "other"


class Example(TimeRef):
    title: str = ""
    description: str = ""


class KeyPoint(TimeRef):
    text: str


class GlossaryTerm(_Lenient):
    term: str
    definition: str = ""
    translation: str = ""


class ReviewQuestion(_Lenient):
    question: str
    answer: str = ""
    difficulty: Literal["easy", "medium", "hard"] = "medium"

    @field_validator("difficulty", mode="before")
    @classmethod
    def _diff(cls, v: Any) -> str:
        v = str(v or "medium").lower()
        return v if v in {"easy", "medium", "hard"} else "medium"


class ChunkKnowledge(_Lenient):
    """What the LLM extracts from a single transcript chunk."""

    section_title: str = ""
    summary: str = ""
    concepts: list[Concept] = Field(default_factory=list)
    technical: list[TechnicalItem] = Field(default_factory=list)
    examples: list[Example] = Field(default_factory=list)
    key_points: list[KeyPoint] = Field(default_factory=list)
    glossary: list[GlossaryTerm] = Field(default_factory=list)
    questions: list[ReviewQuestion] = Field(default_factory=list)


class Chapter(TimeRef):
    title: str
    summary: str = ""


class VideoSynthesis(_Lenient):
    """Final, video-level LLM pass over the chunk summaries."""

    title: str = ""
    overview: str = ""
    learning_objectives: list[str] = Field(default_factory=list)
    takeaways: list[str] = Field(default_factory=list)
    prerequisites: list[str] = Field(default_factory=list)


class VideoKnowledge(_Lenient):
    """The fully assembled knowledge document for one video."""

    title: str = ""
    output_language: str = "en"
    overview: str = ""
    learning_objectives: list[str] = Field(default_factory=list)
    prerequisites: list[str] = Field(default_factory=list)
    chapters: list[Chapter] = Field(default_factory=list)
    concepts: list[Concept] = Field(default_factory=list)
    technical: list[TechnicalItem] = Field(default_factory=list)
    examples: list[Example] = Field(default_factory=list)
    key_points: list[KeyPoint] = Field(default_factory=list)
    takeaways: list[str] = Field(default_factory=list)
    glossary: list[GlossaryTerm] = Field(default_factory=list)
    questions: list[ReviewQuestion] = Field(default_factory=list)


class ConceptLink(_Lenient):
    source: str
    target: str
    relation: str = "related to"


class CourseConcept(_Lenient):
    name: str
    description: str = ""
    videos: list[int] = Field(default_factory=list)  # 1-based video positions

    @field_validator("videos", mode="before")
    @classmethod
    def _ints(cls, v: Any) -> list[int]:
        return _to_int_list(v)


class LearningStep(_Lenient):
    step: str
    videos: list[int] = Field(default_factory=list)
    goal: str = ""

    @field_validator("videos", mode="before")
    @classmethod
    def _ints(cls, v: Any) -> list[int]:
        return _to_int_list(v)


class CollectionSynthesis(_Lenient):
    """Playlist-level, cross-video knowledge."""

    course_title: str = ""
    course_summary: str = ""
    concepts: list[CourseConcept] = Field(default_factory=list)
    concept_map: list[ConceptLink] = Field(default_factory=list)
    recurring_concepts: list[str] = Field(default_factory=list)
    learning_path: list[LearningStep] = Field(default_factory=list)
    glossary: list[GlossaryTerm] = Field(default_factory=list)
    final_questions: list[ReviewQuestion] = Field(default_factory=list)
