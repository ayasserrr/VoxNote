# Free AI providers for VoxNote

VoxNote only needs two capabilities, and both are available for free:

1. **An LLM** that can return JSON (knowledge extraction, synthesis, Q&A)
2. **Speech-to-text**, only for videos without captions and for uploaded files

> Free-tier quotas and model lists change often. Treat the numbers below as a guide (checked October 2026) and confirm them on
> each provider's page. Every model name can be changed in `.env`.

## LLM providers

### Groq (recommended first choice)
- Key: https://console.groq.com/keys (no credit card)
- Free tier with rate limits (roughly 30 requests/min and ~1,000 requests/day for Llama 3.3 70B; tokens-per-minute limits also apply).
- Very fast inference, which suits playlists with many chunks.
- Models: `llama-3.3-70b-versatile` (default), `openai/gpt-oss-120b`, `qwen/qwen3-32b`, `meta-llama/llama-4-scout-17b-16e-instruct`, `llama-3.1-8b-instant`.
- The **same key** gives free **Whisper large-v3** transcription (`STT_PROVIDER=groq`).
- Live list: https://console.groq.com/docs/models

### Google Gemini
- Key: https://aistudio.google.com/apikey (no credit card for the free tier)
- OpenAI-compatible endpoint `https://generativelanguage.googleapis.com/v1beta/openai/`, which VoxNote uses directly.
- Models: `gemini-2.5-flash` (default), `gemini-2.5-flash-lite` (higher limits).
- Very large context window and strong Arabic, including Egyptian dialect. A very good choice for Arabic courses: set `LLM_PROVIDERS=gemini,groq`.
- Note: content sent on the free tier may be used by Google to improve its products. Use a paid tier for sensitive material.

### OpenRouter
- Key: https://openrouter.ai/keys
- Many models with a `:free` suffix; `openrouter/free` routes to an available free model automatically.
- Free models are rate-limited (about 20 requests/min) and can be busy, so use OpenRouter as a fallback.
- Some free providers may train on prompts; check https://openrouter.ai/models?max_price=0

### Ollama (local, unlimited)
- Install: https://ollama.com/download, then `ollama pull qwen2.5:7b` (or `llama3.1:8b`, `qwen2.5:14b` if you have the RAM/VRAM).
- `.env`: `OLLAMA_ENABLED=true`, `OLLAMA_MODEL=qwen2.5:7b`
- No limits and works offline; quality depends on the model size. Qwen 2.5 handles Arabic reasonably well.

### Any OpenAI-compatible server
`OPENAI_COMPAT_BASE_URL`, `OPENAI_COMPAT_MODEL`, `OPENAI_COMPAT_API_KEY` work with LM Studio, vLLM, llama.cpp server, Together, etc.
Add `openai_compat` to `LLM_PROVIDERS`.

## Speech-to-text

| Option | Cost | Setup |
|---|---|---|
| Captions (YouTube) | free | automatic, tried first |
| Groq Whisper large-v3 | free tier (roughly 20 req/min, ~2,000 req/day; long audio is split into 10-minute chunks) | `GROQ_API_KEY`, `STT_PROVIDER=groq`, ffmpeg installed |
| faster-whisper (local) | free, uses your CPU/GPU | `pip install faster-whisper`, `STT_PROVIDER=local`, `LOCAL_WHISPER_MODEL=small` (or `medium`/`large-v3` for better Arabic) |

## Suggested configurations

**Best free quality (English and Arabic):**
```ini
LLM_PROVIDERS=gemini,groq,openrouter
GEMINI_API_KEY=...
GROQ_API_KEY=...
LLM_MIN_INTERVAL=2
```

**Fastest:**
```ini
LLM_PROVIDERS=groq,gemini
GROQ_API_KEY=...
```

**Fully offline / private:**
```ini
LLM_PROVIDERS=ollama
OLLAMA_ENABLED=true
STT_PROVIDER=local
```

## Staying inside free limits

- A comprehensive extraction makes roughly one LLM call per ~2,500 transcript tokens (about 10–12 minutes of speech), plus one call per
  video and one per playlist. A 1-hour lecture therefore takes about 6–8 calls.
- `LLM_MIN_INTERVAL=2..4` spreads the calls out; HTTP 429 responses are retried automatically, honouring `Retry-After`.
- *Standard* detail uses ~40% fewer calls (bigger chunks).
- Configure two providers so that a daily quota running out on one switches to the other instead of failing.
- Transcripts are cached per YouTube ID, and *Regenerate* only re-runs the LLM.
