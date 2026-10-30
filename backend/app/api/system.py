from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from sqlalchemy import text

from app import __version__
from app.config import settings
from app.db import engine
from app.schemas.api import SystemStatus
from app.services import stt
from app.services.llm import provider_status

router = APIRouter(tags=["system"])


@router.get("/health")
def health() -> dict:
    db_ok = True
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception:  # pragma: no cover
        db_ok = False
    return {"status": "ok" if db_ok else "degraded", "database": db_ok}


@router.get("/system/status", response_model=SystemStatus)
def system_status() -> SystemStatus:
    return SystemStatus(
        app=settings.app_name,
        version=__version__,
        task_backend=settings.task_backend,
        llm_providers=provider_status(),
        stt_provider=settings.stt_provider,
        stt_available=stt.is_available(),
        ffmpeg_available=stt.ffmpeg_available(),
        storage_backend=settings.storage_backend,
    )


metrics_router = APIRouter(tags=["system"])


@metrics_router.get("/metrics", include_in_schema=False)
def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
