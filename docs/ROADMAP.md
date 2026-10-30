# Roadmap

## Done — v1.0

**Phase 1 – System design:** requirements, C4 diagrams, data model, API contracts ([ARCHITECTURE.md](ARCHITECTURE.md), [API.md](API.md))

**Phase 2 – Backend foundation:** FastAPI, SQLAlchemy 2, Alembic, JWT auth, collections/videos API

**Phase 3 – Video processing:** yt-dlp metadata and playlists, captions → subtitles → Whisper fallback, language detection, timestamped segments, transcript cache

**Phase 4 – AI knowledge engine:** token-aware chunking, structured extraction with Pydantic validation and JSON repair, deterministic merge,
video synthesis, verification against the transcript, multi-provider fallback using free models

**Phase 5 – Documents:** ReportLab PDFs (Arabic RTL / English LTR / mixed), code blocks, glossary tables, clickable timestamps, TOC and outline,
per-video and playlist books, Markdown export

**Phase 6 – Background processing:** thread pool and Celery + Redis, per-video jobs, exponential-backoff retries, recovery after restarts, atomic playlist synthesis

**Phase 7 – Frontend:** URL preview, settings, live per-video progress, library, video notes viewer, transcript search, course overview, Q&A, settings/status

**Phase 8 – Production engineering:** Docker Compose (Postgres, Redis, API, worker, nginx), GitHub Actions CI, offline test suite, Prometheus metrics, logs

**Phase 9 (partial) – Advanced AI:** Ask your playlist / library (BM25 RAG with citations), full-text search, review questions, concept maps

## Next

- [ ] Hybrid retrieval: pgvector + multilingual embeddings (`intfloat/multilingual-e5-small`) combined with BM25 using reciprocal rank fusion
- [ ] Flashcards (Anki `.apkg` export) and scored quizzes
- [ ] Server-sent events instead of polling
- [ ] Video-frame extraction + OCR for on-screen code and slides
- [ ] Speaker diarization (pyannote) for interviews and panels
- [ ] Notion export, shareable read-only links
- [ ] Workspaces, quotas and usage dashboards (SaaS mode)
- [ ] LLM-as-judge faithfulness scoring as an optional pipeline stage
- [ ] OpenTelemetry tracing across API → queue → worker → LLM
