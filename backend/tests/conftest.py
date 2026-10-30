"""Test configuration: isolated SQLite DB + storage, offline mock LLM,
synchronous job execution and stubbed YouTube access (no network needed)."""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

_TMP = tempfile.mkdtemp(prefix="voxnote-test-")
os.environ.update(
    {
        "DATABASE_URL": f"sqlite:///{_TMP}/test.db",
        "STORAGE_DIR": f"{_TMP}/storage",
        "LLM_PROVIDERS": "mock",
        "STT_PROVIDER": "none",
        "TASK_BACKEND": "thread",
        "GROQ_API_KEY": "",
        "GEMINI_API_KEY": "",
        "OPENROUTER_API_KEY": "",
        "JWT_SECRET": "test-secret-test-secret-test-secret-123",
        "CHUNK_MAX_TOKENS": "400",
    }
)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.services import transcripts as tx  # noqa: E402
from app.services import youtube as yt  # noqa: E402

EN_LINES = [
    "Welcome to this lecture on machine learning fundamentals.",
    "Machine learning is a subset of artificial intelligence that allows systems to learn patterns from data.",
    "Supervised learning uses labeled data, for example predicting house prices from features.",
    "In Python we write model = LinearRegression() and then call model.fit(X_train, y_train).",
    "Gradient descent minimizes the loss function by moving against the gradient step by step.",
    "Classification predicts categories while regression predicts continuous values.",
]
AR_LINES = [
    "الـ RAG architecture بتعتمد على إننا نعمل retrieval للـ relevant documents قبل ما نبعت الـ context للـ LLM.",
    "الـ supervised learning بيعتمد على labeled data وده مثال مهم في التعلم الآلي.",
    "التعلم الآلي هو فرع من الذكاء الاصطناعي يسمح للأنظمة بالتعلم من البيانات.",
]


def make_segments(lines, repeat=8, step=9.0):
    out = []
    for i, text in enumerate(lines * repeat):
        out.append(tx.Segment(i * step, i * step + step, text))
    return out


def fake_transcript(video_id: str) -> tx.TranscriptResult:
    if video_id.startswith("AR"):
        return tx.TranscriptResult("captions", "ar", make_segments(AR_LINES))
    if video_id.startswith("XX"):
        raise tx.TranscriptUnavailable("no captions (test)")
    return tx.TranscriptResult("captions", "en", make_segments(EN_LINES))


def fake_video_meta(video_id: str) -> yt.VideoMeta:
    return yt.VideoMeta(video_id=video_id, title=f"Lecture {video_id}", channel="Test Channel",
                        duration_seconds=430, published_at="2025-01-01", url=yt.video_url(video_id))


def fake_playlist(playlist_id: str, limit=None) -> yt.PlaylistMeta:
    ids = ["ENvideo0001", "ENvideo0002", "ARvideo0003"]
    return yt.PlaylistMeta(playlist_id=playlist_id, title="ML Course", channel="Test Channel",
                           videos=[fake_video_meta(i) for i in ids])


@pytest.fixture(autouse=True)
def _offline(monkeypatch):
    from app.api import collections as col_api
    from app.pipeline import orchestrator
    from app.workers import queue

    monkeypatch.setattr(tx, "get_youtube_transcript", fake_transcript)
    monkeypatch.setattr(orchestrator, "fetch_video_metadata", fake_video_meta)
    monkeypatch.setattr(col_api, "fetch_video_metadata", fake_video_meta)
    monkeypatch.setattr(col_api, "fetch_playlist_metadata", fake_playlist)
    # Run background jobs synchronously so tests are deterministic.
    monkeypatch.setattr(queue, "_submit", lambda fn, arg, delay=0.0: fn(arg))
    monkeypatch.setattr(orchestrator.settings, "retry_base_delay", 0.0)
    monkeypatch.setattr(orchestrator.settings, "crawl_delay", 0.0)
    from app.pipeline import docs as docs_pipeline
    from tests.docs_site import make_client

    monkeypatch.setattr(docs_pipeline, "http_client_factory", make_client)


@pytest.fixture
def client():
    from app.main import app

    with TestClient(app) as c:
        yield c


@pytest.fixture
def auth_client(client):
    import uuid

    email = f"user-{uuid.uuid4().hex[:8]}@example.com"
    r = client.post("/api/auth/register", json={"email": email, "password": "secret123", "full_name": "Test"})
    assert r.status_code == 201, r.text
    client.headers["Authorization"] = f"Bearer {r.json()['access_token']}"
    return client
