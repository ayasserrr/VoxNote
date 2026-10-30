from app.schemas.learning import Curriculum, QuizQuestion
from app.services.learning import grade, sanitize_curriculum


def test_quiz_question_normalization():
    q = QuizQuestion.model_validate({"type": "multiple choice", "question": "?", "options": ["a", "b", "c"],
                                     "answer": "B"})
    assert q.type == "mcq" and q.answer == 1
    q = QuizQuestion.model_validate({"type": "tf", "question": "?", "answer": "false"})
    assert q.type == "true_false" and q.answer is False and q.options == ["True", "False"]
    q = QuizQuestion.model_validate({"type": "mcq", "question": "?", "options": ["only one"], "answer": "x"})
    assert q.type == "short"
    q = QuizQuestion.model_validate({"type": "mcq", "question": "?", "options": ["red", "blue"], "answer": "blue"})
    assert q.answer == 1


def test_grade_mixed_quiz_with_keyword_fallback(monkeypatch):
    quiz = [
        {"id": "q1", "type": "mcq", "question": "?", "options": ["a", "b"], "answer": 1},
        {"id": "q2", "type": "true_false", "question": "?", "options": ["True", "False"], "answer": False},
        {"id": "q3", "type": "short", "question": "What does pip do?", "options": [],
         "answer": "pip installs Python packages from PyPI"},
    ]

    class Broken:
        def structured(self, *a, **k):
            raise RuntimeError("no llm")

    results, score = grade(quiz, {"q1": 1, "q2": "false", "q3": "pip installs packages from PyPI"}, llm=Broken())
    assert [r["correct"] for r in results] == [True, True, True]
    assert score == 1.0
    results, score = grade(quiz, {"q1": 0}, llm=Broken())
    assert score == 0.0 and results[0]["correct_answer"] == "b"


def test_sanitize_curriculum_fixes_sources():
    cur = Curriculum.model_validate({"modules": [
        {"title": "M1", "lessons": [{"title": "L1", "sources": [1, 99]}, {"title": "", "sources": [2]},
                                    {"title": "L3", "sources": []}]},
        {"title": "Empty", "lessons": []},
    ]})
    out = sanitize_curriculum(cur, 3, "T")
    assert len(out.modules) == 1
    lessons = out.modules[0].lessons
    assert [le.title for le in lessons] == ["L1"]
    assert sorted(lessons[0].sources) == [1, 2, 3]  # unused sources attached
    assert out.title == "T"


def test_docs_to_course_to_quiz_flow(auth_client):
    c = auth_client
    r = c.post("/api/collections/docs", json={"url": "https://minilib.dev/docs/", "max_pages": 10})
    assert r.status_code == 201, r.text
    col = c.get(f"/api/collections/{r.json()['id']}").json()
    assert col["kind"] == "docs" and col["status"] == "completed", col
    assert col["page_count"] == 6 and col["course_id"]
    page = c.get(f"/api/collections/{col['id']}/pages/{col['pages'][1]['id']}").json()
    assert "pip install minilib" in page["content"]

    course = c.get(f"/api/courses/{col['course_id']}").json()
    assert course["status"] == "completed" and course["lessons"]
    first, second = course["lessons"][0], course["lessons"][1]
    assert first["status"] == "available" and second["status"] == "locked"

    lesson = c.post(f"/api/lessons/{first['id']}/prepare").json()
    assert lesson["content"]["explanation"] and lesson["quiz"]
    assert all("answer" not in q for q in lesson["quiz"])  # answers are never leaked
    assert lesson["sources"][0]["url"].startswith("https://minilib.dev/docs")

    # Wrong answers -> not passed, next lesson stays locked
    bad = c.post(f"/api/lessons/{first['id']}/submit", json={"answers": {}}).json()
    assert bad["attempt"]["passed"] is False
    assert c.get(f"/api/lessons/{second['id']}").json()["status"] == "locked"

    # Correct answers (mock quiz: q1 -> 0, q2 -> true, q3 -> reference sentence)
    ref = bad["attempt"]["results"][2]["correct_answer"]
    good = c.post(f"/api/lessons/{first['id']}/submit",
                  json={"answers": {"q1": 0, "q2": True, "q3": ref}}).json()
    assert good["attempt"]["passed"] is True and good["attempt"]["score"] == 1.0
    assert good["lesson"]["status"] == "completed"
    assert c.get(f"/api/lessons/{second['id']}").json()["status"] == "available"

    simpler = c.post(f"/api/lessons/{first['id']}/simplify").json()
    assert simpler["simplicity"] == 1
    newq = c.post(f"/api/lessons/{first['id']}/new-quiz").json()
    assert newq["quiz"]
    tutor = c.post(f"/api/lessons/{first['id']}/tutor", json={"question": "What is MiniLib?"}).json()
    assert tutor["answer"]

    ask = c.post("/api/ask", json={"question": "How do I install minilib?", "collection_id": col["id"]}).json()
    assert ask["sources"][0]["kind"] == "page" and ask["sources"][0]["url"].startswith("https://minilib.dev")

    dash = c.get("/api/dashboard").json()
    assert dash["courses"] == 1 and dash["lessons_completed"] == 1 and dash["pages_read"] == 6
    assert dash["xp"] == 100 and dash["quizzes_taken"] == 2

    reset = c.post(f"/api/courses/{course['id']}/reset").json()
    assert reset["stats"]["completed_count"] == 0


def test_course_from_video(auth_client):
    c = auth_client
    r = c.post("/api/collections", json={"url": "https://youtu.be/ENvideo0001"})
    cid = r.json()["id"]
    course = c.post(f"/api/collections/{cid}/course", json={"level": "beginner", "language": "en"})
    assert course.status_code == 201, course.text
    course = c.get(f"/api/courses/{course.json()['id']}").json()
    assert course["status"] == "completed" and course["lessons"]
    lesson = c.post(f"/api/lessons/{course['lessons'][0]['id']}/prepare").json()
    assert lesson["sources"][0]["kind"] == "video" and "youtube.com" in lesson["sources"][0]["url"]
    regular = [le for le in course["lessons"] if le["kind"] == "lesson"]
    assert c.get("/api/courses").json()[0]["stats"]["lesson_count"] == len(regular)
    assert course["lessons"][-1]["kind"] == "exam"


def test_docs_rejects_youtube_and_bad_urls(auth_client):
    assert auth_client.post("/api/collections/docs", json={"url": "https://youtu.be/ENvideo0001"}).status_code == 400
    assert auth_client.post("/api/collections/docs", json={"url": "notaurl"}).status_code == 400


def _docs_course(c):
    r = c.post("/api/collections/docs", json={"url": "https://minilib.dev/docs/", "max_pages": 3})
    col = c.get(f"/api/collections/{r.json()['id']}").json()
    return c.get(f"/api/courses/{col['course_id']}").json()


def test_mistakes_go_to_spaced_repetition_review(auth_client):
    c = auth_client
    course = _docs_course(c)
    first = course["lessons"][0]
    c.post(f"/api/lessons/{first['id']}/prepare")
    c.post(f"/api/lessons/{first['id']}/submit", json={"answers": {"q1": 3, "q2": False}})  # all wrong
    q = c.get("/api/review").json()
    assert q["due"] == 3 and len(q["cards"]) == 3
    assert all("answer" not in card["question"] for card in q["cards"])
    tf = next(card for card in q["cards"] if card["question"]["type"] == "true_false")
    res = c.post(f"/api/review/{tf['id']}/answer", json={"answer": True}).json()
    assert res["result"]["correct"] and res["box"] == 1 and not res["mastered"]
    mcq = next(card for card in q["cards"] if card["question"]["type"] == "mcq")
    res = c.post(f"/api/review/{mcq['id']}/answer", json={"answer": 2}).json()
    assert not res["result"]["correct"] and res["box"] == 0 and res["result"]["correct_answer"]
    q2 = c.get("/api/review").json()
    assert q2["due"] == 1 and q2["upcoming"] == 2  # answered cards are scheduled for later
    dash = c.get("/api/dashboard").json()
    assert dash["due_reviews"] == 1 and dash["streak_days"] == 1


def test_final_exam_certifies_course_and_notes(auth_client):
    c = auth_client
    course = _docs_course(c)
    lessons = [le for le in course["lessons"] if le["kind"] == "lesson"]
    exam = course["lessons"][-1]
    assert exam["kind"] == "exam" and exam["status"] == "locked"
    assert course["stats"]["lesson_count"] == len(lessons) and course["stats"]["exam_status"] == "locked"

    saved = c.put(f"/api/lessons/{lessons[0]['id']}/notes", json={"notes": "pip install minilib"}).json()
    assert saved["id"] == lessons[0]["id"]
    assert c.get(f"/api/lessons/{lessons[0]['id']}").json()["notes"] == "pip install minilib"

    for le in lessons:
        lesson = c.post(f"/api/lessons/{le['id']}/prepare").json()
        ref = next(q for q in lesson["quiz"] if q["type"] == "short")
        first = c.post(f"/api/lessons/{le['id']}/submit", json={"answers": {}}).json()
        model = next(r for r in first["attempt"]["results"] if r["id"] == ref["id"])["correct_answer"]
        assert c.post(f"/api/lessons/{le['id']}/submit",
                      json={"answers": {"q1": 0, "q2": True, "q3": model}}).json()["attempt"]["passed"]

    exam_lesson = c.post(f"/api/lessons/{exam['id']}/prepare").json()
    assert exam_lesson["status"] == "available" and exam_lesson["kind"] == "exam"
    assert exam_lesson["content"]["explanation"] and exam_lesson["quiz"]
    first = c.post(f"/api/lessons/{exam['id']}/submit", json={"answers": {}}).json()
    model = first["attempt"]["results"][2]["correct_answer"]
    done = c.post(f"/api/lessons/{exam['id']}/submit", json={"answers": {"q1": 0, "q2": True, "q3": model}}).json()
    assert done["attempt"]["passed"] and done["course_completed"]
    stats = c.get(f"/api/courses/{course['id']}").json()["stats"]
    assert stats["certified"] and stats["completed_count"] == stats["lesson_count"] and stats["certified_at"]
    assert c.get("/api/dashboard").json()["certificates"] == 1
