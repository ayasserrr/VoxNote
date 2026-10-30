"""VoxNote API entrypoint.

    uvicorn app.main:app --reload
"""

from __future__ import annotations

import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api import ask, auth, collections, documents, system, videos
from app.config import settings
from app.db import init_db
from app.logging_setup import setup_logging

setup_logging()
log = logging.getLogger("voxnote")


@asynccontextmanager
async def lifespan(_: FastAPI):
    if settings.db_auto_create:
        init_db()
    from app.services.llm import configured_providers
    from app.workers.queue import recover_pending, shutdown

    providers = [p.name for p in configured_providers()]
    if providers:
        log.info("LLM provider chain: %s", " -> ".join(providers))
    else:
        log.warning("No LLM provider configured! Add GROQ_API_KEY or GEMINI_API_KEY to .env "
                    "(or LLM_PROVIDERS=mock for an offline demo).")
    recover_pending()
    yield
    shutdown()


app = FastAPI(
    title="VoxNote API",
    version=__version__,
    description="Turn YouTube videos and playlists into complete, structured, bilingual knowledge documents.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_context(request: Request, call_next):
    rid = request.headers.get("x-request-id") or uuid.uuid4().hex[:12]
    t0 = time.perf_counter()
    response = await call_next(request)
    ms = (time.perf_counter() - t0) * 1000
    response.headers["x-request-id"] = rid
    if not request.url.path.endswith(("/health", "/metrics")):
        log.info("%s %s -> %s (%.0f ms) rid=%s", request.method, request.url.path, response.status_code, ms, rid)
    return response


for r in (auth.router, collections.router, videos.router, documents.router, ask.router, system.router):
    app.include_router(r, prefix=settings.api_prefix)
app.include_router(system.metrics_router)


@app.get("/", include_in_schema=False)
def root() -> dict:
    return {"name": "VoxNote API", "version": __version__, "docs": "/docs"}
