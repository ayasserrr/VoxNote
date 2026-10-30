# VoxNote — System Design

## 1. Goals

### Functional requirements

| ID | Requirement |
|---|---|
| F1 | Accept a YouTube video URL, a playlist URL, or an uploaded audio/video file |
| F2 | Retrieve metadata (title, channel, duration, date, thumbnail) and playlist order |
| F3 | Obtain a timestamped transcript: captions first, Whisper speech-to-text as fallback |
| F4 | Detect English / Arabic (including Egyptian dialect) / mixed speech |
| F5 | Extract structured knowledge: concepts, definitions, the speaker's claims, examples, code, equations, key points, glossary, questions |
| F6 | Separate the speaker's content from AI-added explanations |
| F7 | Generate a PDF and a Markdown document per video, plus a combined playlist book |
| F8 | Output language independent of the video language (en / ar / bilingual) |
| F9 | Cross-video synthesis: course summary, concept map, learning path, unified glossary |
| F10 | Show live progress for each video, retry failed videos individually, regenerate with new settings |
| F11 | Question answering and search across one video, one playlist, or the whole library, with timestamp citations |
| F12 | Multi-user accounts (start personal, architected for SaaS) |

### Non-functional requirements

| Concern | Target / approach |
|---|---|
| Cost | Runs on free LLM and STT tiers; no paid service is required |
| Reliability | One failing chunk or video never fails the whole job; automatic retries with exponential backoff |
| Scalability | One job per video; workers scale horizontally (Celery) |
| Traceability | Every extracted item keeps source timestamps; quality report per video |
| Portability | Zero-dependency local mode (SQLite + thread pool) and a Docker production mode (Postgres + Redis + Celery) |
| Security | JWT auth, PBKDF2 password hashing, per-user ownership checks on every resource, no secrets in the repo |
| Observability | Request logging with request IDs, processing logs in the DB, Prometheus metrics |

## 2. C4 — Context and containers

```
               ┌──────────────┐
   Learner ───▶│  VoxNote UI  │  React + TypeScript (Vite; nginx in production)
               └──────┬───────┘
                      │ HTTPS / JSON (JWT)
               ┌──────▼───────┐       ┌──────────────┐
               │  VoxNote API │──────▶│ PostgreSQL / │  users, collections, videos, jobs,
               │   FastAPI    │       │   SQLite     │  transcripts, knowledge JSON, documents, logs
               └──────┬───────┘       └──────────────┘
                      │ enqueue
               ┌──────▼───────┐       ┌──────────────┐
               │ Job queue    │──────▶│ Workers      │  pipeline orchestrator
               │ Redis/thread │       │ Celery/thread│
               └──────────────┘       └──────┬───────┘
                                             │
        ┌──────────────┬─────────────────────┼────────────────────┬───────────────┐
        ▼              ▼                     ▼                    ▼               ▼
   YouTube (yt-dlp,  Groq Whisper      LLM providers         File storage     Prometheus
   transcript API)   (free STT)        Groq/Gemini/OpenRouter (disk / S3)
                                       /Ollama (free)
```

## 3. Video pipeline

Every stage writes its status to `videos.stage` / `videos.progress` immediately, so the UI (which polls every 2.5 s) shows live
progress. Each stage duration is also recorded in the Prometheus histogram `voxnote_stage_seconds`.

| Stage | Module | Notes |
|---|---|---|
| `metadata` | `services/youtube.py` | yt-dlp, no API key. Playlists use `extract_flat`, so a 200-video playlist is listed in one request |
| `transcribing` | `services/transcripts.py`, `services/stt.py` | 1) youtube-transcript-api (manual captions before auto captions, preferred languages first) 2) yt-dlp subtitles (json3) 3) audio download + Whisper. Audio is normalised with ffmpeg (mono, 16 kHz, 32 kbps) and split into 10-minute chunks to stay under upload limits; timestamps are shifted back onto the original timeline. **Cache:** a transcript already fetched for the same YouTube ID is reused |
| `language` | `services/language.py` | Ratio of Arabic to Latin letters → `ar` / `en` / `mixed`. Code-switched speech is common in technical Arabic, so `mixed` is its own label, not an error |
| `extracting` | `services/knowledge.py` | Token-aware chunks (`CHUNK_MAX_TOKENS`, overlapping segments). Each line is prefixed `[mm:ss]` so the model can cite times. One structured LLM call per chunk. Failed chunks are recorded but do not stop the video |
| `assembling` | `services/knowledge.py` | Deterministic merge: concepts are deduplicated by a normalised name (handles case, articles, Arabic `ال` and diacritics) while keeping the earliest start / latest end; technical items, examples, key points and questions are deduplicated. Then one video-level LLM call writes the overview, objectives, takeaways and prerequisites |
| `verifying` | `services/knowledge.py::verify` | Timeline coverage, concept grounding (concept names found in the transcript), timestamps outside the duration, failed chunks → `quality` JSON plus warnings |
| `rendering` | `services/pdf/`, `services/markdown.py` | PDF and Markdown, stored through `services/storage.py` |

### Hierarchical extraction (why not one big prompt?)

A 90-minute lecture is about 15–20k words. One huge prompt runs into context limits on free models, makes the model compress
(it loses details), takes a long time, and fails all at once. Chunking keeps each request small (fast, cheap, reliable), lets the
model be exhaustive locally, and makes failures partial. The merge step is deterministic and the final synthesis only sees chunk
summaries, so the video-level call stays small.

### Structured output

`schemas/knowledge.py` defines `ChunkKnowledge`, `VideoSynthesis`, `VideoKnowledge` and `CollectionSynthesis`. The schemas are
deliberately lenient: timestamps given as `"02:05"` become `125`, unknown `kind` values map to `other`, and `["Video 3"]` becomes `[3]`.
Free models are imperfect, and a strict schema would throw away good content over a formatting slip. `llm.extract_json` strips
code fences, removes `<think>` blocks from reasoning models, finds the JSON object and fixes trailing commas. If validation still
fails, the model gets one repair round with the validation error.

### Provider fallback

`LLMClient` holds an ordered list of providers. For each call it:
1. Throttles requests (`LLM_MIN_INTERVAL`, shared across threads).
2. Retries HTTP 429/5xx with `Retry-After` or exponential backoff. If the wait is longer than 90 s (daily quota used up), it moves to the next provider immediately.
3. Retries without `response_format` if a model rejects JSON mode.
4. Disables a provider for the rest of the run after a 401/403 (bad key).

Token usage per provider is tracked (`voxnote_llm_tokens_total`) and stored on each `ExtractedKnowledge` row.

## 4. Playlist synthesis

`pipeline/orchestrator.py::check_collection` runs after every video finishes. Once all videos have reached a terminal state, it
claims the synthesis **atomically** (`UPDATE … WHERE stage != 'synthesizing'`), so two workers finishing at the same moment
cannot both start it. The synthesis prompt gets a condensed view of each video (overview, concepts, takeaways), cut down to fit a
free-tier context, and returns a `CollectionSynthesis`. The playlist book is then rendered: course-level sections first, then every
video's full document.

## 5. Data model

```
users 1─* collections 1─* videos 1─1 transcripts 1─* transcript_segments
                    │           1─1 extracted_knowledge (data JSON, quality JSON, provider, tokens)
                    │           1─* processing_jobs (attempt history, metrics)
                    1─* documents (kind video|collection, format pdf|md, storage_key)
                    1─* processing_logs
```

- `collections.kind`: `video | playlist | upload`. A single video is a collection with one video, so there is only one code path.
- `collections.settings`: the processing settings (language, detail, toggles), stored so a job can be regenerated or resumed.
- `collections.synthesis`: the cross-video knowledge JSON.
- The knowledge is stored as JSON (`extracted_knowledge.data`). It is always read and written as a whole document, its schema
  changes quickly, and both PostgreSQL (`JSON`) and SQLite support it. Concepts are indexed for search through the BM25 index instead.

Migrations live in `backend/alembic`. In local mode, `DB_AUTO_CREATE=true` creates the tables on startup; Docker runs `alembic upgrade head`.

## 6. Jobs, retries, recovery

- `workers/queue.py` hides the backend: `enqueue_video(id, delay)` and `enqueue_synthesis(id)`.
- **thread mode:** `ThreadPoolExecutor(WORKER_CONCURRENCY)`; delayed retries use timers. On startup, `recover_pending()` re-queues
  videos that were left `queued`/`processing` and playlists that were stuck in synthesis.
- **celery mode:** `acks_late`, `prefetch_multiplier=1` and `reject_on_worker_lost`, so a crashed worker's job is redelivered.
- **Retries:** errors that a retry can fix (network, rate limits, a temporary LLM failure) are retried up to `MAX_RETRIES` with
  exponential backoff. Errors a retry cannot fix (no transcript and no STT, missing configuration) fail immediately with an
  actionable message. Users can retry a single video or all failed videos; completed videos are never processed again.

## 7. Retrieval (Ask your playlist)

`services/search.py` builds passages from ~75-second transcript windows plus every extracted concept, and ranks them with **BM25**.
Arabic is normalised (alef variants, ta marbuta, diacritics, tatweel, the `ال` prefix), and stop words are removed in both languages.
The index is cached per scope and invalidated when a video's `updated_at` changes. The top-k passages are numbered and sent to the
LLM with instructions to cite `[n]` and refuse when the context does not contain the answer. The API returns the answer plus the
sources with deep links.

BM25 was chosen for the MVP because it needs no embedding model, no GPU and no extra infrastructure, and it handles exact technical
terms well (for example `LinearRegression`, `RAG`). The interface is isolated, so hybrid BM25 + vector search (pgvector or Qdrant with a
multilingual embedding model such as `multilingual-e5`) can be added without changing the API.

## 8. PDF rendering and bidirectional text

ReportLab draws glyphs left to right and does not shape Arabic. `services/pdf/text.py`:
1. wraps each paragraph **in logical order**, measuring the *shaped* width,
2. reshapes (`arabic-reshaper`) and reorders (`python-bidi`) **each line separately**,
3. passes the pre-broken lines to ReportLab.

Applying bidi to a whole paragraph and then wrapping it puts the end of an Arabic sentence on the first line; this approach avoids
that. The base direction is chosen per paragraph (mostly Arabic → RTL and right-aligned), so mixed sentences like
"الـ RAG architecture بتعتمد على retrieval" render correctly. Tables and two-column transcript rows are mirrored in RTL documents.
DejaVu Sans is bundled (it covers Latin, Arabic and maths symbols), so no system fonts are required.

Timestamps are `<a href="https://www.youtube.com/watch?v=ID&t=SECs">` links. The table of contents and PDF outline are generated with
a multi-pass build.

## 9. Security

- PBKDF2-SHA256 (390k iterations, standard library only) for passwords; HS256 JWTs with configurable expiry.
- Every collection, video and document lookup checks `user_id` ownership and returns 404, not 403, so the existence of other users' resources is not revealed.
- Download links accept `?token=` so the browser can open PDFs directly; tokens expire.
- Upload type allow-list and size limit; storage keys are resolved inside the storage root (no path traversal).
- `ALLOW_REGISTRATION=false` locks the instance down after the first account is created.

## 10. Observability

- `GET /metrics`: `voxnote_videos_processed_total{status}`, `voxnote_stage_seconds{stage}`,
  `voxnote_llm_requests_total{provider,outcome}`, `voxnote_llm_tokens_total{provider,kind}`,
  `voxnote_transcript_source_total{source}`, `voxnote_documents_generated_total{kind,format}`.
- `GET /api/health` checks the database.
- `GET /api/collections/{id}/logs` returns a per-collection processing log (also visible in the UI).
- Each request is logged with its method, path, status, latency and `x-request-id`.

Note: in Celery mode, the pipeline metrics are produced in the worker processes. To scrape them, run a Prometheus multiprocess
setup or a pushgateway; the API process only exposes its own metrics.
