"""Free model discovery.

Free models get retired and renamed every few months. Groq retired
`llama-3.3-70b-versatile` on 16 Aug 2026, and Google retired the Gemini 2.5
models in Oct 2026. So VoxNote does not hard-code model names. It asks each
provider for its *live* model list (`GET /models`, OpenAI-compatible), keeps
the chat models, and ranks them with preference patterns. The result is cached.

Set `<PROVIDER>_MODEL` to an explicit comma-separated list to override this.
"""

from __future__ import annotations

import logging
import re
import threading
import time
from dataclasses import dataclass

import httpx

log = logging.getLogger(__name__)

CACHE_SECONDS = 6 * 3600

_COMMON_EXCLUDE = (
    r"(whisper|tts|speech|audio|guard|embed|moderation|image|ocr|transcri|realtime|live|rerank|safety|"
    r"orpheus|playai|distil|veo|imagen|lyria|aqa|learnlm|computer-use|robotics|native)"
)


@dataclass(frozen=True)
class FreeProviderSpec:
    name: str
    label: str
    signup_url: str
    note: str
    preferences: tuple[str, ...]  # regexes, best first
    fallback: tuple[str, ...]  # used when the live list cannot be read
    exclude: str = _COMMON_EXCLUDE


SPECS: dict[str, FreeProviderSpec] = {
    "groq": FreeProviderSpec(
        name="groq",
        label="Groq",
        signup_url="https://console.groq.com/keys",
        note="Free tier, no credit card. Very fast. The same key gives free Whisper speech-to-text. "
             "Each model has its own free quota, so VoxNote rotates between several.",
        preferences=(r"^openai/gpt-oss-120b$", r"^qwen/qwen3", r"^moonshotai/kimi", r"^meta-llama/llama-4-maverick",
                     r"^meta-llama/llama-4", r"^openai/gpt-oss-20b$", r"llama"),
        fallback=("openai/gpt-oss-120b", "openai/gpt-oss-20b"),
        exclude=_COMMON_EXCLUDE + r"|compound|allam|prompt",
    ),
    "gemini": FreeProviderSpec(
        name="gemini",
        label="Google Gemini",
        signup_url="https://aistudio.google.com/apikey",
        note="Free tier, no credit card (not available in the EU/UK/CH). Large context, excellent Arabic. "
             "The free tier may use prompts to improve Google products.",
        preferences=(r"^gemini-flash-latest$", r"^gemini-[\d.]+-flash$", r"^gemini-[\d.]+-flash-preview",
                     r"^gemini-flash-lite-latest$", r"^gemini-[\d.]+-flash-lite", r"^gemma-3-27b", r"^gemini"),
        fallback=("gemini-flash-latest", "gemini-flash-lite-latest"),
        exclude=_COMMON_EXCLUDE + r"|pro|thinking|exp-|deep-research|nano|banana",
    ),
    "cerebras": FreeProviderSpec(
        name="cerebras",
        label="Cerebras",
        signup_url="https://cloud.cerebras.ai",
        note="Free tier on many accounts (no card); extremely fast. Shorter context on the free tier.",
        preferences=(r"^gpt-oss-120b$", r"^qwen-3", r"^llama-4", r"^llama", r"."),
        fallback=("gpt-oss-120b",),
    ),
    "mistral": FreeProviderSpec(
        name="mistral",
        label="Mistral",
        signup_url="https://console.mistral.ai/api-keys",
        note="Free 'Experiment' plan: no credit card, phone verification. Prompts may be used for training.",
        preferences=(r"^mistral-small-\d", r"^mistral-small", r"^mistral-medium", r"^magistral-small",
                     r"^open-mistral-nemo", r"^ministral-8b", r"^mistral-large"),
        fallback=("mistral-small-latest",),
        exclude=_COMMON_EXCLUDE + r"|codestral|devstral|pixtral|voxtral|saba",
    ),
    "openrouter": FreeProviderSpec(
        name="openrouter",
        label="OpenRouter",
        signup_url="https://openrouter.ai/keys",
        note="':free' models at $0. Without ever buying credits the limit is ~50 requests/day, "
             "so it is used as a last fallback.",
        preferences=(r"^openrouter/free$",),
        fallback=("openrouter/free",),
    ),
    "ollama": FreeProviderSpec(
        name="ollama",
        label="Ollama (local)",
        signup_url="https://ollama.com/download",
        note="Runs on your own computer: unlimited, private, offline. Quality depends on the model size.",
        preferences=(r"qwen3", r"qwen2\.5", r"gpt-oss", r"llama3", r"gemma", r"mistral", r"."),
        fallback=("qwen2.5:7b",),
    ),
}

_cache: dict[str, tuple[float, list[str]]] = {}
_lock = threading.Lock()


def _strip(model_id: str) -> str:
    return model_id.removeprefix("models/")


def list_models(base_url: str, api_key: str | None, provider: str, timeout: float = 15.0) -> list[str]:
    """Return model ids from an OpenAI-compatible `GET /models` endpoint (cached)."""
    key = f"{provider}|{base_url}|{(api_key or '')[-6:]}"
    with _lock:
        hit = _cache.get(key)
        if hit and time.monotonic() - hit[0] < CACHE_SECONDS:
            return hit[1]
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    resp = httpx.get(f"{base_url.rstrip('/')}/models", headers=headers, timeout=timeout)
    resp.raise_for_status()
    data = resp.json()
    items = data.get("data") if isinstance(data, dict) else data
    ids: list[str] = []
    for m in items or []:
        if not isinstance(m, dict):
            continue
        if m.get("active") is False:  # Groq marks retired models inactive
            continue
        mid = m.get("id") or m.get("name")
        if mid:
            ids.append(_strip(str(mid)))
    with _lock:
        _cache[key] = (time.monotonic(), ids)
    return ids


def rank_models(spec: FreeProviderSpec, available: list[str], limit: int) -> list[str]:
    exclude = re.compile(spec.exclude, re.I)
    candidates = [m for m in available if not exclude.search(m)]
    ranked: list[str] = []
    for pattern in spec.preferences:
        rx = re.compile(pattern, re.I)
        for m in sorted(candidates, key=lambda x: (len(x), x)):
            if rx.search(m) and m not in ranked:
                ranked.append(m)
        if len(ranked) >= limit:
            break
    return ranked[:limit]


def resolve_models(provider: str, configured: str | None, base_url: str, api_key: str | None,
                   limit: int = 3) -> tuple[list[str], str]:
    """Return (models, how) where how is 'configured', 'discovered' or 'fallback'."""
    if configured and configured.strip().lower() != "auto":
        return [m.strip() for m in configured.split(",") if m.strip()], "configured"
    spec = SPECS.get(provider)
    if spec is None:
        return [], "fallback"
    if provider == "openrouter":
        return list(spec.fallback), "fallback"
    try:
        available = list_models(base_url, api_key, provider)
        ranked = rank_models(spec, available, limit)
        if ranked:
            return ranked, "discovered"
    except Exception as exc:  # noqa: BLE001 - network/auth problems -> safe defaults
        log.info("could not list %s models (%s); using defaults", provider, exc)
    return list(spec.fallback)[:limit], "fallback"


def clear_cache() -> None:
    with _lock:
        _cache.clear()
