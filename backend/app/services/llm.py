"""Provider-agnostic LLM client focused on FREE models.

Every supported provider exposes an OpenAI-compatible `/chat/completions`
endpoint, so one small httpx client covers all of them:

| provider      | free option                                   | key from                          |
|---------------|-----------------------------------------------|-----------------------------------|
| groq          | llama-3.3-70b-versatile (free tier)           | https://console.groq.com/keys     |
| gemini        | gemini-2.5-flash (free tier)                  | https://aistudio.google.com/apikey|
| openrouter    | `openrouter/free` or any `:free` model        | https://openrouter.ai/keys        |
| ollama        | any local model, 100% free & offline          | https://ollama.com                |
| openai_compat | LM Studio, vLLM, Together, ...                | -                                 |
| mock          | deterministic offline extractor (tests/demo)  | -                                 |

Providers are tried in the order of LLM_PROVIDERS; when one is rate limited
or down the client falls back to the next configured provider. Responses are
parsed as JSON and validated with Pydantic, with one automatic "repair" round
when a model returns malformed JSON.
"""

from __future__ import annotations

import json
import logging
import re
import threading
import time
from dataclasses import dataclass, field
from typing import Any, TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from app.config import settings
from app.metrics import LLM_REQUESTS, LLM_TOKENS

log = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class LLMError(Exception):
    pass


class NoProviderConfigured(LLMError):
    pass


@dataclass
class Provider:
    name: str
    base_url: str
    model: str
    api_key: str | None = None
    headers: dict[str, str] = field(default_factory=dict)
    supports_json_mode: bool = True


@dataclass
class LLMResponse:
    text: str
    provider: str
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0


@dataclass
class UsageTracker:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    calls: int = 0
    providers: set[str] = field(default_factory=set)
    last_provider: str | None = None
    last_model: str | None = None

    def add(self, r: LLMResponse) -> None:
        self.prompt_tokens += r.prompt_tokens
        self.completion_tokens += r.completion_tokens
        self.calls += 1
        self.providers.add(r.provider)
        self.last_provider, self.last_model = r.provider, r.model


def configured_providers() -> list[Provider]:
    s = settings
    out: list[Provider] = []
    for name in s.provider_list:
        if name == "groq" and s.groq_api_key:
            out.append(Provider("groq", s.groq_base_url, s.groq_model, s.groq_api_key))
        elif name == "gemini" and s.gemini_api_key:
            out.append(Provider("gemini", s.gemini_base_url, s.gemini_model, s.gemini_api_key))
        elif name == "openrouter" and s.openrouter_api_key:
            out.append(
                Provider(
                    "openrouter",
                    s.openrouter_base_url,
                    s.openrouter_model,
                    s.openrouter_api_key,
                    headers={"HTTP-Referer": "https://github.com/ayasserrr/VoxNote", "X-Title": "VoxNote"},
                )
            )
        elif name == "ollama" and s.ollama_enabled:
            out.append(Provider("ollama", s.ollama_base_url, s.ollama_model, None))
        elif name == "openai_compat" and s.openai_compat_base_url and s.openai_compat_model:
            out.append(
                Provider("openai_compat", s.openai_compat_base_url, s.openai_compat_model, s.openai_compat_api_key)
            )
        elif name == "mock":
            out.append(Provider("mock", "", "voxnote-mock-1"))
    return out


def provider_status() -> list[dict[str, Any]]:
    """Which providers are configured (for the settings page)."""
    active = {p.name: p for p in configured_providers()}
    rows = []
    for name, model in (
        ("groq", settings.groq_model),
        ("gemini", settings.gemini_model),
        ("openrouter", settings.openrouter_model),
        ("ollama", settings.ollama_model),
        ("openai_compat", settings.openai_compat_model),
        ("mock", "voxnote-mock-1"),
    ):
        rows.append(
            {
                "name": name,
                "model": active[name].model if name in active else model,
                "configured": name in active,
                "in_chain": name in settings.provider_list,
            }
        )
    return rows


# --------------------------------------------------------------- JSON utils
_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)
_TRAILING_COMMA_RE = re.compile(r",\s*([}\]])")


def extract_json(text: str) -> Any:
    """Best-effort extraction of a JSON object from model output."""
    if not text:
        raise ValueError("empty response")
    t = text.strip()
    t = re.sub(r"<think>.*?</think>", "", t, flags=re.DOTALL).strip()  # reasoning models
    t = _FENCE_RE.sub("", t).strip()
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        pass
    start, end = t.find("{"), t.rfind("}")
    if start == -1 or end <= start:
        raise ValueError("no JSON object found in response")
    candidate = t[start : end + 1]
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        return json.loads(_TRAILING_COMMA_RE.sub(r"\1", candidate))


# ------------------------------------------------------------------ client
class LLMClient:
    _lock = threading.Lock()
    _last_call = 0.0

    def __init__(self, providers: list[Provider] | None = None, usage: UsageTracker | None = None):
        self.providers = providers if providers is not None else configured_providers()
        self.usage = usage or UsageTracker()
        self._disabled: set[str] = set()  # providers that hard-failed during this run

    @property
    def available(self) -> bool:
        return bool(self.providers)

    def _throttle(self) -> None:
        if settings.llm_min_interval <= 0:
            return
        with LLMClient._lock:
            wait = LLMClient._last_call + settings.llm_min_interval - time.monotonic()
            if wait > 0:
                time.sleep(wait)
            LLMClient._last_call = time.monotonic()

    def _call_provider(
        self, p: Provider, messages: list[dict[str, str]], json_mode: bool, max_tokens: int, temperature: float
    ) -> LLMResponse:
        if p.name == "mock":
            from app.services.mock_llm import mock_complete

            text = mock_complete(messages, json_mode)
            return LLMResponse(text, "mock", p.model, sum(len(m["content"]) // 4 for m in messages), len(text) // 4)

        url = f"{p.base_url.rstrip('/')}/chat/completions"
        headers = {"Content-Type": "application/json", **p.headers}
        if p.api_key:
            headers["Authorization"] = f"Bearer {p.api_key}"
        body: dict[str, Any] = {
            "model": p.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        use_json = json_mode and p.supports_json_mode
        if use_json:
            body["response_format"] = {"type": "json_object"}

        last_exc: Exception | None = None
        for attempt in range(1, settings.llm_max_retries + 1):
            self._throttle()
            try:
                resp = httpx.post(url, headers=headers, json=body, timeout=settings.llm_timeout)
            except httpx.HTTPError as exc:
                last_exc = exc
                time.sleep(min(2**attempt, 30))
                continue
            if resp.status_code == 400 and use_json and "response_format" in resp.text:
                # Model does not support JSON mode -> retry without it.
                body.pop("response_format", None)
                use_json = False
                continue
            if resp.status_code in (429, 500, 502, 503, 504):
                retry_after = resp.headers.get("retry-after")
                try:
                    wait = float(retry_after) if retry_after else 2**attempt * 3
                except ValueError:
                    wait = 2**attempt * 3
                LLM_REQUESTS.labels(p.name, f"http_{resp.status_code}").inc()
                last_exc = LLMError(f"{p.name} HTTP {resp.status_code}: {resp.text[:200]}")
                if wait > 90:  # daily quota exhausted -> fall back to next provider
                    break
                log.warning("%s returned %s, retrying in %.1fs", p.name, resp.status_code, wait)
                time.sleep(wait)
                continue
            if resp.status_code >= 400:
                LLM_REQUESTS.labels(p.name, f"http_{resp.status_code}").inc()
                raise LLMError(f"{p.name} HTTP {resp.status_code}: {resp.text[:300]}")
            data = resp.json()
            try:
                text = data["choices"][0]["message"].get("content") or ""
            except (KeyError, IndexError, TypeError) as exc:
                raise LLMError(f"{p.name}: unexpected response shape") from exc
            usage = data.get("usage") or {}
            r = LLMResponse(
                text=text,
                provider=p.name,
                model=data.get("model") or p.model,
                prompt_tokens=int(usage.get("prompt_tokens") or 0),
                completion_tokens=int(usage.get("completion_tokens") or 0),
            )
            LLM_REQUESTS.labels(p.name, "ok").inc()
            LLM_TOKENS.labels(p.name, "prompt").inc(r.prompt_tokens)
            LLM_TOKENS.labels(p.name, "completion").inc(r.completion_tokens)
            return r
        raise LLMError(f"{p.name}: giving up after retries ({last_exc})")

    def complete(
        self,
        messages: list[dict[str, str]],
        *,
        json_mode: bool = False,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> LLMResponse:
        if not self.providers:
            raise NoProviderConfigured(
                "No LLM provider configured. Add a free key to .env, e.g. GROQ_API_KEY "
                "(https://console.groq.com/keys) or GEMINI_API_KEY (https://aistudio.google.com/apikey), "
                "or set LLM_PROVIDERS=mock for an offline demo."
            )
        errors: list[str] = []
        for p in self.providers:
            if p.name in self._disabled:
                continue
            try:
                r = self._call_provider(
                    p,
                    messages,
                    json_mode,
                    max_tokens or settings.llm_max_output_tokens,
                    settings.llm_temperature if temperature is None else temperature,
                )
                self.usage.add(r)
                return r
            except LLMError as exc:
                log.warning("LLM provider %s failed: %s", p.name, exc)
                errors.append(str(exc))
                if "HTTP 401" in str(exc) or "HTTP 403" in str(exc):
                    self._disabled.add(p.name)
        raise LLMError("All LLM providers failed: " + " | ".join(errors))

    def structured(
        self,
        system: str,
        user: str,
        schema: type[T],
        *,
        max_tokens: int | None = None,
    ) -> T:
        """Ask for JSON matching `schema`; validate; one repair round on failure."""
        messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
        r = self.complete(messages, json_mode=True, max_tokens=max_tokens)
        try:
            return schema.model_validate(extract_json(r.text))
        except (ValueError, ValidationError) as exc:
            log.info("invalid JSON from %s, attempting repair: %s", r.provider, str(exc)[:200])
            repair = messages + [
                {"role": "assistant", "content": r.text[:6000]},
                {
                    "role": "user",
                    "content": "Your previous answer was not valid JSON for the requested schema "
                    f"({str(exc)[:300]}). Return ONLY the corrected JSON object, nothing else.",
                },
            ]
            r2 = self.complete(repair, json_mode=True, max_tokens=max_tokens)
            try:
                return schema.model_validate(extract_json(r2.text))
            except (ValueError, ValidationError) as exc2:
                raise LLMError(f"Model returned invalid structured output: {str(exc2)[:300]}") from exc2
