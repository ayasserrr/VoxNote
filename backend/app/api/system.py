from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from sqlalchemy import text

from app import __version__
from app.config import settings
from app.db import engine
from app.deps import get_current_user
from app.models import User
from app.schemas.api import SystemStatus
from app.services import stt
from app.services.free_models import clear_cache
from app.services.llm import provider_status, test_providers

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


@router.post("/system/test-ai")
async def test_ai(_: User = Depends(get_current_user)) -> dict:
    """Re-discover the free models and send a tiny test prompt to each one."""
    clear_cache()
    results = await run_in_threadpool(test_providers)
    return {"results": results, "working": sum(1 for r in results if r["ok"])}


metrics_router = APIRouter(tags=["system"])


@metrics_router.get("/metrics", include_in_schema=False)
def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
