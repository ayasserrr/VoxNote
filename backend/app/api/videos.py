from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user, get_owned_video
from app.models import Document, Stage, Status, User
from app.schemas.api import DocumentOut, TranscriptOut, VideoDetailOut, VideoOut
from app.workers.queue import enqueue_video

router = APIRouter(prefix="/videos", tags=["videos"])


@router.get("/{video_id}", response_model=VideoDetailOut)
def get_video(video_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    v = get_owned_video(video_id, user, db)
    docs = db.scalars(select(Document).where(Document.video_id == v.id)).all()
    base = VideoOut.model_validate(v, from_attributes=True).model_dump()
    k = v.knowledge
    return VideoDetailOut(**base, **{
        "collection_id": v.collection_id,
        "description": v.description,
        "knowledge": k.data if k else None,
        "quality": k.quality if k else None,
        "llm_provider": k.llm_provider if k else None,
        "llm_model": k.llm_model if k else None,
        "documents": [DocumentOut.model_validate(d, from_attributes=True) for d in docs],
    })


@router.get("/{video_id}/transcript", response_model=TranscriptOut)
def get_transcript(video_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    v = get_owned_video(video_id, user, db)
    if not v.transcript:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Transcript not available yet")
    return v.transcript


@router.post("/{video_id}/retry", response_model=VideoDetailOut)
def retry_video(video_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Retry a single video without touching the rest of the playlist."""
    v = get_owned_video(video_id, user, db)
    if v.status in (Status.queued.value, Status.processing.value):
        raise HTTPException(status.HTTP_409_CONFLICT, "Video is already being processed")
    v.status, v.error, v.attempts, v.progress, v.stage = Status.queued.value, None, 0, 0.0, Stage.waiting.value
    col = v.collection
    col.status, col.stage, col.error = Status.processing.value, Stage.waiting.value, None
    db.commit()
    enqueue_video(v.id)
    return get_video(video_id, user, db)
