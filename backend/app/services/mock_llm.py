"""Deterministic, offline stand-in for an LLM (LLM_PROVIDERS=mock).

It lets you run the whole pipeline - and the test-suite - without any API key.
The output is extractive (sentences copied from the transcript), so documents
look plausible but are obviously not as good as a real model's.
"""

from __future__ import annotations

import json
import re
from collections import Counter

_TS_LINE = re.compile(r"^\[(\d+):(\d{2})(?::(\d{2}))?\]\s*(.*)$")
_WORD = re.compile(r"[A-Za-z؀-ۿ][A-Za-z؀-ۿ\-]{3,}")
_STOP = set(
    "this that with from have will your what when then there they them their about which would could "
    "should these those into just like also some more very really because where here been being were "
    "okay right going thing things know want need make made does doing done video today let's".split()
)


def _lines(text: str) -> list[tuple[float, str]]:
    out = []
    for raw in text.splitlines():
        m = _TS_LINE.match(raw.strip())
        if not m:
            continue
        a, b, c, body = m.groups()
        secs = int(a) * 3600 + int(b) * 60 + int(c) if c else int(a) * 60 + int(b)
        out.append((float(secs), body))
    return out


def _keywords(text: str, n: int) -> list[str]:
    words = [w.lower() for w in _WORD.findall(text) if w.lower() not in _STOP]
    return [w for w, _ in Counter(words).most_common(n)]


def _chunk(user: str) -> dict:
    lines = _lines(user)
    body = " ".join(t for _, t in lines)
    kws = _keywords(body, 6)
    start = lines[0][0] if lines else 0
    end = lines[-1][0] if lines else 0
    sentences = [t for _, t in lines]

    def first_with(word: str) -> tuple[float, str]:
        for ts, t in lines:
            if word in t.lower():
                return ts, t
        return start, sentences[0] if sentences else ""

    concepts = []
    for kw in kws[:4]:
        ts, sent = first_with(kw)
        concepts.append(
            {
                "name": kw.title(),
                "definition": sent,
                "explanation": " ".join(t for _, t in lines if kw in t.lower())[:600],
                "instructor_points": [t for _, t in lines if kw in t.lower()][:3],
                "examples": [],
                "related": [k.title() for k in kws if k != kw][:3],
                "start": ts,
                "end": end,
            }
        )
    code_lines = [(ts, t) for ts, t in lines if re.search(r"\w+\(.*\)|=|import |SELECT ", t)]
    return {
        "section_title": " / ".join(k.title() for k in kws[:2]) or "Section",
        "summary": " ".join(sentences[:4])[:800],
        "concepts": concepts,
        "technical": [
            {"kind": "code", "title": "Mentioned code", "content": t, "language": "", "start": ts}
            for ts, t in code_lines[:2]
        ],
        "examples": [
            {"title": "Example", "description": t, "start": ts}
            for ts, t in lines
            if "example" in t.lower() or "مثال" in t
        ][:3],
        "key_points": [{"text": t, "start": ts} for ts, t in lines[:: max(len(lines) // 4, 1)]][:5],
        "glossary": [{"term": k.title(), "definition": first_with(k)[1][:200], "translation": ""} for k in kws[:3]],
        "questions": [
            {"question": f"What does the speaker say about {k}?", "answer": first_with(k)[1], "difficulty": "easy"}
            for k in kws[:2]
        ],
    }


def _video(user: str) -> dict:
    kws = _keywords(user, 8)
    paras = [p.strip() for p in user.split("\n") if len(p.strip()) > 40][:4]
    return {
        "title": "",
        "overview": "\n\n".join(paras) or "Overview not available.",
        "learning_objectives": [f"Explain {k}" for k in kws[:4]],
        "takeaways": [f"{k.title()} is a central topic of this video." for k in kws[:5]],
        "prerequisites": [],
    }


def _collection(user: str) -> dict:
    kws = _keywords(user, 10)
    videos = sorted({int(n) for n in re.findall(r"VIDEO (\d+)", user)}) or [1]
    return {
        "course_title": "",
        "course_summary": "This collection covers: " + ", ".join(kws) + ".",
        "concepts": [{"name": k.title(), "description": "", "videos": videos[:3]} for k in kws[:6]],
        "concept_map": [{"source": kws[i].title(), "target": kws[i + 1].title(), "relation": "related to"}
                        for i in range(min(len(kws) - 1, 4))],
        "recurring_concepts": [k.title() for k in kws[:3]],
        "learning_path": [{"step": f"Watch video {v}", "goal": "", "videos": [v]} for v in videos],
        "glossary": [{"term": k.title(), "definition": "", "translation": ""} for k in kws[:5]],
        "final_questions": [
            {"question": f"How is {kws[0]} used across the course?", "answer": "", "difficulty": "medium"}
        ] if kws else [],
    }


def _answer(user: str) -> str:
    refs = re.findall(r"^\[(\d+)\][^\n]*\n(.*)$", user, flags=re.MULTILINE)
    if not refs:
        return "I could not find relevant information in your library."
    bullets = "\n".join(f"- {text.strip()[:240]} [{n}]" for n, text in refs[:4])
    return "Based on your videos (offline mock model):\n\n" + bullets


def _sentences(text: str) -> list[str]:
    text = re.sub(r"```.*?```", " ", text, flags=re.S)
    parts = re.split(r"(?<=[.!?؟])\s+", re.sub(r"\s+", " ", re.sub(r"^#+ .*$", "", text, flags=re.M)))
    return [p.strip() for p in parts if 30 <= len(p.strip()) <= 260]


def _curriculum(user: str) -> dict:
    items = re.findall(r"^\[(\d+)\]\s*(.+)$", user, flags=re.M)
    modules, per = [], 3
    for m in range(0, len(items), per):
        chunk = items[m: m + per]
        modules.append({
            "title": f"Module {m // per + 1}: {chunk[0][1][:50]}",
            "summary": "",
            "lessons": [{"title": t.split(" [")[0][:80], "objectives": [f"Understand {t.split(' [')[0][:50]}"],
                         "sources": [int(n)], "estimated_minutes": 8} for n, t in chunk],
        })
    title = re.search(r'material: "([^"]+)"', user)
    return {"title": title.group(1) if title else "Course", "description": "A step-by-step course (mock).",
            "outcomes": ["Understand the main ideas"], "modules": modules}


def _lesson(user: str) -> dict:
    src = user.split("SOURCE MATERIAL:", 1)[-1]
    sents = _sentences(src) or ["This lesson explains the topic step by step using the documentation."]
    code = re.search(r"```(\w*)\n(.*?)```", src, flags=re.S)
    title = re.search(r'Lesson \d+: "([^"]+)"', user)
    t = title.group(1) if title else "Lesson"
    expl = f"### Why it matters\n\n{sents[0]}\n\n### How it works\n\n" + "\n\n".join(sents[1:5])
    if code:
        expl += f"\n\n```{code.group(1)}\n{code.group(2).strip()}\n```"
    distractors = ["It is only used for styling web pages.", "It requires a paid license to use.",
                   "It replaces the operating system."]
    quiz = [
        {"id": "q1", "type": "mcq", "question": f"Which statement about {t} is correct?",
         "options": [sents[0][:160]] + distractors, "answer": 0,
         "explanation": "This is stated in the lesson.", "difficulty": "easy"},
        {"id": "q2", "type": "true_false", "question": sents[min(1, len(sents) - 1)][:200], "answer": True,
         "explanation": "The lesson states this.", "difficulty": "easy"},
        {"id": "q3", "type": "short", "question": f"In your own words, what is {t} about?",
         "answer": sents[0], "explanation": "See the first section of the lesson.", "difficulty": "medium"},
    ]
    return {"title": t, "summary": sents[0][:200], "explanation": expl,
            "analogy": f"Think of {t} like a recipe: follow the steps in order and you get a predictable result.",
            "key_points": [s[:160] for s in sents[:4]],
            "example": {"title": "Example", "content": f"```{code.group(1)}\n{code.group(2).strip()}\n```"
                        if code else sents[-1]},
            "common_mistakes": ["Skipping the setup steps."], "quiz": quiz}


def _grade(user: str) -> dict:
    items = []
    for block in user.split("\n\n"):
        qid = re.search(r"id: (\S+)", block)
        ref = re.search(r"REFERENCE: (.*)", block)
        ans = re.search(r"STUDENT: (.*)", block, flags=re.S)
        if not qid:
            continue
        rw = set(re.findall(r"\w{4,}", (ref.group(1) if ref else "").lower()))
        aw = set(re.findall(r"\w{4,}", (ans.group(1) if ans else "").lower()))
        overlap = len(rw & aw) / len(rw) if rw else 0
        score = 1 if overlap >= 0.4 else 0.5 if overlap >= 0.15 else 0
        items.append({"id": qid.group(1), "score": score,
                      "feedback": "Good answer!" if score == 1 else "Partly right — review the key idea."
                      if score else "Not quite. Re-read the lesson's first section."})
    return {"items": items}


def mock_complete(messages: list[dict[str, str]], json_mode: bool) -> str:
    system = messages[0]["content"] if messages else ""
    user = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
    if "TASK: CHUNK_EXTRACTION" in system:
        return json.dumps(_chunk(user), ensure_ascii=False)
    if "TASK: VIDEO_SYNTHESIS" in system:
        return json.dumps(_video(user), ensure_ascii=False)
    if "TASK: COLLECTION_SYNTHESIS" in system:
        return json.dumps(_collection(user), ensure_ascii=False)
    if "TASK: CURRICULUM" in system:
        return json.dumps(_curriculum(user), ensure_ascii=False)
    if "TASK: EXAM" in system:
        out = _lesson(user)
        out["title"] = "Final exam"
        return json.dumps(out, ensure_ascii=False)
    if "TASK: LESSON" in system:
        return json.dumps(_lesson(user), ensure_ascii=False)
    if "TASK: QUIZ" in system:
        return json.dumps({"quiz": _lesson(user)["quiz"][::-1]}, ensure_ascii=False)
    if "TASK: GRADE" in system:
        return json.dumps(_grade(user), ensure_ascii=False)
    if "TASK: TUTOR" in system:
        q = user.rsplit("LEARNER QUESTION:", 1)[-1].strip()
        return f"Great question! (offline mock tutor)\n\n**{q}** — re-read the key points of this lesson."
    if "TASK: ANSWER" in system:
        return _answer(user)
    return json.dumps({}) if json_mode else ""
