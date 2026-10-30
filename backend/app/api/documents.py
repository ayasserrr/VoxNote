from __future__ import annotations

from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse, Response
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user
from app.models import Document, User
from app.services.storage import get_storage

router = APIRouter(prefix="/documents", tags=["documents"])

_MEDIA = {"pdf": "application/pdf", "md": "text/markdown; charset=utf-8"}


@router.get("/{document_id}/download")
def download(
    document_id: str,
    inline: bool = Query(default=False, description="Display in browser instead of downloading"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    doc = db.get(Document, document_id)
    if not doc or doc.collection.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found")
    filename = doc.storage_key.rsplit("/", 1)[-1]
    disposition = "inline" if inline else "attachment"
    headers = {"Content-Disposition": f"{disposition}; filename*=UTF-8''{quote(filename)}"}
    storage = get_storage()
    path = storage.local_path(doc.storage_key)
    media = _MEDIA.get(doc.format, "application/octet-stream")
    if path:
        return FileResponse(path, media_type=media, headers=headers)
    try:
        data = storage.read_bytes(doc.storage_key)
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status.HTTP_404_NOT_FOUND, "File missing from storage") from exc
    return Response(data, media_type=media, headers=headers)
