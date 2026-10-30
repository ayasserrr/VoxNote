"""Provider-agnostic LLM client that uses only FREE models.

Every supported provider exposes an OpenAI-compatible `/chat/completions`
endpoint, so one small httpx client covers all of them:

| provider      | cost                                              | key from                            |
|---------------|---------------------------------------------------|-------------------------------------|
| groq          | free tier, no credit card                         | https://console.groq.com/keys       |
| gemini        | free tier, no credit card (not in EU/UK/CH)       | https://aistudio.google.com/apikey  |
| cerebras      | free tier, no credit card                         | https://cloud.cerebras.ai           |
| mistral       | free "Experiment" plan (phone verification)       | https://console.mistral.ai/api-keys |
| openrouter    | `:free` models at $0 (~50 requests/day)           | https://openrouter.ai/keys          |
| ollama        | runs locally: unlimited, offline                  | https://ollama.com                  |
| openai_compat | LM Studio, vLLM, llama.cpp, ...                   | -                                   |
| mock          | deterministic offline extractor (tests/demo)      | -                                   |

Model names are NOT hard-coded. `services/free_models.py` discovers the
currently available free models from each provider's live model list,
because free models get retired regularly. The chain holds one entry per
(provider, model), so when a model is rate limited, retired or out of quota,
the next one is used. Responses are parsed as JSON and validated with
Pydantic, with one automatic "repair" round for malformed JSON.
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


_PROVIDER_KEYS = {
    "groq": ("groq_api_key", "groq_base_url", "groq_model"),
    "gemini": ("gemini_api_key", "gemini_base_url", "gemini_model"),
    "cerebras": ("cerebras_api_key", "cerebras_base_url", "cerebras_model"),
    "mistral": ("mistral_api_key", "mistral_base_url", "mistral_model"),
    "openrouter": ("openrouter_api_key", "openrouter_base_url", "openrouter_model"),
}


def _provider_config(name: str) -> tuple[str | None, str | None, str | None, bool]:
    """(api_key, base_url, model_setting, enabled) for a provider name."""
    s = settings
    if name in _PROVIDER_KEYS:
        k, b, m = _PROVIDER_KEYS[name]
        key = getattr(s, k)
        return key, getattr(s, b), getattr(s, m), bool(key)
    if name == "ollama":
        return None, s.ollama_base_url, s.ollama_model, s.ollama_enabled
    if name == "openai_compat":
        return (s.openai_compat_api_key, s.openai_compat_base_url, s.openai_compat_model,
                bool(s.openai_compat_base_url and s.openai_compat_model))
    if name == "mock":
        return None, "", "voxnote-mock-1", True
    return None, None, None, False


def configured_providers() -> list[Provider]:
    """The fallback chain: one entry per (provider, model), in LLM_PROVIDERS order.

    Several free models per provider are included because free quotas are usually
    per model: when one model is rate limited, the next one still has quota.
    """
    from app.services.free_models import resolve_models

    out: list[Provider] = []
    for name in settings.provider_list:
        key, base, model_setting, enabled = _provider_config(name)
        if not enabled:
            continue
        if name == "mock":
            out.append(Provider("mock", "", "voxnote-mock-1"))
            continue
        if name == "openai_compat":
            models = [m.strip() for m in (model_setting or "").split(",") if m.strip()]
        else:
            models, _ = resolve_models(name, model_setting, base or "", key, settings.llm_models_per_provider)
        headers = {}
        if name == "openrouter":
            headers = {"HTTP-Referer": "https://github.com/ayasserrr/VoxNote", "X-Title": "VoxNote"}
        for m in models:
            out.append(Provider(name, base or "", m, key, headers=dict(headers)))
    return out


def provider_status() -> list[dict[str, Any]]:
    """Which free providers are configured and which models were selected (for the Settings page)."""
    from app.services.free_models import SPECS, resolve_models

    rows = []
    names = ["groq", "gemini", "cerebras", "mistral", "openrouter", "ollama", "openai_compat", "mock"]
    for name in names:
        key, base, model_setting, enabled = _provider_config(name)
        spec = SPECS.get(name)
        models: list[str] = []
        how = ""
        if enabled and name == "mock":
            models, how = ["voxnote-mock-1"], "built-in"
        elif enabled and name == "openai_compat":
            models, how = [m.strip() for m in (model_setting or "").split(",") if m.strip()], "configured"
        elif enabled:
            models, how = resolve_models(name, model_setting, base or "", key, settings.llm_models_per_provider)
        rows.append({
            "name": name,
            "label": spec.label if spec else name,
            "model": ", ".join(models) if models else (model_setting or ""),
            "models": models,
            "selection": how,
            "configured": enabled,
            "in_chain": name in settings.provider_list,
            "free": True,
            "signup_url": spec.signup_url if spec else "",
            "note": spec.note if spec else "",
        })
    return rows


def test_providers() -> list[dict[str, Any]]:
    """Send a tiny prompt to every configured provider/model and report the result."""
    results = []
    for p in configured_providers():
        client = LLMClient(providers=[p])
        t0 = time.monotonic()
        try:
            r = client._call_provider(p, [{"role": "user", "content": "Reply with exactly: OK"}],
                                      json_mode=False, max_tokens=300, temperature=0)
            results.append({"provider": p.name, "model": p.model, "ok": True, "reply": r.text.strip()[:60],
                            "seconds": round(time.monotonic() - t0, 2)})
        except Exception as exc:  # noqa: BLE001
            results.append({"provider": p.name, "model": p.model, "ok": False, "error": str(exc)[:300],
                            "seconds": round(time.monotonic() - t0, 2)})
    return results


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


def _is_reasoning_model(p: Provider) -> bool:
    m = p.model.lower()
    if p.name in {"groq", "cerebras"}:
        return "gpt-oss" in m
    return p.name == "gemini" and re.search(r"gemini-(3|flash-latest|flash-lite-latest)", m) is not None


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
        effort = settings.llm_reasoning_effort.lower()
        if effort and effort != "none" and _is_reasoning_model(p):
            body["reasoning_effort"] = effort

        last_exc: Exception | None = None
        for attempt in range(1, settings.llm_max_retries + 1):
            self._throttle()
            try:
                resp = httpx.post(url, headers=headers, json=body, timeout=settings.llm_timeout)
            except httpx.HTTPError as exc:
                last_exc = exc
                time.sleep(min(2**attempt, 30))
                continue
            if resp.status_code == 400:
                low = resp.text.lower()
                # Optional parameters a model may not support -> retry without them.
                if "reasoning_effort" in body and ("reasoning" in low or "unknown" in low or "unsupported" in low):
                    body.pop("reasoning_effort", None)
                    continue
                if use_json and ("response_format" in low or "json" in low):
                    body.pop("response_format", None)
                    use_json = False
                    continue
            if resp.status_code == 413 or (resp.status_code in (400, 429) and "too large" in resp.text.lower()):
                # Free tiers cap tokens per request/minute: shrink the output budget and retry.
                if body["max_tokens"] > 1500:
                    body["max_tokens"] = max(1500, body["max_tokens"] // 2)
                    continue
                raise LLMError(f"{p.name}/{p.model} HTTP {resp.status_code}: request too large for the free tier")
            if resp.status_code in (429, 500, 502, 503, 504):
                retry_after = resp.headers.get("retry-after")
                try:
                    wait = float(retry_after) if retry_after else 2**attempt * 3
                except ValueError:
                    wait = 2**attempt * 3
                LLM_REQUESTS.labels(p.name, f"http_{resp.status_code}").inc()
                last_exc = LLMError(f"{p.name}/{p.model} HTTP {resp.status_code}: {resp.text[:200]}")
                if wait > 90:  # daily quota exhausted -> fall back to next provider
                    break
                log.warning("%s returned %s, retrying in %.1fs", p.name, resp.status_code, wait)
                time.sleep(wait)
                continue
            if resp.status_code >= 400:
                LLM_REQUESTS.labels(p.name, f"http_{resp.status_code}").inc()
                raise LLMError(f"{p.name}/{p.model} HTTP {resp.status_code}: {resp.text[:300]}")
            data = resp.json()
            try:
                choice = data["choices"][0]
                text = choice["message"].get("content") or ""
            except (KeyError, IndexError, TypeError) as exc:
                raise LLMError(f"{p.name}: unexpected response shape") from exc
            if not text.strip():
                if choice.get("finish_reason") == "length" and body["max_tokens"] < 16000:
                    body["max_tokens"] = min(body["max_tokens"] * 2, 16000)  # reasoning used up the budget
                    continue
                raise LLMError(f"{p.name}/{p.model}: empty response")
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
        raise LLMError(f"{p.name}/{p.model}: giving up after retries ({last_exc})")

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
            pkey = f"{p.name}|{p.model}"
            if p.name in self._disabled or pkey in self._disabled:
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
                msg = str(exc).lower()
                if "http 401" in msg or "http 403" in msg:
                    self._disabled.add(p.name)  # bad key -> skip all models of this provider
                elif "http 404" in msg or "decommission" in msg or "does not exist" in msg or "not found" in msg:
                    self._disabled.add(pkey)  # retired model -> skip just this one
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
