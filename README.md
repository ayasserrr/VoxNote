<div align="center">

# VoxNote

### AI-Powered Video Knowledge Extraction

**Your AI learning hub — turn videos and documentation into notes, courses and quizzes.**

VoxNote has two things it does:

1. **Learn from documentation.** Paste any documentation site (a framework tutorial, a library's docs, an API guide).
   VoxNote reads every page, designs a step-by-step **course**, and then teaches it to you one small lesson at a time:
   a simple explanation with an analogy and a worked example, then a **quiz** (multiple choice, true/false, short answer).
   Your answers are **corrected with explanations and feedback**. Pass the quiz to unlock the next lesson. If something is hard,
   click **"Explain it more simply"** or ask the built-in **tutor**.
2. **Learn from YouTube.** Paste a video or a whole playlist. VoxNote transcribes it (Arabic, English or mixed) and produces detailed,
   bilingual study documents (PDF + Markdown) with every concept, code sample, example, glossary term and clickable timestamps.
   Any video or playlist can also be turned into an interactive course with quizzes.

Then **ask questions across everything** you added; answers cite the exact video moment or documentation page.

FastAPI · React + TypeScript · PostgreSQL/SQLite · Celery + Redis · Whisper · free LLMs (Groq, Gemini, OpenRouter, Ollama) · BeautifulSoup · ReportLab · Docker

</div>

---

## Contents

- [Learning Hub (documentation → course → quizzes)](#learning-hub)
- [What it does with videos](#what-it-does)
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

## Learning Hub

```
 documentation URL ──▶ crawler ──▶ clean pages ──▶ AI curriculum ──▶ modules ▶ lessons
                     (sitemap,     (headings,       (2-8 modules,
                      robots.txt,   code, tables)    one idea per lesson)
                      sidebar order)
                                                        │ for each lesson, generated when you open it
                                                        ▼
        ┌─────────────── Learn ───────────────┐  ┌──── Practice ────┐  ┌───────── Result ──────────┐
        │ why it matters · simple explanation │  │ multiple choice   │  │ score · ✓/✗ per question  │
        │ analogy · worked example · key      │─▶│ true / false      │─▶│ correct answer + why      │
        │ points · common mistakes · sources  │  │ short answer      │  │ AI feedback on your text  │
        └─────────────────────────────────────┘  └───────────────────┘  │ ≥70% → next lesson unlocks│
             ▲  "Explain it more simply"  ·  tutor chat about the lesson   └───────────────────────────┘
```

- **Any docs site.** Start from the page where the docs begin (for example `https://docs.python.org/3/tutorial/`). The crawler
  stays inside that section, follows the sidebar order, also uses `sitemap.xml`, respects `robots.txt`, and keeps
  headings, code blocks, lists and tables while removing navigation, footers and cookie banners. Up to 300 pages.
- **Course design.** The AI groups the pages into modules and short lessons, each linked to the 1–3 pages it teaches.
  Your level (beginner / intermediate / advanced) and teaching language (English, Arabic, or Arabic with English terms)
  shape every lesson.
- **Lessons on demand.** A lesson is generated the first time you open it, and the next one is prepared in the background
  while you study. Even a 300-page site stays within free AI limits.
- **Real practice.** Five questions per lesson. Multiple-choice and true/false answers are checked exactly; short answers are
  graded by the AI for meaning, in any language, with partial credit and feedback. Answers are never sent to the browser
  before you submit. *Retry*, or ask for *new questions*.
- **Stuck?** *Explain it more simply* rewrites the lesson with shorter sentences and an everyday analogy (up to two levels simpler).
  The **tutor** answers your questions using the lesson and its source pages.
- **Progress.** Lessons unlock as you pass them. The app tracks best scores, attempts, XP and per-course progress, and the dashboard
  has a *Continue learning* section.
- **Videos too.** On any processed video or playlist, click **Learn this as a course**. Lessons are built from the video chapters,
  and each source links to the exact moment.

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

1. **Dashboard** – one smart input: paste a YouTube link (→ notes and PDF) or a docs link (→ course). It also shows your XP,
   lessons completed, average quiz score, *Continue learning* and recent items.
2. **New → Documentation** – docs URL, your level, teaching language, maximum pages, "only this section". You get live
   crawl progress, then **Open my course**.
3. **Learning Hub** – your courses with progress rings. Course page: modules and lessons (locked / available / completed with score),
   stats, outcomes and *Continue*. Lesson page: **Learn → Practice → Result**, *Explain it more simply*, tutor, and previous/next navigation.
4. **New → YouTube** – paste a video or playlist URL. A preview shows the title, channel, number of videos and total duration. Then choose:
   - *Document language*: Auto / English / Arabic / Bilingual
   - *Detail*: Comprehensive (captures everything) or Standard (fewer LLM calls)
   - Include transcript, clickable timestamps, one document per video, combined playlist book, maximum number of videos
5. **Collection page** – live status for every video (*Transcribing → AI extraction → Verifying → Generating documents*),
   per-video PDF/Markdown downloads, the playlist book, *Retry failed*, *Regenerate with new settings*, and a processing log.
6. **Course overview** tab (playlists) – summary, learning path, concept map, recurring concepts, unified glossary and course questions.
7. **Video page** – embedded player, interactive notes (Overview / Concepts / Technical / Examples / Takeaways / Glossary / Questions),
   a searchable transcript where every timestamp jumps to that moment on YouTube, *Ask this video*, and quality metrics.
8. **Ask** – questions across your **entire library** (videos and docs), answered with citations.
9. **Library** – every collection, plus full-text search across all transcripts and documentation pages.

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
│   │   ├── models.py               # SQLAlchemy models: User, Collection, Video, ProcessingJob, Transcript,
│   │   │                           #   TranscriptSegment, ExtractedKnowledge, Document, ProcessingLog,
│   │   │                           #   DocPage, Course, Lesson, QuizAttempt
│   │   ├── api/                    # routers: auth, collections, videos, documents, ask, learning, system
│   │   ├── schemas/
│   │   │   ├── api.py              # request/response models
│   │   │   ├── knowledge.py        # LLM structured-output schemas (validated)
│   │   │   └── learning.py         # curriculum / lesson / quiz / grading schemas
│   │   ├── services/
│   │   │   ├── crawler.py          # documentation crawler + main-content extraction
│   │   │   ├── learning.py         # curriculum, lessons, quizzes, grading, tutor, progress
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
│   │   ├── pipeline/orchestrator.py# video stages, retries, playlist synthesis
│   │   ├── pipeline/docs.py        # docs: crawl → pages → course
│   │   └── workers/                # queue abstraction + Celery app
│   ├── alembic/                    # database migrations
│   ├── tests/                      # pytest suite (runs offline)
│   ├── Dockerfile
│   └── requirements*.txt
├── frontend/
│   ├── src/
│   │   ├── pages/                  # Dashboard, New, LearningHub, Course, Lesson, Library, Collection,
│   │   │                           #   DocPage, Video, Ask, Settings, Login
│   │   ├── components/             # Layout, Markdown, KnowledgeView, TranscriptView, AskPanel, CourseCard, ...
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
| `QUIZ_PASS_SCORE` | `0.7` | Score needed to complete a lesson |
| `CRAWL_MAX_PAGES` / `CRAWL_DELAY` | `300` / `0.3` | Documentation crawl limits |
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
cd backend && pytest -q       # 41 tests, fully offline (mock LLM, stubbed YouTube, fake docs site)
cd frontend && npm run build
```

The tests cover the documentation crawler (scope, robots.txt, sitemap, page limits, content extraction), the full
docs → course → lesson → quiz → grading → unlock flow, quiz-schema normalisation and keyword-fallback grading,
curriculum sanitising, courses built from videos, URL parsing, language detection, chunking, JSON repair, lenient schema validation, concept merging, auth/JWT, Arabic RTL
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
| Docs crawl finds almost no text | The site renders its content with JavaScript. Try the docs' GitHub README, a static mirror, or a more specific section URL. |
| Docs crawl went outside the docs | Keep "Only this section" enabled and start from the docs root (e.g. `/docs/` or `/tutorial/`). |
| A lesson fails to prepare | Usually a free-tier rate limit. Click *Try again* after a few seconds, or add a second provider key. |
| YouTube transcripts suddenly fail | YouTube changes often: `pip install -U yt-dlp youtube-transcript-api`. |
| Upgrading from VoxNote 1.0 | Nothing to do: the database schema is migrated automatically on startup and existing data is kept. |

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
- [x] **Learning Hub:** documentation crawler, AI curricula, on-demand lessons, quizzes with AI grading and feedback, simpler re-explanations, tutor, progress and XP
- [ ] Flashcards / spaced-repetition export (Anki), quizzes with scoring
- [ ] Speaker diarization, video-frame OCR for on-screen code and slides
- [ ] Vector search (pgvector) alongside BM25 (hybrid retrieval)
- [ ] Export to Notion, workspaces and sharing, learning progress tracking

See [docs/ROADMAP.md](docs/ROADMAP.md).

## License

MIT — see [LICENSE](LICENSE).
