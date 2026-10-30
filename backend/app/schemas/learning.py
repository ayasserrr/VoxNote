"""Structured-output schemas for the Learning Hub (curriculum, lessons, quizzes, grading)."""

from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.knowledge import _to_int_list


class _Lenient(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)


# ------------------------------------------------------------- curriculum
class CurriculumLesson(_Lenient):
    title: str
    objectives: list[str] = Field(default_factory=list)
    sources: list[int] = Field(default_factory=list)  # 1-based source numbers
    estimated_minutes: int = 10

    @field_validator("sources", mode="before")
    @classmethod
    def _ints(cls, v: Any) -> list[int]:
        return _to_int_list(v)

    @field_validator("estimated_minutes", mode="before")
    @classmethod
    def _minutes(cls, v: Any) -> int:
        try:
            return max(3, min(int(float(str(v).split()[0])), 60))
        except (ValueError, IndexError):
            return 10


class CurriculumModule(_Lenient):
    title: str
    summary: str = ""
    lessons: list[CurriculumLesson] = Field(default_factory=list)


class Curriculum(_Lenient):
    title: str = ""
    description: str = ""
    outcomes: list[str] = Field(default_factory=list)
    modules: list[CurriculumModule] = Field(default_factory=list)


# ----------------------------------------------------------------- lessons
QuestionType = Literal["mcq", "true_false", "short"]


class QuizQuestion(_Lenient):
    id: str = ""
    type: QuestionType = "mcq"
    question: str
    options: list[str] = Field(default_factory=list)
    answer: Any = None  # mcq: option index; true_false: bool; short: reference answer
    explanation: str = ""
    difficulty: Literal["easy", "medium", "hard"] = "easy"

    @field_validator("type", mode="before")
    @classmethod
    def _type(cls, v: Any) -> str:
        v = str(v or "mcq").lower().replace("-", "_").replace(" ", "_")
        aliases = {"multiple_choice": "mcq", "choice": "mcq", "truefalse": "true_false", "tf": "true_false",
                   "boolean": "true_false", "open": "short", "short_answer": "short", "open_ended": "short",
                   "text": "short"}
        v = aliases.get(v, v)
        return v if v in {"mcq", "true_false", "short"} else "mcq"

    @field_validator("difficulty", mode="before")
    @classmethod
    def _diff(cls, v: Any) -> str:
        v = str(v or "easy").lower()
        return v if v in {"easy", "medium", "hard"} else "easy"

    @model_validator(mode="after")
    def _normalize_answer(self) -> QuizQuestion:
        if self.type == "true_false":
            a = self.answer
            if isinstance(a, str):
                a = a.strip().lower() in {"true", "t", "yes", "صح", "صحيح", "1"}
            self.answer = bool(a)
            self.options = ["True", "False"]
        elif self.type == "mcq":
            self.options = [str(o).strip() for o in self.options if str(o).strip()][:6]
            if len(self.options) < 2:
                # Not a usable MCQ -> turn it into an open question.
                self.type = "short"
                self.answer = str(self.answer or "")
                return self
            self.answer = _mcq_index(self.answer, self.options)
        else:
            self.options = []
            self.answer = "" if self.answer is None else str(self.answer)
        return self


def _mcq_index(answer: Any, options: list[str]) -> int:
    if isinstance(answer, bool):
        return 0
    if isinstance(answer, int):
        return answer if 0 <= answer < len(options) else 0
    s = str(answer or "").strip()
    if re.fullmatch(r"\d+", s):
        i = int(s)
        return i if i < len(options) else max(i - 1, 0)
    m = re.fullmatch(r"\(?([A-Fa-f])[\).:]?", s)
    if m:
        return min(ord(m.group(1).upper()) - 65, len(options) - 1)
    m = re.match(r"^([A-Fa-f])[\).:]\s+", s)
    if m:
        return min(ord(m.group(1).upper()) - 65, len(options) - 1)
    low = s.lower()
    for i, o in enumerate(options):
        if o.lower() == low or (low and low in o.lower()):
            return i
    return 0


class LessonExample(_Lenient):
    title: str = ""
    content: str = ""  # Markdown (may contain code)


class LessonContent(_Lenient):
    title: str = ""
    summary: str = ""
    explanation: str = ""  # Markdown
    analogy: str = ""
    key_points: list[str] = Field(default_factory=list)
    example: LessonExample | None = None
    common_mistakes: list[str] = Field(default_factory=list)
    quiz: list[QuizQuestion] = Field(default_factory=list)

    @field_validator("example", mode="before")
    @classmethod
    def _example(cls, v: Any) -> Any:
        if isinstance(v, str):
            return {"title": "", "content": v} if v.strip() else None
        return v


class QuizOnly(_Lenient):
    quiz: list[QuizQuestion] = Field(default_factory=list)


class GradeItem(_Lenient):
    id: str
    score: float = 0.0
    feedback: str = ""

    @field_validator("score", mode="before")
    @classmethod
    def _score(cls, v: Any) -> float:
        try:
            x = float(str(v).strip().rstrip("%"))
        except ValueError:
            return 0.0
        if x > 1:
            x = x / 100 if x > 10 else x / 10
        return max(0.0, min(x, 1.0))


class GradeResult(_Lenient):
    items: list[GradeItem] = Field(default_factory=list)


# --------------------------------------------------------------- API models
class CourseCreate(BaseModel):
    level: Literal["beginner", "intermediate", "advanced"] = "beginner"
    language: Literal["auto", "en", "ar", "bilingual"] = "auto"


class DocsCreate(BaseModel):
    url: str = Field(min_length=4, max_length=2000)
    max_pages: int = Field(default=40, ge=1, le=300)
    same_path_only: bool = True
    level: Literal["beginner", "intermediate", "advanced"] = "beginner"
    language: Literal["auto", "en", "ar", "bilingual"] = "auto"


class SubmitAnswers(BaseModel):
    answers: dict[str, Any]


class TutorQuestion(BaseModel):
    question: str = Field(min_length=2, max_length=2000)
