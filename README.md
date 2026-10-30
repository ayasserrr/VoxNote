<div align="center">

# VoxNote

### AI-Powered Video Knowledge Extraction

**Turn every video into a complete learning resource.**

VoxNote takes YouTube videos and whole playlists and turns what the speaker says into detailed, organized,
bilingual (Arabic / English) learning documents. Each document has the full transcript, an explanation of every concept,
code, examples, a glossary, review questions and clickable timestamps. You can then **ask questions across the whole
playlist** and get answers that cite the exact moments in the videos.

FastAPI · React + TypeScript · PostgreSQL/SQLite · Celery + Redis · Whisper · free LLMs (Groq, Gemini, OpenRouter, Ollama) · ReportLab · Docker

</div>

---

## Contents

- [What it does](#what-it-does)
- [Quick start (5 minutes)](#quick-start-5-minutes)
- [Free AI providers](#free-ai-providers--how-to-get-keys)
- [Using the app](#using-the-app)
- [Architecture](#architecture)
- [Project structure](#project-structure)
- [Configuration reference](#configuration-reference)
- [Running with Docker (production-style)](#running-with-docker-production-style)
- [Testing & quality](#testing--quality)
- [Troubleshooting](#troubleshooting)
- [Responsible use](#responsible-use)
- [Roadmap](#roadmap)

More documentation in [`docs/`](docs): [architecture](docs/ARCHITECTURE.md) · [API](docs/API.md) ·
[free AI providers](docs/FREE_AI_PROVIDERS.md) · [evaluation](docs/EVALUATION.md) · [roadmap](docs/ROADMAP.md)

---

## What it does

Paste a YouTube URL (one video or a playlist with dozens of videos) and click **Start processing**. For **each video**, VoxNote:

1. Reads the metadata: title, channel, duration, publication date.
2. Gets the transcript. It uses captions when they exist; otherwise it transcribes the audio with **Whisper large-v3 (free on Groq)**.
3. Detects the language: English, Arabic (including colloquial Egyptian) or **mixed Arabic + English**.
4. Splits the transcript into token-budgeted chunks and runs a **structured LLM extraction** on each chunk. The output is validated
   with Pydantic and contains concepts, definitions, the speaker's own claims, examples, code, equations, key points, a glossary and questions.
5. Assembles the chunks into one document: merges duplicate concepts, keeps the timestamps and writes a video-level overview.
6. **Checks the result against the transcript**: timeline coverage, concept grounding, timestamp validity and failed chunks.
7. Builds a **professional PDF** (Arabic RTL, English LTR and mixed text, clickable YouTube timestamps, table of contents) plus a **Markdown** export.
8. Saves everything to your personal library.

For **playlists**, it then builds a **cross-video knowledge layer**: a course summary, a learning path, a concept relationship map,
recurring concepts, a unified glossary and course-level review questions. It also produces a combined **Playlist Knowledge Book** PDF.

Each generated document contains:

| # | Section | What's inside |
|---|---|---|
| 00 | Video information | Title, channel, duration, date, detected language, transcript source, AI model |
| 01 | Overview | Multi-paragraph overview, learning objectives, prerequisites |
| 02 | Chapters & timeline | Auto-detected sections with time ranges and summaries |
| 03 | Detailed concepts | Definition, explanation, *what the speaker said*, examples, related concepts, plus **AI-added clarifications that are clearly marked as not from the video** |
| 04 | Technical concepts | Code, commands, equations, algorithms, tools, architectures |
| 05 | Examples & use cases | Every example the speaker gives |
| 06 | Takeaways & key points | The things to remember, with timestamps |
| 07 | Glossary | Term, definition and translation |
| 08 | Review questions | Generated from the actual content, with answers |
| 09 | Complete transcript | Readable timestamped paragraphs, each linked to the video |
| 10 | Quality report | Coverage and grounding metrics, warnings |

Other features:

- **Ask your playlist / library (RAG):** answers are grounded in the transcripts, with `[1]`-style citations and timestamp links.
- **Search** across every transcript you have processed (Arabic-aware normalization).
- **Live progress per video.** If a video fails, only that video is retried, never the whole playlist.
- **Regenerate** documents with new settings (for example English → Arabic) without transcribing again.
- **Upload your own audio/video files**, for content you own or recordings without a YouTube link.
- **Output language is independent of the video language:** English video → Arabic PDF, Arabic video → English PDF, mixed video → bilingual PDF.
- **Automatic fallback between providers:** if Groq is rate-limited, VoxNote moves on to Gemini, then OpenRouter, then Ollama.

---

## Quick start (5 minutes)

### Requirements

- **Python 3.11+**
- **Node.js 18+** (20 or 22 recommended)
- **ffmpeg**. Optional, but needed to transcribe long videos that have no captions.
  macOS: `brew install ffmpeg` · Ubuntu: `sudo apt install ffmpeg` · Windows: `winget install ffmpeg`
- **One free API key.** [Groq](https://console.groq.com/keys) is recommended because the same key also covers speech-to-text.

### 1. Clone and configure

```bash
git clone https://github.com/ayasserrr/VoxNote.git
cd VoxNote
cp .env.example .env
```

Open `.env` and paste your free key:

```ini
GROQ_API_KEY=gsk_...            # https://console.groq.com/keys
# and/or
GEMINI_API_KEY=AIza...          # https://aistudio.google.com/apikey
```

### 2. Install

**Linux / macOS / WSL**

```bash
./scripts/setup.sh        # or: make setup
```

**Windows (PowerShell)**

```powershell
./scripts/setup.ps1
```

<details>
<summary>Manual install (any OS)</summary>

```bash
# backend
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate    Linux/macOS: source .venv/bin/activate
pip install -r requirements-dev.txt

# frontend
cd ../frontend
npm install
```
</details>

### 3. Run

```bash
./scripts/dev.sh          # or: make dev
```

Or start the two parts in separate terminals:

```bash
# terminal 1 – API
cd backend && source .venv/bin/activate && uvicorn app.main:app --reload --port 8000
# terminal 2 – React UI
cd frontend && npm run dev
```

Then open **http://localhost:5173**, create an account (it is stored locally), paste a YouTube URL, and start processing.

- API docs (Swagger): http://localhost:8000/docs
- Prometheus metrics: http://localhost:8000/metrics

> **No key yet?** Run `make demo` (or set `LLM_PROVIDERS=mock` in `.env`). The whole pipeline then runs with a built-in offline
> extractive "model", so you can try the full UI. The output quality is low on purpose; add a free key for real results.

By default, local mode needs no database server and no Redis. It uses **SQLite** and an **in-process job queue**, and both are
recovered automatically after a restart. Use [Docker](#running-with-docker-production-style) for the full PostgreSQL + Redis + Celery stack.

---

## Free AI providers — how to get keys

VoxNote is designed to run **entirely on free models**. It tries the providers in `LLM_PROVIDERS` in order and skips any provider without a key.

| Provider | What you get for free | Default model | Get a key |
|---|---|---|---|
| **Groq** ⭐ | Rate-limited free tier, very fast inference, **free Whisper large-v3 speech-to-text** | `llama-3.3-70b-versatile` | https://console.groq.com/keys |
| **Google Gemini** | Free tier for Flash models, large context window, strong Arabic | `gemini-2.5-flash` | https://aistudio.google.com/apikey |
| **OpenRouter** | Many `:free` models; `openrouter/free` routes to one automatically | `openrouter/free` | https://openrouter.ai/keys |
| **Ollama** | Unlimited, runs locally and offline | `qwen2.5:7b` | https://ollama.com/download |
| Any OpenAI-compatible server | LM Studio, vLLM, … | configurable | — |

**Recommended setup:** `GROQ_API_KEY` (LLM + speech-to-text) plus `GEMINI_API_KEY` as a fallback.
Free tiers have per-minute and per-day limits, so VoxNote retries on HTTP 429 (honouring `Retry-After`), throttles requests
(`LLM_MIN_INTERVAL`) and falls back to the next provider.
See [docs/FREE_AI_PROVIDERS.md](docs/FREE_AI_PROVIDERS.md) for limits, model choices and tips for Arabic.

Model names change over time. Every model is configurable in `.env` (`GROQ_MODEL`, `GEMINI_MODEL`, `OPENROUTER_MODEL`, `OLLAMA_MODEL`).
The **Settings** page in the app shows which providers are active.

---

## Using the app

1. **New** – paste a video or playlist URL. A preview shows the title, channel, number of videos and total duration. Then choose:
   - *Document language*: Auto / English / Arabic / Bilingual
   - *Detail*: Comprehensive (captures everything) or Standard (fewer LLM calls)
   - Include transcript, clickable timestamps, one document per video, combined playlist book, maximum number of videos
2. **Collection page** – live status for every video (*Transcribing → AI extraction → Verifying → Generating documents*),
   per-video PDF/Markdown downloads, the playlist book, *Retry failed*, *Regenerate with new settings*, and a processing log.
3. **Course overview** tab (playlists) – summary, learning path, concept map, recurring concepts, unified glossary and course questions.
4. **Video page** – embedded player, interactive notes (Overview / Concepts / Technical / Examples / Takeaways / Glossary / Questions),
   a searchable transcript where every timestamp jumps to that moment on YouTube, *Ask this video*, and quality metrics.
5. **Ask** – questions across your **entire library**, answered with citations.
6. **Library** – every collection, plus full-text search across all transcripts.

---

## Architecture

```
┌──────────────┐   REST/JSON   ┌───────────────────────────────────────────────┐
│ React + TS   │ ────────────▶ │ FastAPI  (auth · collections · videos · ask)  │
│ (Vite/nginx) │ ◀──────────── │                                               │
└──────────────┘   polling     └──────────┬────────────────────────────────────┘
                                          │ enqueue 1 job per video
                                          ▼
                      ┌──────────── Job queue ────────────┐
                      │ thread pool (local) │ Celery+Redis │
                      └──────────────┬─────────────────────┘
                                     ▼
 ┌───────────────────────────── Video pipeline ─────────────────────────────────┐
 │ metadata → transcript → language → chunk → LLM extract (per chunk, JSON)     │
 │ (yt-dlp)   captions /    ar/en/    token-     validated by Pydantic,         │
 │            Whisper       mixed     aware      provider fallback chain        │
 │      → merge + video synthesis → verify vs transcript → PDF + Markdown       │
 └──────────────────────────────────────────┬───────────────────────────────────┘
                                            ▼ all videos finished
                         Playlist synthesis (concept map, path, glossary)
                                   → Playlist Knowledge Book
 Storage: PostgreSQL/SQLite (metadata, transcripts, knowledge JSON, logs)
          Local disk or S3-compatible bucket (PDF/Markdown, uploads)
```

Key design decisions:

- **Each video has its own lifecycle** (status, stage, attempts, error). Videos are retried, processed in parallel and scaled independently. A playlist is never one big job.
- **Hierarchical extraction.** A 2-hour lecture is never sent to the LLM in one request. It is chunked (about 2,500 tokens, with overlap), extracted chunk by chunk, merged deterministically, then summarized.
- **Structured output.** Every LLM response is parsed and validated against Pydantic schemas. Malformed JSON gets one automatic repair round. One failing chunk does not fail the video.
- **Traceability.** Every concept, example and key point keeps `start`/`end` timestamps. AI-added explanations are stored in a separate `ai_clarification` field and shown with a distinct visual marker.
- **Idempotency.** Transcripts are cached by YouTube ID, so the same video is never transcribed twice, and *Regenerate* reuses them.
- **Free-tier friendly.** Throttling, `Retry-After`-aware retries and automatic fallback between providers.

Full details are in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

---

## Project structure

```
VoxNote/
├── backend/
│   ├── app/
│   │   ├── main.py                 # FastAPI app, middleware, lifespan (DB init, job recovery)
│   │   ├── config.py               # all settings (env / .env)
│   │   ├── models.py               # SQLAlchemy models: User, Collection, Video, ProcessingJob,
│   │   │                           #   Transcript, TranscriptSegment, ExtractedKnowledge, Document, ProcessingLog
│   │   ├── api/                    # routers: auth, collections, videos, documents, ask, system
│   │   ├── schemas/
│   │   │   ├── api.py              # request/response models
│   │   │   └── knowledge.py        # LLM structured-output schemas (validated)
│   │   ├── services/
│   │   │   ├── youtube.py          # URL parsing + metadata/playlists via yt-dlp
│   │   │   ├── transcripts.py      # captions → yt-dlp subtitles → audio + Whisper
│   │   │   ├── stt.py              # Groq Whisper / faster-whisper, ffmpeg chunking
│   │   │   ├── language.py         # ar / en / mixed detection
│   │   │   ├── chunking.py         # token-aware chunking with overlap
│   │   │   ├── llm.py              # provider-agnostic client, fallback, JSON repair
│   │   │   ├── prompts.py          # prompt templates
│   │   │   ├── knowledge.py        # extraction → merge → synthesis → verification
│   │   │   ├── search.py           # BM25 retrieval + RAG answers
│   │   │   ├── markdown.py         # Markdown export
│   │   │   ├── storage.py          # local / S3 storage
│   │   │   ├── mock_llm.py         # offline model for tests & demo
│   │   │   └── pdf/                # ReportLab renderer + bidi text + bundled fonts
│   │   ├── pipeline/orchestrator.py# stages, retries, playlist synthesis
│   │   └── workers/                # queue abstraction + Celery app
│   ├── alembic/                    # database migrations
│   ├── tests/                      # pytest suite (runs offline)
│   ├── Dockerfile
│   └── requirements*.txt
├── frontend/
│   ├── src/
│   │   ├── pages/                  # New, Library, Collection, Video, Ask, Settings, Login
│   │   ├── components/             # KnowledgeView, TranscriptView, AskPanel, ...
│   │   ├── api.ts · types.ts · auth.tsx · styles.css
│   ├── Dockerfile · nginx.conf
├── docs/                           # architecture, API, providers, evaluation, roadmap
├── deploy/prometheus.yml
├── scripts/                        # setup.sh, dev.sh, setup.ps1
├── docker-compose.yml
├── Makefile
└── .env.example
```

---

## Configuration reference

All settings are environment variables, documented inline in [`.env.example`](.env.example). The most important ones:

| Variable | Default | Purpose |
|---|---|---|
| `LLM_PROVIDERS` | `groq,gemini,openrouter,ollama` | Provider order / fallback chain (`mock` for offline) |
| `GROQ_API_KEY`, `GEMINI_API_KEY`, `OPENROUTER_API_KEY` | – | Free API keys |
| `*_MODEL` | see `.env.example` | Model for each provider |
| `LLM_MIN_INTERVAL` | `0` | Seconds between LLM calls (2–4 recommended on free tiers) |
| `STT_PROVIDER` | `groq` | `groq` (free Whisper), `local` (faster-whisper) or `none` |
| `ALLOW_AUDIO_DOWNLOAD` | `true` | Transcribe audio when a video has no captions |
| `YOUTUBE_PROXY_URL` | – | Proxy for servers that YouTube blocks |
| `DATABASE_URL` | SQLite in `backend/data/` | Any SQLAlchemy URL (PostgreSQL in Docker) |
| `TASK_BACKEND` | `thread` | `thread` or `celery` |
| `CHUNK_MAX_TOKENS` | `2500` | Transcript chunk size for extraction |
| `STORAGE_BACKEND` | `local` | `local` or `s3` |
| `JWT_SECRET` | dev value | **Change this for any deployment** |

---

## Running with Docker (production-style)

```bash
cp .env.example .env       # add your free key(s)
docker compose up --build
```

| Service | URL |
|---|---|
| Web app | http://localhost:3000 |
| API + Swagger | http://localhost:8000/docs |
| Prometheus (optional) | `docker compose --profile monitoring up` → http://localhost:9090 |

The stack is PostgreSQL 16, Redis 7, the FastAPI API (it runs `alembic upgrade head` on start), a Celery worker
(scale it with `docker compose up --scale worker=3`) and the React build served by nginx, which proxies `/api`.
To use Ollama on your host machine from Docker, set `OLLAMA_ENABLED=true`. The containers reach it through `host.docker.internal`.

---

## Testing & quality

```bash
make test                     # backend tests + frontend type-check
# or
cd backend && pytest -q       # 30 tests, fully offline (mock LLM, stubbed YouTube)
cd frontend && npm run build
```

The tests cover URL parsing, language detection, chunking, JSON repair, lenient schema validation, concept merging, auth/JWT, Arabic RTL
line wrapping, PDF generation (English, Arabic and the playlist book), Markdown export, the complete video and playlist pipelines through the API,
RAG answers and search, failure handling plus single-video retry, and per-user ownership checks.
CI (GitHub Actions) runs lint, tests, migrations, the frontend build and the Docker builds on every push.

Quality metrics produced for every video (see [docs/EVALUATION.md](docs/EVALUATION.md)): timeline coverage, concept grounding,
invalid timestamps, failed chunks, LLM calls and tokens, and processing time per stage (Prometheus).

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| "No LLM provider configured" | Add `GROQ_API_KEY` or `GEMINI_API_KEY` to `.env` and **restart** the backend. Check the Settings page. |
| `No transcript available ... RequestBlocked / IpBlocked` | YouTube blocks many cloud and VPN IPs. Run locally, set `YOUTUBE_PROXY_URL`, or upload the audio file. |
| Video has no captions | Set `GROQ_API_KEY` (free Whisper) and install `ffmpeg`, or use `STT_PROVIDER=local` with `pip install faster-whisper`. |
| HTTP 429 / slow progress | Free-tier rate limit. Set `LLM_MIN_INTERVAL=3`, add a second provider key, or choose *Standard* detail. |
| Arabic shows as boxes in the PDF | The bundled DejaVu fonts cover Arabic; make sure `backend/app/services/pdf/fonts/` exists. |
| Want to move from local SQLite to Alembic migrations | `cd backend && alembic stamp head` once, then use `alembic upgrade head` after future schema changes. |

---

## Responsible use

VoxNote is a learning tool. Only process content that you are allowed to process, and respect YouTube's Terms of Service
and creators' rights. Captions are read through public interfaces. Audio is downloaded only as a fallback when there are no captions,
and you can turn that off with `ALLOW_AUDIO_DOWNLOAD=false`. For your own recordings, use the **Upload** option. Generated documents
link back to the original video and clearly mark AI-added explanations.

---

## Roadmap

- [x] **Level 1 – Core MVP:** videos and playlists, Arabic/English, transcription, detailed extraction, per-video and combined PDFs, progress and retries, library
- [x] **Level 2 (partial):** chapters, timestamp citations, review questions, concept maps, search, *Ask your playlist*
- [ ] Flashcards / spaced-repetition export (Anki), quizzes with scoring
- [ ] Speaker diarization, video-frame OCR for on-screen code and slides
- [ ] Vector search (pgvector) alongside BM25 (hybrid retrieval)
- [ ] Export to Notion, workspaces and sharing, learning progress tracking

See [docs/ROADMAP.md](docs/ROADMAP.md).

## License

MIT — see [LICENSE](LICENSE).
