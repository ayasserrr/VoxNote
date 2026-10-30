"""Retrieval over processed videos ("Ask your playlist").

The index is built from transcript windows (several consecutive segments,
~60-90 s of speech) plus each video's extracted concepts, ranked with BM25.
BM25 needs no embedding model and no GPU, works for Arabic and English after
light normalisation, and is plenty for a personal library. The retrieval layer
is isolated here so it can later be swapped for a vector store (pgvector,
Qdrant) without touching the API.
"""

from __future__ import annotations

import re
import threading
from dataclasses import dataclass

from rank_bm25 import BM25Okapi
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import Collection, DocPage, Transcript, Video
from app.services.chunking import fmt_ts
from app.services.llm import LLMClient
from app.services.prompts import ANSWER_SYSTEM

_TOKEN = re.compile(r"[\w؀-ۿ]+", re.UNICODE)
_STOP = set(
    "the a an and or of to in on for is are was were be it this that with as at by from what how why "
    "do does did can i you he she we they me my your our their about which who whom not no yes "
    "في من على الى إلى عن مع هو هي ده دي اللي ان أن إن كان كانت ما لا".split()
)


def normalize_ar(text: str) -> str:
    text = re.sub(r"[ً-ْـ]", "", text)  # diacritics + tatweel
    text = re.sub("[إأآا]", "ا", text)
    text = text.replace("ى", "ي").replace("ة", "ه")
    return text


def tokenize(text: str) -> list[str]:
    toks = []
    for t in _TOKEN.findall(normalize_ar(text.lower())):
        if t in _STOP or len(t) < 2:
            continue
        if t.startswith("ال") and len(t) > 4:
            t = t[2:]
        toks.append(t)
    return toks


@dataclass
class Passage:
    video_id: str  # video id, or page id for documentation pages
    collection_id: str
    video_title: str
    youtube_id: str | None
    start: float
    end: float
    text: str
    kind: str = "video"
    url: str | None = None


def page_passages(pages: list[DocPage], max_chars: int = 1400) -> list[Passage]:
    """Split documentation pages into heading-aware passages."""
    out: list[Passage] = []
    for p in pages:
        sections = re.split(r"\n(?=#{1,3} )", p.content)
        buf = ""
        for sec in sections:
            if buf and len(buf) + len(sec) > max_chars:
                out.append(Passage(p.id, p.collection_id, p.title, None, 0, 0, buf.strip(), "page", p.url))
                buf = ""
            buf += "\n" + sec
            while len(buf) > max_chars * 1.5:
                out.append(Passage(p.id, p.collection_id, p.title, None, 0, 0, buf[:max_chars].strip(), "page",
                                   p.url))
                buf = buf[max_chars:]
        if buf.strip():
            out.append(Passage(p.id, p.collection_id, p.title, None, 0, 0, buf.strip(), "page", p.url))
    return out


def build_passages(videos: list[Video], window_seconds: float = 75.0) -> list[Passage]:
    passages: list[Passage] = []
    for v in videos:
        tr: Transcript | None = v.transcript
        if tr is None:
            continue
        buf, start = [], None
        last_end = 0.0
        for seg in tr.segments:
            if start is None:
                start = seg.start
            buf.append(seg.text)
            last_end = seg.end
            if seg.end - start >= window_seconds:
                passages.append(Passage(v.id, v.collection_id, v.title, v.youtube_id, start, seg.end, " ".join(buf)))
                buf, start = [], None
        if buf and start is not None:
            passages.append(Passage(v.id, v.collection_id, v.title, v.youtube_id, start, last_end, " ".join(buf)))
        if v.knowledge and v.knowledge.data:
            for c in v.knowledge.data.get("concepts", []):
                text = f"{c.get('name', '')}: {c.get('definition', '')} {c.get('explanation', '')}".strip()
                if len(text) > 20:
                    s = float(c.get("start") or 0)
                    passages.append(Passage(v.id, v.collection_id, v.title, v.youtube_id, s,
                                            float(c.get("end") or s), text[:1500]))
    return passages


class _Index:
    def __init__(self, passages: list[Passage]):
        self.passages = passages
        corpus = [tokenize(p.text + " " + p.video_title) for p in passages]
        self.bm25 = BM25Okapi(corpus) if corpus else None

    def search(self, query: str, k: int) -> list[tuple[Passage, float]]:
        if not self.bm25:
            return []
        q = tokenize(query)
        if not q:
            return []
        scores = self.bm25.get_scores(q)
        ranked = sorted(zip(self.passages, scores, strict=False), key=lambda x: x[1], reverse=True)
        return [(p, float(s)) for p, s in ranked[:k] if s > 0]


_cache: dict[str, tuple[str, _Index]] = {}
_cache_lock = threading.Lock()


def _scope_videos(db: Session, user_id: str, collection_id: str | None, video_id: str | None) -> list[Video]:
    stmt = (
        select(Video)
        .join(Collection, Collection.id == Video.collection_id)
        .where(Collection.user_id == user_id)
        .options(selectinload(Video.transcript).selectinload(Transcript.segments), selectinload(Video.knowledge))
    )
    if collection_id:
        stmt = stmt.where(Video.collection_id == collection_id)
    if video_id:
        stmt = stmt.where(Video.id == video_id)
    return list(db.scalars(stmt))


def _scope_pages(db: Session, user_id: str, collection_id: str | None) -> list[DocPage]:
    stmt = (select(DocPage).join(Collection, Collection.id == DocPage.collection_id)
            .where(Collection.user_id == user_id))
    if collection_id:
        stmt = stmt.where(DocPage.collection_id == collection_id)
    return list(db.scalars(stmt))


def get_index(db: Session, user_id: str, collection_id: str | None = None, video_id: str | None = None) -> _Index:
    videos = _scope_videos(db, user_id, collection_id, video_id)
    pages = [] if video_id else _scope_pages(db, user_id, collection_id)
    version = "|".join(f"{v.id}:{v.updated_at.timestamp() if v.updated_at else 0}" for v in videos)
    version += "|" + ",".join(p.id for p in pages)
    key = f"{user_id}:{collection_id}:{video_id}"
    with _cache_lock:
        hit = _cache.get(key)
        if hit and hit[0] == version:
            return hit[1]
    idx = _Index(build_passages(videos) + page_passages(pages))
    with _cache_lock:
        _cache[key] = (version, idx)
    return idx


def search(db: Session, user_id: str, query: str, k: int = 10, collection_id: str | None = None,
           video_id: str | None = None) -> list[tuple[Passage, float]]:
    return get_index(db, user_id, collection_id, video_id).search(query, k)


def answer(db: Session, user_id: str, question: str, k: int = 8, collection_id: str | None = None,
           video_id: str | None = None, llm: LLMClient | None = None) -> tuple[str, list[Passage], LLMClient]:
    hits = search(db, user_id, question, k, collection_id, video_id)
    passages = [p for p, _ in hits]
    llm = llm or LLMClient()
    if not passages:
        return ("I couldn't find anything related to that question in the processed videos. "
                "Try different keywords or process more videos."), [], llm
    context = "\n\n".join(
        (f"[{i}] Documentation page: {p.video_title}\n{p.text[:1800]}" if p.kind == "page" else
         f"[{i}] Video: {p.video_title} @ {fmt_ts(p.start)}\n{p.text[:1800]}")
        for i, p in enumerate(passages, 1)
    )
    user = f"Question: {question}\n\nExcerpts:\n\n{context}"
    r = llm.complete([{"role": "system", "content": ANSWER_SYSTEM}, {"role": "user", "content": user}],
                     max_tokens=1500)
    return r.text.strip(), passages, llm
