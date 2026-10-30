"""Learning Hub API: courses, lessons, quizzes, tutor and dashboard."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.config import settings
from app.db import get_db
from app.deps import get_current_user, get_owned_collection
from app.models import (
    Collection,
    CollectionKind,
    Course,
    DocPage,
    Document,
    Lesson,
    QuizAttempt,
    Status,
    User,
    Video,
)
from app.schemas.api import (
    AttemptOut,
    CollectionSummary,
    CourseOut,
    CourseProgress,
    CourseSummary,
    DashboardOut,
    LessonOut,
    LessonSource,
    LessonSummary,
    SubmitOut,
    TutorOut,
)
from app.schemas.learning import CourseCreate, SubmitAnswers, TutorQuestion
from app.services import learning
from app.services.llm import LLMError
from app.workers.queue import enqueue_course, enqueue_lesson

router = APIRouter(tags=["learning"])


# ----------------------------------------------------------------- helpers
def _owned_course(course_id: str, user: User, db: Session) -> Course:
    course = db.get(Course, course_id)
    if not course or course.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Course not found")
    return course


def _owned_lesson(lesson_id: str, user: User, db: Session) -> Lesson:
    lesson = db.get(Lesson, lesson_id)
    if not lesson or lesson.course.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Lesson not found")
    return lesson


def _lesson_summary(le: Lesson) -> LessonSummary:
    s = LessonSummary.model_validate(le, from_attributes=True)
    return s.model_copy(update={"has_content": bool(le.content)})


def _course_summary(c: Course) -> CourseSummary:
    col = c.collection
    s = CourseSummary.model_validate(c, from_attributes=True)
    return s.model_copy(update={
        "collection_kind": col.kind, "source_url": col.source_url, "thumbnail_url": col.thumbnail_url,
        "stats": CourseProgress(**learning.course_progress(c)),
    })


def _course_out(c: Course) -> CourseOut:
    base = _course_summary(c).model_dump()
    return CourseOut(**base, outcomes=c.outcomes or [], lessons=[_lesson_summary(le) for le in c.lessons])


def _sources(refs: list[dict]) -> list[LessonSource]:
    out = []
    for r in refs or []:
        out.append(LessonSource(kind=r.get("kind", "page"), title=r.get("title", ""), url=r.get("url"),
                                page_id=r.get("page_id"), video_id=r.get("video_id"),
                                youtube_id=r.get("youtube_id"), start=r.get("start"), end=r.get("end")))
        if r.get("kind") == "video" and r.get("youtube_id"):
            out[-1].url = f"https://www.youtube.com/watch?v={r['youtube_id']}&t={int(r.get('start') or 0)}s"
    return out


def _lesson_out(db: Session, le: Lesson) -> LessonOut:
    course = le.course
    neighbours = {
        p: i for p, i in db.execute(
            select(Lesson.position, Lesson.id).where(Lesson.course_id == course.id,
                                                     Lesson.position.in_([le.position - 1, le.position + 1]))
        ).all()
    }
    last = le.quiz_attempts[-1] if le.quiz_attempts else None
    return LessonOut(
        **_lesson_summary(le).model_dump(),
        course_id=course.id,
        course_title=course.title,
        language=course.language,
        content=le.content,
        quiz=learning.public_quiz(le.quiz),
        sources=_sources(le.source_refs),
        generating=learning.is_generating(le),
        simplicity=le.simplicity,
        prev_lesson_id=neighbours.get(le.position - 1),
        next_lesson_id=neighbours.get(le.position + 1),
        last_attempt=AttemptOut.model_validate(last, from_attributes=True) if last else None,
        pass_score=settings.quiz_pass_score,
    )


async def _generate(lesson_id: str, **kw) -> bool:
    try:
        return await run_in_threadpool(learning.generate_lesson, lesson_id, **kw)
    except LLMError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"The AI could not prepare this lesson: {exc}") from exc


# ----------------------------------------------------------------- courses
@router.post("/collections/{collection_id}/course", response_model=CourseOut, status_code=201)
def create_course(collection_id: str, body: CourseCreate, user: User = Depends(get_current_user),
                  db: Session = Depends(get_db)) -> CourseOut:
    """Create (or rebuild) the interactive course for a collection."""
    col = get_owned_collection(collection_id, user, db)
    if col.kind == CollectionKind.docs.value:
        if not col.pages:
            raise HTTPException(status.HTTP_409_CONFLICT, "The documentation has not been crawled yet")
    elif not any(v.status == Status.completed.value for v in col.videos):
        raise HTTPException(status.HTTP_409_CONFLICT, "Wait until at least one video has been processed")
    course = col.course
    if course and course.status in (Status.queued.value, Status.processing.value):
        raise HTTPException(status.HTTP_409_CONFLICT, "The course is already being built")
    if course is None:
        course = Course(collection_id=col.id, user_id=user.id, title=col.title)
        db.add(course)
    course.level, course.language = body.level, body.language
    course.status, course.error = Status.queued.value, None
    db.commit()
    enqueue_course(course.id)
    db.refresh(course)
    return _course_out(course)


@router.get("/courses", response_model=list[CourseSummary])
def list_courses(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    courses = db.scalars(
        select(Course).where(Course.user_id == user.id)
        .options(selectinload(Course.lessons), selectinload(Course.collection))
        .order_by(func.coalesce(Course.last_opened_at, Course.created_at).desc())
    ).all()
    return [_course_summary(c) for c in courses]


@router.get("/courses/{course_id}", response_model=CourseOut)
def get_course(course_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _course_out(_owned_course(course_id, user, db))


@router.delete("/courses/{course_id}", status_code=204)
def delete_course(course_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    db.delete(_owned_course(course_id, user, db))
    db.commit()


@router.post("/courses/{course_id}/reset", response_model=CourseOut)
def reset_progress(course_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    course = _owned_course(course_id, user, db)
    for le in course.lessons:
        le.status = "available" if le.position == 0 else "locked"
        le.best_score, le.attempts, le.completed_at = None, 0, None
        for a in list(le.quiz_attempts):
            db.delete(a)
    db.commit()
    db.refresh(course)
    return _course_out(course)


# ----------------------------------------------------------------- lessons
@router.get("/lessons/{lesson_id}", response_model=LessonOut)
def get_lesson(lesson_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    le = _owned_lesson(lesson_id, user, db)
    le.course.last_opened_at = learning.now()
    db.commit()
    return _lesson_out(db, le)


@router.post("/lessons/{lesson_id}/prepare", response_model=LessonOut)
async def prepare_lesson(lesson_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Generate the lesson if needed (synchronously), then prefetch the next one."""
    le = _owned_lesson(lesson_id, user, db)
    if not le.content:
        await _generate(lesson_id)
    db.expire_all()
    le = _owned_lesson(lesson_id, user, db)
    nxt = db.scalar(select(Lesson).where(Lesson.course_id == le.course_id, Lesson.position == le.position + 1))
    if le.content and nxt is not None and not nxt.content and not learning.is_generating(nxt):
        enqueue_lesson(nxt.id)
    return _lesson_out(db, le)


@router.post("/lessons/{lesson_id}/simplify", response_model=LessonOut)
async def simplify_lesson(lesson_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Re-explain the lesson more simply (and with a fresh quiz)."""
    _owned_lesson(lesson_id, user, db)
    ok = await _generate(lesson_id, simpler=True)
    if not ok:
        raise HTTPException(status.HTTP_409_CONFLICT, "This lesson is already being prepared, try again shortly")
    db.expire_all()
    return _lesson_out(db, _owned_lesson(lesson_id, user, db))


@router.post("/lessons/{lesson_id}/regenerate", response_model=LessonOut)
async def regenerate_lesson(lesson_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _owned_lesson(lesson_id, user, db)
    ok = await _generate(lesson_id, force=True)
    if not ok:
        raise HTTPException(status.HTTP_409_CONFLICT, "This lesson is already being prepared, try again shortly")
    db.expire_all()
    return _lesson_out(db, _owned_lesson(lesson_id, user, db))


@router.post("/lessons/{lesson_id}/new-quiz", response_model=LessonOut)
async def new_quiz(lesson_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    le = _owned_lesson(lesson_id, user, db)
    if not le.content:
        raise HTTPException(status.HTTP_409_CONFLICT, "Open the lesson first")
    try:
        await run_in_threadpool(learning.new_quiz, lesson_id)
    except LLMError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc
    db.expire_all()
    return _lesson_out(db, _owned_lesson(lesson_id, user, db))


@router.post("/lessons/{lesson_id}/submit", response_model=SubmitOut)
async def submit_quiz(lesson_id: str, body: SubmitAnswers, user: User = Depends(get_current_user),
                      db: Session = Depends(get_db)) -> SubmitOut:
    le = _owned_lesson(lesson_id, user, db)
    if not le.quiz:
        raise HTTPException(status.HTTP_409_CONFLICT, "This lesson has no quiz yet")
    attempt = await run_in_threadpool(learning.submit, db, le, body.answers)
    db.refresh(le)
    course = le.course
    nxt = db.scalar(select(Lesson.id).where(Lesson.course_id == course.id, Lesson.position == le.position + 1))
    if attempt.passed and nxt:
        enqueue_lesson(nxt)
    return SubmitOut(
        attempt=AttemptOut.model_validate(attempt, from_attributes=True),
        lesson=_lesson_summary(le),
        next_lesson_id=nxt,
        course_completed=all(x.status == "completed" for x in course.lessons),
    )


@router.post("/lessons/{lesson_id}/tutor", response_model=TutorOut)
async def tutor(lesson_id: str, body: TutorQuestion, user: User = Depends(get_current_user),
                db: Session = Depends(get_db)) -> TutorOut:
    le = _owned_lesson(lesson_id, user, db)
    try:
        answer, llm = await run_in_threadpool(learning.tutor_answer, db, le, body.question)
    except LLMError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc
    return TutorOut(answer=answer, provider=llm.usage.last_provider, model=llm.usage.last_model)


# --------------------------------------------------------------- dashboard
@router.get("/dashboard", response_model=DashboardOut)
def dashboard(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> DashboardOut:
    from app.api.collections import summary_fields

    cols = db.scalars(
        select(Collection).where(Collection.user_id == user.id)
        .options(selectinload(Collection.videos), selectinload(Collection.pages), selectinload(Collection.course))
        .order_by(Collection.created_at.desc())
    ).all()
    courses = db.scalars(
        select(Course).where(Course.user_id == user.id)
        .options(selectinload(Course.lessons), selectinload(Course.collection))
        .order_by(func.coalesce(Course.last_opened_at, Course.created_at).desc())
    ).all()
    lessons = [le for c in courses for le in c.lessons]
    done = [le for le in lessons if le.status == "completed"]
    scores = [le.best_score for le in lessons if le.best_score is not None]
    quizzes = db.scalar(
        select(func.count(QuizAttempt.id)).join(Lesson).join(Course).where(Course.user_id == user.id)) or 0
    col_ids = [c.id for c in cols]
    docs = db.scalar(select(func.count(Document.id)).where(Document.collection_id.in_(col_ids))) if col_ids else 0
    videos_done = db.scalar(select(func.count(Video.id)).where(
        Video.collection_id.in_(col_ids), Video.status == Status.completed.value)) if col_ids else 0
    pages = db.scalar(select(func.count(DocPage.id)).where(DocPage.collection_id.in_(col_ids))) if col_ids else 0
    in_progress = [c for c in courses if c.status == Status.completed.value
                   and any(le.status != "completed" for le in c.lessons)]
    return DashboardOut(
        collections=len(cols),
        videos_processed=videos_done or 0,
        pages_read=pages or 0,
        documents=docs or 0,
        courses=len(courses),
        lessons_completed=len(done),
        quizzes_taken=quizzes,
        average_score=round(sum(scores) / len(scores), 3) if scores else None,
        xp=int(sum((le.best_score or 0) * 100 for le in done)),
        continue_learning=[_course_summary(c) for c in (in_progress or courses)[:4]],
        recent=[CollectionSummary.model_validate(c, from_attributes=True).model_copy(update=summary_fields(c))
                for c in cols[:6]],
    )
