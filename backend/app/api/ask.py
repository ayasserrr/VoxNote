"""Ask Your Playlist (RAG) and keyword search across the library."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user, get_owned_collection, get_owned_video
from app.models import User
from app.schemas.api import AskIn, AskOut, SearchHit, SourceRef
from app.services import search as search_svc
from app.services.llm import LLMError
from app.services.youtube import video_url

router = APIRouter(tags=["ask"])


def _ref(i: int, p: search_svc.Passage) -> SourceRef:
    return SourceRef(ref=i, video_id=p.video_id, video_title=p.video_title, youtube_id=p.youtube_id,
                     start=p.start, end=p.end, text=p.text[:600],
                     url=video_url(p.youtube_id, p.start) if p.youtube_id else None)


@router.post("/ask", response_model=AskOut)
async def ask(body: AskIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> AskOut:
    if body.collection_id:
        get_owned_collection(body.collection_id, user, db)
    if body.video_id:
        get_owned_video(body.video_id, user, db)
    try:
        answer, passages, llm = await run_in_threadpool(
            search_svc.answer, db, user.id, body.question, body.top_k, body.collection_id, body.video_id)
    except LLMError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc
    return AskOut(answer=answer, sources=[_ref(i, p) for i, p in enumerate(passages, 1)],
                  provider=llm.usage.last_provider, model=llm.usage.last_model)


@router.get("/search", response_model=list[SearchHit])
def search(q: str = Query(min_length=2), collection_id: str | None = None, limit: int = Query(20, le=50),
           user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[SearchHit]:
    if collection_id:
        get_owned_collection(collection_id, user, db)
    hits = search_svc.search(db, user.id, q, limit, collection_id)
    return [SearchHit(**_ref(i, p).model_dump(), score=round(s, 3), collection_id=p.collection_id)
            for i, (p, s) in enumerate(hits, 1)]
