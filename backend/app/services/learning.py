"""Learning Hub engine.

    sources (doc pages / video sections)
        │  condensed outline
        ▼
    LLM curriculum  ──▶ modules ▶ lessons (each linked to 1-3 sources)
        │
        ▼  on demand, one lesson at a time (and the next one prefetched)
    LLM lesson: easy explanation + analogy + key points + worked example + quiz
        │
        ▼
    learner answers ──▶ MCQ / true-false graded exactly, open answers graded by the LLM
        │                (keyword-overlap fallback when no LLM is reachable)
        ▼
    score ≥ pass mark ──▶ lesson completed, next lesson unlocked

Lessons are generated lazily so a 300-page documentation site does not burn
the free-tier quota up front.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.orm import Session, selectinload

from app.config import settings
from app.db import session_scope
from app.models import (
    Collection,
    CollectionKind,
    Course,
    DocPage,
    Lesson,
    QuizAttempt,
    Status,
    Transcript,
    TranscriptSegment,
    Video,
)
from app.schemas.learning import (
    Curriculum,
    CurriculumLesson,
    CurriculumModule,
    GradeResult,
    LessonContent,
    QuizOnly,
    QuizQuestion,
)
from app.services.chunking import fmt_ts
from app.services.language import detect_language, resolve_output_language
from app.services.llm import LLMClient
from app.services.prompts import (
    GRADE_SYSTEM,
    TUTOR_SYSTEM,
    curriculum_system,
    lesson_system,
    quiz_only_system,
)

log = logging.getLogger(__name__)

PASS_SCORE = settings.quiz_pass_score
LESSON_SOURCE_BUDGET = 14000  # characters of source material per lesson prompt
OUTLINE_BUDGET = 26000  # characters for the curriculum prompt
GENERATION_LOCK = timedelta(minutes=5)


def now() -> datetime:
    return datetime.now(UTC)


# ------------------------------------------------------------------ sources
@dataclass
class Unit:
    """One addressable piece of source material."""

    ref: dict[str, Any]
    title: str
    outline: str


def _video_units(v: Video) -> list[Unit]:
    k = v.knowledge.data if v.knowledge else {}
    chapters = (k or {}).get("chapters") or []
    units: list[Unit] = []
    if chapters:
        for ch in chapters:
            start = float(ch.get("start") or 0)
            end = float(ch.get("end") or start)
            units.append(Unit(
                ref={"kind": "video", "video_id": v.id, "youtube_id": v.youtube_id, "start": start, "end": end,
                     "title": f"{v.title} — {ch.get('title', '')}"},
                title=f"{v.title} — {ch.get('title', '')} [{fmt_ts(start)}]",
                outline=(ch.get("summary") or "")[:260],
            ))
        return units
    # No knowledge yet: split the transcript into ~8-minute sections.
    segs = v.transcript.segments if v.transcript else []
    window = 480.0
    start = None
    texts: list[str] = []
    for s in segs:
        start = s.start if start is None else start
        texts.append(s.text)
        if s.end - start >= window or s is segs[-1]:
            units.append(Unit(
                ref={"kind": "video", "video_id": v.id, "youtube_id": v.youtube_id, "start": start, "end": s.end,
                     "title": f"{v.title} [{fmt_ts(start)}]"},
                title=f"{v.title} [{fmt_ts(start)}–{fmt_ts(s.end)}]",
                outline=" ".join(texts)[:260],
            ))
            start, texts = None, []
    return units


def collect_units(db: Session, col: Collection) -> list[Unit]:
    if col.kind == CollectionKind.docs.value:
        return [
            Unit(
                ref={"kind": "page", "page_id": p.id, "url": p.url, "title": p.title},
                title=p.title,
                outline=("Sections: " + "; ".join(p.headings[:12]) + ". " if p.headings else "")
                + re.sub(r"\s+", " ", p.content[:220]),
            )
            for p in col.pages
        ]
    videos = db.scalars(
        select(Video).where(Video.collection_id == col.id, Video.status == Status.completed.value)
        .options(selectinload(Video.knowledge), selectinload(Video.transcript).selectinload(Transcript.segments))
        .order_by(Video.position)
    ).all()
    units: list[Unit] = []
    for v in videos:
        units.extend(_video_units(v))
    return units


def unit_text(db: Session, ref: dict[str, Any], budget: int) -> str:
    """Resolve a source reference to its text (bounded by `budget` characters)."""
    if ref.get("kind") == "page":
        page = db.get(DocPage, ref.get("page_id"))
        if not page:
            return ""
        return f"# Source: {page.title} ({page.url})\n\n{page.content[:budget]}"
    if ref.get("kind") == "video":
        v = db.get(Video, ref.get("video_id"))
        if not v or not v.transcript:
            return ""
        start, end = float(ref.get("start") or 0), float(ref.get("end") or 1e9)
        segs = db.scalars(
            select(TranscriptSegment).where(
                TranscriptSegment.transcript_id == v.transcript.id,
                TranscriptSegment.end >= start - 1,
                TranscriptSegment.start <= end + 1,
            ).order_by(TranscriptSegment.idx)
        ).all()
        text = "\n".join(f"[{fmt_ts(s.start)}] {s.text}" for s in segs)
        return f"# Source: video \"{v.title}\" ({fmt_ts(start)}–{fmt_ts(end)}), transcript:\n\n{text[:budget]}"
    return ""


def lesson_sources_text(db: Session, refs: list[dict[str, Any]]) -> str:
    if not refs:
        return ""
    per = LESSON_SOURCE_BUDGET // len(refs)
    return "\n\n---\n\n".join(t for t in (unit_text(db, r, per) for r in refs) if t)


# --------------------------------------------------------------- curriculum
def condensed_outline(units: list[Unit]) -> str:
    per = max(OUTLINE_BUDGET // max(len(units), 1), 90)
    lines = []
    for i, u in enumerate(units, 1):
        lines.append(f"[{i}] {u.title}\n    {u.outline}"[:per])
    return "\n".join(lines)


def fallback_curriculum(units: list[Unit], title: str) -> Curriculum:
    """Deterministic course (one lesson per source, modules of 6) when the LLM is unavailable."""
    modules: list[CurriculumModule] = []
    per_module = 6
    for m in range(0, len(units), per_module):
        chunk = units[m: m + per_module]
        modules.append(CurriculumModule(
            title=f"Part {m // per_module + 1}: {chunk[0].title[:60]}",
            lessons=[CurriculumLesson(title=u.title[:120], sources=[m + i + 1]) for i, u in enumerate(chunk)],
        ))
    return Curriculum(title=title, description="", modules=modules[:8])


def sanitize_curriculum(cur: Curriculum, n_units: int, title: str) -> Curriculum:
    """Drop invalid source numbers, empty lessons and enforce limits; attach unused sources."""
    used: set[int] = set()
    modules: list[CurriculumModule] = []
    total = 0
    for m in cur.modules:
        lessons = []
        for lesson in m.lessons:
            lesson.sources = [s for s in dict.fromkeys(lesson.sources) if 1 <= s <= n_units][:3]
            if not lesson.title.strip() or not lesson.sources or total >= 40:
                continue
            used.update(lesson.sources)
            lessons.append(lesson)
            total += 1
        if lessons:
            m.lessons = lessons
            modules.append(m)
    if not modules:
        raise ValueError("curriculum has no valid lessons")
    # Sources the model forgot: attach each to the lesson that uses the closest preceding source.
    missing = [i for i in range(1, n_units + 1) if i not in used]
    flat = [lesson for m in modules for lesson in m.lessons]
    for s in missing:
        best = min(flat, key=lambda les: min(abs(x - s) for x in les.sources))
        if len(best.sources) < 4:
            best.sources.append(s)
    cur.modules = modules
    cur.title = cur.title or title
    return cur


def build_curriculum(llm: LLMClient, units: list[Unit], *, title: str, level: str, language: str) -> Curriculum:
    user = f'Learning material: "{title}" ({len(units)} sources)\n\nSOURCES:\n{condensed_outline(units)}'
    try:
        cur = llm.structured(curriculum_system(level, language), user, Curriculum, max_tokens=4096)
        return sanitize_curriculum(cur, len(units), title)
    except Exception as exc:  # noqa: BLE001 - any failure -> deterministic fallback
        log.warning("curriculum generation failed, using fallback: %s", exc)
        cur = fallback_curriculum(units, title)
        cur.description = "Auto-generated outline (the AI curriculum could not be generated)."
        return cur


def _course_language(db: Session, col: Collection, requested: str) -> str:
    if requested != "auto":
        return requested
    if col.kind == CollectionKind.docs.value:
        sample = " ".join(p.content[:2000] for p in col.pages[:5])
        return resolve_output_language("auto", detect_language(sample))
    langs = [v.language for v in col.videos if v.language]
    detected = max(set(langs), key=langs.count) if langs else "en"
    return resolve_output_language("auto", detected)


def build_course(course_id: str) -> None:
    """Background job: create the curriculum and lessons of a course."""
    with session_scope() as db:
        course = db.get(Course, course_id)
        if course is None:
            return
        col = course.collection
        course.status = Status.processing.value
        course.error = None
        units = collect_units(db, col)
        if not units:
            course.status = Status.failed.value
            course.error = "There is no processed content to learn from yet."
            return
        language = _course_language(db, col, course.language)
        level, title = course.level, col.title

    llm = LLMClient()
    cur = build_curriculum(llm, units, title=title, level=level, language=language)

    with session_scope() as db:
        course = db.get(Course, course_id)
        if course is None:
            return
        for old in list(course.lessons):
            db.delete(old)
        db.flush()
        course.title = cur.title or title
        course.description = cur.description
        course.outcomes = cur.outcomes
        course.language = language
        pos = 0
        for mi, m in enumerate(cur.modules):
            for lesson in m.lessons:
                db.add(Lesson(
                    course_id=course.id, position=pos, module_index=mi, module_title=m.title,
                    title=lesson.title, objectives=lesson.objectives, estimated_minutes=lesson.estimated_minutes,
                    source_refs=[units[s - 1].ref for s in lesson.sources],
                    status="available" if pos == 0 else "locked",
                ))
                pos += 1
        course.status = Status.completed.value
    # Warm up the first lesson so the learner can start immediately.
    from app.workers.queue import enqueue_lesson

    with session_scope() as db:
        first = db.scalar(select(Lesson.id).where(Lesson.course_id == course_id, Lesson.position == 0))
    if first:
        enqueue_lesson(first)


# ------------------------------------------------------------------ lessons
def _claim(lesson_id: str) -> bool:
    """Atomically take the generation lock (stale locks expire)."""
    with session_scope() as db:
        stale = now() - GENERATION_LOCK
        res = db.execute(
            update(Lesson)
            .where(Lesson.id == lesson_id)
            .where((Lesson.generating_since.is_(None)) | (Lesson.generating_since < stale))
            .values(generating_since=now())
        )
        return res.rowcount == 1


def _release(lesson_id: str) -> None:
    with session_scope() as db:
        db.execute(update(Lesson).where(Lesson.id == lesson_id).values(generating_since=None))


def is_generating(lesson: Lesson) -> bool:
    if lesson.generating_since is None:
        return False
    since = lesson.generating_since
    if since.tzinfo is None:
        since = since.replace(tzinfo=UTC)
    return since > now() - GENERATION_LOCK


def _assign_ids(quiz: list[QuizQuestion]) -> list[dict[str, Any]]:
    out = []
    for i, q in enumerate(quiz, 1):
        q.id = f"q{i}"
        out.append(q.model_dump())
    return out


def _fallback_quiz(content: LessonContent) -> list[QuizQuestion]:
    qs = []
    for i, kp in enumerate(content.key_points[:3], 1):
        qs.append(QuizQuestion(id=f"q{i}", type="true_false", question=kp, answer=True,
                               explanation="This is one of the key points of the lesson."))
    return qs


def generate_lesson(lesson_id: str, *, simpler: bool = False, force: bool = False) -> bool:
    """Generate (or regenerate) a lesson's content and quiz. Returns False if another worker is on it."""
    with session_scope() as db:
        lesson = db.get(Lesson, lesson_id)
        if lesson is None:
            return True
        if lesson.content and not force and not simpler:
            return True
    if not _claim(lesson_id):
        return False
    try:
        with session_scope() as db:
            lesson = db.get(Lesson, lesson_id)
            course = lesson.course
            sources = lesson_sources_text(db, lesson.source_refs or [])
            simplicity = lesson.simplicity + (1 if simpler else 0)
            level, language = course.level, course.language
            neighbours = db.scalars(
                select(Lesson.title).where(Lesson.course_id == course.id,
                                           Lesson.position.in_([lesson.position - 1, lesson.position + 1]))
                .order_by(Lesson.position)
            ).all()
            user = (
                f'Course: "{course.title}"\nModule: "{lesson.module_title}"\nLesson {lesson.position + 1}: '
                f'"{lesson.title}"\nObjectives: {"; ".join(lesson.objectives) or "-"}\n'
                f"Neighbouring lessons (do not teach them here): {'; '.join(neighbours) or '-'}\n\n"
                f"SOURCE MATERIAL:\n{sources or '(no source text available - teach from the title only)'}"
            )
        llm = LLMClient()
        content = llm.structured(lesson_system(level, language, simplicity), user, LessonContent, max_tokens=4096)
        if not content.explanation.strip():
            raise ValueError("the model returned an empty explanation")
        quiz = content.quiz or _fallback_quiz(content)
        data = content.model_dump(exclude={"quiz"})
        data["title"] = data.get("title") or ""
        with session_scope() as db:
            lesson = db.get(Lesson, lesson_id)
            lesson.content = data
            lesson.quiz = _assign_ids(quiz)
            lesson.simplicity = simplicity
            lesson.generating_since = None
            if lesson.status == "locked" and lesson.position == 0:
                lesson.status = "available"
        return True
    except Exception:
        _release(lesson_id)
        raise


def prefetch_lesson(lesson_id: str) -> None:
    """Best-effort background generation (errors are logged, the learner can retry)."""
    try:
        generate_lesson(lesson_id)
    except Exception as exc:  # noqa: BLE001
        log.warning("prefetch of lesson %s failed: %s", lesson_id, exc)


def new_quiz(lesson_id: str) -> None:
    with session_scope() as db:
        lesson = db.get(Lesson, lesson_id)
        course = lesson.course
        previous = [q.get("question", "") for q in (lesson.quiz or [])]
        sources = lesson_sources_text(db, lesson.source_refs or [])
        content = lesson.content or {}
        user = (
            f'Lesson: "{lesson.title}"\n\nLESSON:\n{content.get("explanation", "")}\n\n'
            f"Key points: {'; '.join(content.get('key_points', []))}\n\nSOURCE MATERIAL:\n{sources[:8000]}"
        )
        language = course.language
    out = LLMClient().structured(quiz_only_system(language, previous), user, QuizOnly, max_tokens=2500)
    if not out.quiz:
        raise ValueError("the model returned no questions")
    with session_scope() as db:
        lesson = db.get(Lesson, lesson_id)
        lesson.quiz = _assign_ids(out.quiz)


def public_quiz(quiz: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    """Questions without answers/explanations (sent before the learner submits)."""
    return [
        {k: q.get(k) for k in ("id", "type", "question", "options", "difficulty")}
        for q in quiz or []
    ]


# ----------------------------------------------------------------- grading
_WORD = re.compile(r"[\w؀-ۿ]{3,}")


def _keyword_score(reference: str, answer: str) -> float:
    ref = {w.lower() for w in _WORD.findall(reference)}
    ans = {w.lower() for w in _WORD.findall(answer)}
    if not ref or not ans:
        return 0.0
    overlap = len(ref & ans) / len(ref)
    return 1.0 if overlap >= 0.5 else 0.5 if overlap >= 0.25 else 0.0


def _display_answer(q: dict[str, Any]) -> str:
    if q["type"] == "mcq":
        opts = q.get("options") or []
        i = q.get("answer") if isinstance(q.get("answer"), int) else 0
        return opts[i] if 0 <= i < len(opts) else ""
    if q["type"] == "true_false":
        return "True" if q.get("answer") else "False"
    return str(q.get("answer") or "")


def grade(quiz: list[dict[str, Any]], answers: dict[str, Any], llm: LLMClient | None = None
          ) -> tuple[list[dict[str, Any]], float]:
    results: list[dict[str, Any]] = []
    open_items: list[tuple[dict[str, Any], str]] = []
    for q in quiz:
        given = answers.get(q["id"])
        r = {"id": q["id"], "type": q["type"], "question": q["question"], "your_answer": given,
             "correct_answer": _display_answer(q), "explanation": q.get("explanation", ""), "feedback": "",
             "score": 0.0}
        if q["type"] == "mcq":
            try:
                r["score"] = 1.0 if given is not None and int(given) == int(q["answer"]) else 0.0
            except (TypeError, ValueError):
                r["score"] = 0.0
            opts = q.get("options") or []
            if isinstance(given, int) and 0 <= given < len(opts):
                r["your_answer"] = opts[given]
        elif q["type"] == "true_false":
            g = given
            if isinstance(g, str):
                g = g.strip().lower() in {"true", "1", "yes"}
            r["score"] = 1.0 if g is not None and bool(g) == bool(q["answer"]) else 0.0
            r["your_answer"] = None if given is None else ("True" if g else "False")
        else:
            text = str(given or "").strip()
            r["your_answer"] = text
            if text:
                open_items.append((q, text))
        results.append(r)

    if open_items:
        scores: dict[str, tuple[float, str]] = {}
        try:
            llm = llm or LLMClient()
            body = "\n\n".join(
                f"id: {q['id']}\nQUESTION: {q['question']}\nREFERENCE: {q.get('answer', '')}\nSTUDENT: {text[:1500]}"
                for q, text in open_items
            )
            graded = llm.structured(GRADE_SYSTEM, body, GradeResult, max_tokens=1200)
            scores = {g.id: (g.score, g.feedback) for g in graded.items}
        except Exception as exc:  # noqa: BLE001 - fall back to keyword matching
            log.warning("LLM grading failed, using keyword overlap: %s", exc)
        for q, text in open_items:
            r = next(x for x in results if x["id"] == q["id"])
            if q["id"] in scores:
                r["score"], r["feedback"] = scores[q["id"]]
            else:
                r["score"] = _keyword_score(str(q.get("answer", "")), text)
                r["feedback"] = "Graded automatically by comparing with the model answer."

    for r in results:
        r["correct"] = r["score"] >= 0.99
    total = sum(r["score"] for r in results) / len(results) if results else 0.0
    return results, round(total, 3)


def submit(db: Session, lesson: Lesson, answers: dict[str, Any]) -> QuizAttempt:
    results, score = grade(lesson.quiz or [], answers)
    passed = score >= PASS_SCORE
    attempt = QuizAttempt(lesson_id=lesson.id, answers=answers, results=results, score=score, passed=passed)
    db.add(attempt)
    lesson.attempts += 1
    lesson.best_score = max(lesson.best_score or 0.0, score)
    if passed and lesson.status != "completed":
        lesson.status = "completed"
        lesson.completed_at = now()
    if passed:
        nxt = db.scalar(select(Lesson).where(Lesson.course_id == lesson.course_id,
                                             Lesson.position == lesson.position + 1))
        if nxt and nxt.status == "locked":
            nxt.status = "available"
    lesson.course.updated_at = now()
    db.commit()
    db.refresh(attempt)
    return attempt


# ------------------------------------------------------------------- tutor
def tutor_answer(db: Session, lesson: Lesson, question: str) -> tuple[str, LLMClient]:
    content = lesson.content or {}
    sources = lesson_sources_text(db, lesson.source_refs or [])
    user = (
        f'Lesson: "{lesson.title}"\n\nLESSON TEXT:\n{content.get("explanation", "")[:6000]}\n\n'
        f"SOURCE MATERIAL:\n{sources[:8000]}\n\nLEARNER QUESTION: {question}"
    )
    llm = LLMClient()
    r = llm.complete([{"role": "system", "content": TUTOR_SYSTEM}, {"role": "user", "content": user}],
                     max_tokens=900)
    return r.text.strip(), llm


# ------------------------------------------------------------------ stats
def course_progress(course: Course) -> dict[str, Any]:
    lessons = course.lessons
    done = [le for le in lessons if le.status == "completed"]
    scores = [le.best_score for le in lessons if le.best_score is not None]
    nxt = next((le for le in lessons if le.status != "completed"), None)
    return {
        "lesson_count": len(lessons),
        "completed_count": len(done),
        "progress": round(len(done) / len(lessons), 3) if lessons else 0.0,
        "average_score": round(sum(scores) / len(scores), 3) if scores else None,
        "xp": int(sum((le.best_score or 0) * 100 for le in done)),
        "next_lesson_id": nxt.id if nxt else None,
        "next_lesson_title": nxt.title if nxt else None,
        "minutes_total": sum(le.estimated_minutes for le in lessons),
    }
