# Getting started with VoxNote — step by step

This guide takes you from nothing to a running VoxNote on your own computer (Windows, macOS or Linux).
It takes about **10 minutes**, and everything you need is **free**.

- [1. Install the prerequisites](#1-install-the-prerequisites)
- [2. Get the code](#2-get-the-code)
- [3. Get a free AI key](#3-get-a-free-ai-key)
- [4. Configure `.env`](#4-configure-env)
- [5. Install dependencies](#5-install-dependencies)
- [6. Start VoxNote](#6-start-voxnote)
- [7. Your first course (walkthrough)](#7-your-first-course-walkthrough)
- [8. Updating to the latest version](#8-updating-to-the-latest-version)
- [9. Running with Docker instead](#9-running-with-docker-instead)
- [10. Stopping, resetting, and where data lives](#10-stopping-resetting-and-where-data-lives)
- [11. Troubleshooting](#11-troubleshooting)

---

## 1. Install the prerequisites

| Tool | Version | Check it with | Get it |
|---|---|---|---|
| **Git** | any | `git --version` | https://git-scm.com/downloads |
| **Python** | 3.11 or newer | `python --version` (Windows) / `python3 --version` | https://www.python.org/downloads/ (Windows: tick **"Add python.exe to PATH"**) |
| **Node.js** | 18 or newer (20/22 recommended) | `node --version` | https://nodejs.org (LTS) |
| **ffmpeg** | optional | `ffmpeg -version` | needed only to transcribe long videos **without captions** |

Install ffmpeg (optional):

- **Windows:** `winget install Gyan.FFmpeg` (then open a new terminal)
- **macOS:** `brew install ffmpeg`
- **Ubuntu/Debian:** `sudo apt install ffmpeg`

> Documentation courses and videos that already have captions work **without** ffmpeg.

---

## 2. Get the code

```bash
git clone https://github.com/ayasserrr/VoxNote.git
cd VoxNote
```

(If you already cloned it earlier, see [Updating](#8-updating-to-the-latest-version).)

---

## 3. Get a free AI key

VoxNote uses **only free AI models**. You don't need a paid key or a credit card. You need **at least one** free key;
**two is better**, because VoxNote automatically switches to the other one when a free tier reaches its limit.

| Provider | Why | Get the key (free) |
|---|---|---|
| **Groq** (recommended) | No credit card. Very fast. The same key also gives free speech-to-text (Whisper) for videos without captions. | https://console.groq.com/keys → sign in → *Create API Key* (starts with `gsk_`) |
| **Google Gemini** | No credit card. Excellent Arabic. (Not offered in the EU/UK/CH.) | https://aistudio.google.com/apikey → *Create API key* (starts with `AIza`) |
| Cerebras | No card, very fast | https://cloud.cerebras.ai |
| Mistral | Free "Experiment" plan (asks for a phone number, no card) | https://console.mistral.ai/api-keys |
| OpenRouter | `:free` models (about 50 requests/day) | https://openrouter.ai/keys |
| Ollama | Runs 100% on your computer, unlimited, no account | https://ollama.com/download, then `ollama pull qwen2.5:7b` |

You do **not** need to choose model names. VoxNote finds the current free models of each provider automatically. Free models
get retired every few months, and VoxNote switches to the replacement by itself.

No key yet? You can still try the app with the built-in **offline demo model** (`LLM_PROVIDERS=mock`, see below).
Its output is low quality on purpose. It is only there so you can explore.

---|---|---|
| **Groq** (recommended) | Very fast, free tier, **and** the same key gives free speech-to-text (Whisper) for videos without captions | https://console.groq.com/keys → *Create API Key* (starts with `gsk_`) |
| **Google Gemini** | Free tier, large context, excellent Arabic | https://aistudio.google.com/apikey → *Create API key* (starts with `AIza`) |
| OpenRouter | Many `:free` models, good fallback | https://openrouter.ai/keys |
| Ollama | Runs 100% on your computer, unlimited, no key | https://ollama.com/download, then `ollama pull qwen2.5:7b` |

No key yet? You can still try the whole app with the built-in **offline demo model** (`LLM_PROVIDERS=mock`, see below).
Its output is low quality on purpose. It is only there so you can explore the app.

---

## 4. Configure `.env`

Create your settings file from the template:

- **macOS / Linux:** `cp .env.example .env`
- **Windows (PowerShell):** `Copy-Item .env.example .env`

Open `.env` in any editor and paste your key(s):

```ini
GROQ_API_KEY=gsk_your_key_here
GEMINI_API_KEY=AIza_your_key_here      # optional second free provider
LLM_MIN_INTERVAL=2                     # gentle on free-tier rate limits
```

Leave all the `*_MODEL=auto` lines as they are. VoxNote then picks the current free models automatically.

Optional:

```ini
# Offline demo (no keys at all):
LLM_PROVIDERS=mock

# Prefer Gemini first (great for Arabic courses):
LLM_PROVIDERS=gemini,groq,openrouter

# Fully local with Ollama:
LLM_PROVIDERS=ollama
OLLAMA_ENABLED=true
OLLAMA_MODEL=qwen2.5:7b

# For anything other than a personal local install, change this:
JWT_SECRET=some-long-random-string
```

Every option is explained inside `.env.example`.

---

## 5. Install dependencies

### macOS / Linux / WSL (one command)

```bash
./scripts/setup.sh
```

This creates a Python virtual environment in `backend/.venv`, installs the backend packages, and installs the frontend packages.
It takes about a minute.

### Windows (PowerShell, one command)

```powershell
./scripts/setup.ps1
```

If PowerShell refuses to run scripts, run this once and try again:
`Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`

### Manual (any OS)

```bash
# backend
cd backend
python -m venv .venv
# Windows:      .venv\Scripts\activate
# macOS/Linux:  source .venv/bin/activate
pip install -r requirements.txt
cd ..

# frontend
cd frontend
npm install
cd ..
```

---

## 6. Start VoxNote

### macOS / Linux / WSL

```bash
./scripts/dev.sh
```

This starts both the API and the web app. Press **Ctrl+C** to stop both.

### Windows (one command)

```powershell
./scripts/dev.ps1
```

This opens two windows, one for the API and one for the web app. Close both to stop.

Or start the two parts yourself in two terminals. Terminal 1 (API):

```powershell
cd backend
.venv\Scripts\activate
uvicorn app.main:app --reload --port 8000
```

Terminal 2 (web app):

```powershell
cd frontend
npm run dev
```

### Open it

| What | URL |
|---|---|
| **The app** | **http://localhost:5173** |
| API documentation (Swagger) | http://localhost:8000/docs |
| Health check | http://localhost:8000/api/health → `{"status":"ok"}` |

On first start the database (a single SQLite file) is created automatically. You should see
`Running upgrade -> 0001 … 0002 … 0003` in the API terminal, then `Application startup complete`.

Then:

1. Open http://localhost:5173 and click **Create one** to register. The account is stored only on your computer.
2. Go to **Settings** and click **Test my AI keys**. Each free model should show a green ✓.
   - If a provider shows "no key", fix `.env` (in the project root) and restart the API.
   - You can run the same check in a terminal:
     ```bash
     cd backend
     .venv/bin/python -m app.check_ai        # Windows: .venv\Scripts\python -m app.check_ai
     ```

---

## 7. Your first course (walkthrough)

### Learn from documentation

1. Click **New → Documentation**. You can also paste the URL straight into the dashboard box.
2. Paste the URL where the docs **start**, for example:
   - `https://docs.python.org/3/tutorial/`
   - `https://fastapi.tiangolo.com/tutorial/`
   - `https://flask.palletsprojects.com/en/stable/tutorial/`
3. Choose your **level** and **teaching language**, and set **maximum pages** (start with 20–40 for a first try). Keep
   **"Only this section"** enabled.
4. Click **Read docs & build my course**. You will see live progress: *Reading documentation (N pages found)* →
   *Designing your course*.
5. Click **Open my course**. You get modules and lessons. Only lesson 1 is unlocked at first.
6. **Learn:** read the simple explanation, the analogy, the worked example and the key points. You can:
   - click **Explain it more simply** if it's too hard,
   - open **Ask the tutor** to ask questions about this lesson,
   - write your own **notes** (they save automatically).
7. **Practice:** click **I'm ready — test me** and answer 5 questions (multiple choice, true/false, short answer).
8. **Result:** each answer is corrected with the right answer, an explanation, and AI feedback on what you wrote.
   - Score **≥ 70%**: the lesson is completed and the next one unlocks.
   - Below 70%: review the lesson, retry, or ask for **new questions**.
9. Questions you get wrong go into **Review** (sidebar). It uses spaced repetition: they come back after 10 minutes,
   then 1, 3, 7 and 16 days, until you master them.
10. After the last lesson, the **final exam** unlocks: a course recap plus a 10-question exam. Pass it to earn your
    **certificate of completion**.
11. The **Dashboard** shows your daily **streak**, XP, lessons completed, certificates and *Continue learning*.

### Learn from YouTube

1. **New → YouTube**, then paste a video or playlist URL (a preview appears).
2. Choose the document language and detail level, then click **Start processing**. Each video shows live progress.
3. Download the **PDF / Markdown** for each video and the combined **playlist book**, or read the notes in the app.
4. Click **Learn this as a course** to get lessons and quizzes built from the videos (every lesson links to the exact moment).
5. Use **Ask** to ask questions across all your videos and docs, with citations.

---

## 8. Updating to the latest version

From the `VoxNote` folder:

```bash
git pull
```

Then reinstall the dependencies (new versions sometimes add packages):

- **macOS / Linux:** `./scripts/setup.sh`
- **Windows:** `./scripts/setup.ps1`
- or manually: `cd backend && pip install -r requirements.txt` (with the venv activated) and `cd frontend && npm install`

Restart VoxNote. **Database upgrades are automatic** and keep your data. Your `.env` is never overwritten, but compare it
with `.env.example` to see new options.

---

## 9. Running with Docker instead

If you have Docker Desktop, you can run the full production-style stack (PostgreSQL, Redis, API, Celery worker and the web app
served by nginx) with one command:

```bash
cp .env.example .env        # add your key(s) as in step 4
docker compose up --build
```

- App: **http://localhost:3000**
- API docs: http://localhost:8000/docs
- Stop: `Ctrl+C`, then `docker compose down`. Add `-v` to also delete the data.
- More workers: `docker compose up --scale worker=3`
- Monitoring: `docker compose --profile monitoring up`, then Prometheus at http://localhost:9090

---

## 10. Stopping, resetting, and where data lives

- **Stop:** press `Ctrl+C` in the terminal(s).
- **Local data:** `backend/data/voxnote.db` (database) and `backend/data/storage/` (PDFs, Markdown, uploads).
- **Start fresh:** stop VoxNote and delete the `backend/data/` folder.
- **Reset a single course:** open the course and click **Reset progress**.
- Background jobs that were running when you stopped are resumed automatically on the next start.

---

## 11. Troubleshooting

| Problem | Fix |
|---|---|
| `python` / `python3` not found | Install Python 3.11+. On Windows, re-run the installer and tick *Add to PATH*. |
| `npm` not found | Install Node.js LTS and open a new terminal. |
| Web app shows network errors | The API isn't running. Check the API terminal and open http://localhost:8000/api/health. |
| "No LLM provider configured" | Put a key in `.env` (in the **project root**, next to `README.md`) and **restart the API**. Check **Settings**. |
| Lessons fail with HTTP 429 / take long | Free-tier rate limit. Set `LLM_MIN_INTERVAL=3`, add a second provider key, and click *Try again*. |
| Docs crawl finds almost no text | The site renders its content with JavaScript. Try another docs URL (a static mirror, the GitHub README, or a deeper section). |
| Crawl wanders outside the docs | Keep *Only this section* enabled and start from the docs root (e.g. `/docs/`, `/tutorial/`). |
| YouTube: "No transcript available" | The video has no captions: add `GROQ_API_KEY` (free Whisper) and install ffmpeg. On servers/VPNs, YouTube may block the IP: run locally or set `YOUTUBE_PROXY_URL`. |
| YouTube suddenly stops working | Update the downloaders: `pip install -U yt-dlp youtube-transcript-api` (venv activated). |
| Port 8000 or 5173 already in use | Stop the other program, or run the API with `--port 8001` and start the UI with `VITE_BACKEND_URL=http://localhost:8001 npm run dev`. |
| Windows: `scripts\setup.ps1 cannot be loaded` | `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` |

Still stuck? Run the tests to check your installation:

```bash
cd backend && .venv/bin/python -m pytest -q      # Windows: .venv\Scripts\python -m pytest -q
```

All tests run offline. They need no API keys and no internet.
