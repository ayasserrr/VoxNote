"""Shared FastAPI dependencies."""

from __future__ import annotations

from fastapi import Depends, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Collection, User, Video
from app.security import decode_access_token

_bearer = HTTPBearer(auto_error=False)


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    token: str | None = Query(default=None, description="Token for direct download links"),
    db: Session = Depends(get_db),
) -> User:
    raw = creds.credentials if creds else token
    if not raw:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    user_id = decode_access_token(raw)
    user = db.get(User, user_id) if user_id else None
    if not user or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token")
    return user


def get_owned_collection(collection_id: str, user: User, db: Session) -> Collection:
    col = db.get(Collection, collection_id)
    if not col or col.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Collection not found")
    return col


def get_owned_video(video_id: str, user: User, db: Session) -> Video:
    video = db.get(Video, video_id)
    if not video or video.collection.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Video not found")
    return video
