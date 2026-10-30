# Free AI providers for VoxNote

**VoxNote only uses free AI.** You don't need a paid API key or a credit card. You need **one** free key, and **two or more**
is better: when one free tier reaches its limit, VoxNote automatically moves to the next provider.

> Checked in **October 2026**. Free tiers and model names change often, which is why VoxNote **discovers the free models
> automatically** (see below). Always confirm limits on the provider's own page.

## Quick recommendation

| Goal | Put in `.env` |
|---|---|
| Easiest start | `GROQ_API_KEY` (also enables free speech-to-text) |
| Best free setup | `GROQ_API_KEY` + `GEMINI_API_KEY` |
| Arabic-heavy courses | `LLM_PROVIDERS=gemini,groq,...` with both keys |
| No account at all / fully private | Ollama on your computer (`OLLAMA_ENABLED=true`) |
| Just look around | `LLM_PROVIDERS=mock` (offline demo, low quality) |

## The providers

| Provider | Free terms (Oct 2026) | Sign up | `.env` |
|---|---|---|---|
| **Groq** ⭐ | Free tier, **no credit card**. Rate-limited per model (VoxNote rotates several models to multiply the quota). Also **free Whisper** speech-to-text. | https://console.groq.com/keys | `GROQ_API_KEY=` |
| **Google Gemini** | Free tier, **no credit card**, Flash / Flash-Lite models, large context, strong Arabic. Not offered in the EU/UK/CH. Free-tier prompts may be used to improve Google products. | https://aistudio.google.com/apikey | `GEMINI_API_KEY=` |
| **Cerebras** | Free tier on many accounts (no card), extremely fast, shorter context on the free tier. Terms have varied, so test it with *Test my AI keys*. | https://cloud.cerebras.ai | `CEREBRAS_API_KEY=` |
| **Mistral** | Free **Experiment** plan: **no card**, phone verification, roughly 1 request/second. Prompts may be used for training. | https://console.mistral.ai/api-keys | `MISTRAL_API_KEY=` |
| **OpenRouter** | `:free` models at $0. About **50 requests/day** if you have never bought credits, so it is used as a last fallback. | https://openrouter.ai/keys | `OPENROUTER_API_KEY=` |
| **Ollama** | Runs on **your computer**: unlimited, offline, private. Needs a decent CPU/GPU and RAM. | https://ollama.com/download | `OLLAMA_ENABLED=true` |
| OpenAI-compatible server | Anything you host yourself (LM Studio, llama.cpp, vLLM) | – | `OPENAI_COMPAT_BASE_URL=`, `OPENAI_COMPAT_MODEL=` |

## Automatic free-model discovery

Free models are retired regularly:

- Groq **retired `llama-3.3-70b-versatile` on 16 Aug 2026** and recommends `openai/gpt-oss-120b`.
- Google **retired the Gemini 2.5 models in Oct 2026**. The `gemini-flash-latest` alias always points to the newest Flash.

So the model settings default to **`auto`**. On startup (and every 6 hours) VoxNote:

1. calls each provider's live model list (`GET /models`),
2. drops retired/inactive models and non-chat models (Whisper, TTS, guards, embeddings, image, audio…),
3. ranks the remaining models with a preference list (for example Groq: `gpt-oss-120b` → `qwen3` → `kimi` → `llama-4` → `gpt-oss-20b`;
   Gemini: `gemini-flash-latest` → newest Flash → Flash-Lite),
4. keeps the best `LLM_MODELS_PER_PROVIDER` (default 3) and puts them all in the fallback chain.

During a request:

- **Rate limited (429):** wait for `Retry-After`, or move to the next model or provider if the wait is long (daily quota used up).
- **Model retired (404 / "decommissioned"):** skip that model and try the next one. No restart needed.
- **Request too large for the free tier (413):** retry with a smaller output budget.
- **Reasoning models** (gpt-oss, Gemini 3) use `reasoning_effort=low` to stay fast and inside the free limits. If a model rejects the
  parameter, the request is retried without it. If the reasoning used up the whole token budget, the request is retried with more room.
- **Bad key (401/403):** that provider is skipped for the rest of the job.

To pin specific models, use a list instead of `auto`, for example `GROQ_MODEL=openai/gpt-oss-120b,qwen/qwen3-32b`.

## Checking your keys

- In the app, go to **Settings → Test my AI keys**. It shows each provider, the models it picked, and a live test of each model.
- In a terminal:

  ```bash
  cd backend
  .venv/bin/python -m app.check_ai          # Windows: .venv\Scripts\python -m app.check_ai
  ```

## Speech-to-text (only for videos without captions, and for uploads)

| Option | Cost | Setup |
|---|---|---|
| YouTube captions | free | automatic, always tried first |
| Groq Whisper large-v3 (falls back to large-v3-turbo) | free tier (about 2,000 requests/day; long audio is split into 10-minute chunks) | `GROQ_API_KEY`, ffmpeg installed |
| faster-whisper on your computer | free | `pip install faster-whisper`, `STT_PROVIDER=local` |

Documentation courses do not need speech-to-text at all.

## Staying inside the free limits

- A documentation lesson costs **1 LLM call** (plus 1 for grading if you write a short answer). Lessons are generated only when you
  open them, plus the next one in advance.
- A video takes about one call per 10–12 minutes of speech, plus 1 per video and 1 per playlist.
- Set `LLM_MIN_INTERVAL=2..4` to spread the calls out.
- Use two providers. A daily quota running out on one then just switches to the other.
- Transcripts are cached; *Regenerate* only re-runs the LLM.
