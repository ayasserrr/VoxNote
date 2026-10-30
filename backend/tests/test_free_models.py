"""Free-model discovery and fallback behaviour (no network: httpx is stubbed)."""

import httpx
import pytest

from app.services import free_models, llm
from app.services.free_models import SPECS, rank_models, resolve_models

GROQ_LIVE = [
    "llama-3.3-70b-versatile", "whisper-large-v3", "whisper-large-v3-turbo", "openai/gpt-oss-120b",
    "openai/gpt-oss-20b", "qwen/qwen3-32b", "meta-llama/llama-prompt-guard-2-86m", "groq/compound",
    "playai-tts", "meta-llama/llama-4-scout-17b-16e-instruct",
]
GEMINI_LIVE = [
    "models/gemini-3.6-flash", "models/gemini-flash-latest", "models/gemini-flash-lite-latest",
    "models/gemini-3.6-pro", "models/gemini-3.6-flash-image", "models/text-embedding-004",
    "models/gemini-3.6-flash-native-audio", "models/gemma-3-27b-it",
]


def test_rank_groq_prefers_current_free_chat_models():
    ranked = rank_models(SPECS["groq"], GROQ_LIVE, 3)
    assert ranked == ["openai/gpt-oss-120b", "qwen/qwen3-32b", "meta-llama/llama-4-scout-17b-16e-instruct"]
    assert not any(x in " ".join(ranked) for x in ("whisper", "guard", "tts", "compound"))


def test_rank_gemini_uses_flash_alias_and_skips_pro_image_audio():
    ids = [free_models._strip(m) for m in GEMINI_LIVE]
    ranked = rank_models(SPECS["gemini"], ids, 3)
    assert ranked[0] == "gemini-flash-latest"
    assert "gemini-3.6-flash" in ranked
    assert not any(("pro" in m or "image" in m or "audio" in m or "embedding" in m) for m in ranked)


def test_resolve_explicit_list_and_fallback(monkeypatch):
    models, how = resolve_models("groq", "a/b, c/d", "https://x", "k")
    assert (models, how) == (["a/b", "c/d"], "configured")

    def boom(*a, **k):
        raise httpx.ConnectError("offline")

    free_models.clear_cache()
    monkeypatch.setattr(free_models.httpx, "get", boom)
    models, how = resolve_models("gemini", "auto", "https://x", "k")
    assert how == "fallback" and models[0] == "gemini-flash-latest"


def test_discovery_skips_inactive_models(monkeypatch):
    free_models.clear_cache()
    payload = {"data": [{"id": "llama-3.3-70b-versatile", "active": False},
                        {"id": "openai/gpt-oss-120b", "active": True}]}
    monkeypatch.setattr(free_models.httpx, "get",
                        lambda *a, **k: httpx.Response(200, json=payload, request=httpx.Request("GET", "https://x")))
    models, how = resolve_models("groq", "auto", "https://api.groq.com/openai/v1", "key", 3)
    assert how == "discovered" and models == ["openai/gpt-oss-120b"]


class _Calls:
    def __init__(self, responses):
        self.responses = list(responses)
        self.bodies = []

    def __call__(self, url, headers=None, json=None, timeout=None):
        self.bodies.append(dict(json))
        status, payload = self.responses.pop(0)
        return httpx.Response(status, json=payload, request=httpx.Request("POST", url))


def _ok(text, finish="stop"):
    return 200, {"choices": [{"message": {"content": text}, "finish_reason": finish}],
                 "usage": {"prompt_tokens": 5, "completion_tokens": 2}}


@pytest.fixture
def two_models():
    return [llm.Provider("groq", "https://g", "retired-model", "k"),
            llm.Provider("groq", "https://g", "openai/gpt-oss-120b", "k")]


def test_retired_model_falls_back_to_next_free_model(monkeypatch, two_models):
    calls = _Calls([(404, {"error": {"message": "The model `retired-model` has been decommissioned"}}), _ok("hi")])
    monkeypatch.setattr(llm.httpx, "post", calls)
    client = llm.LLMClient(providers=two_models)
    r = client.complete([{"role": "user", "content": "x"}])
    assert r.text == "hi" and r.model == "openai/gpt-oss-120b"
    assert "groq|retired-model" in client._disabled and "groq" not in client._disabled
    assert calls.bodies[1].get("reasoning_effort") == "low"  # reasoning models get a low effort budget


def test_request_too_large_shrinks_output_budget(monkeypatch, two_models):
    calls = _Calls([(413, {"error": {"message": "Request too large for model"}}), _ok("ok")])
    monkeypatch.setattr(llm.httpx, "post", calls)
    r = llm.LLMClient(providers=[two_models[1]]).complete([{"role": "user", "content": "x"}], max_tokens=8000)
    assert r.text == "ok" and calls.bodies[1]["max_tokens"] == 4000


def test_empty_answer_when_reasoning_used_budget_retries_bigger(monkeypatch, two_models):
    calls = _Calls([_ok("", finish="length"), _ok("done")])
    monkeypatch.setattr(llm.httpx, "post", calls)
    r = llm.LLMClient(providers=[two_models[1]]).complete([{"role": "user", "content": "x"}], max_tokens=2000)
    assert r.text == "done" and calls.bodies[1]["max_tokens"] == 4000


def test_unsupported_reasoning_param_is_dropped(monkeypatch, two_models):
    calls = _Calls([(400, {"error": {"message": "Unknown parameter: reasoning_effort"}}), _ok("fine")])
    monkeypatch.setattr(llm.httpx, "post", calls)
    r = llm.LLMClient(providers=[two_models[1]]).complete([{"role": "user", "content": "x"}])
    assert r.text == "fine" and "reasoning_effort" not in calls.bodies[1]


def test_status_lists_only_free_providers(client):
    st = client.get("/api/system/status").json()
    names = {p["name"] for p in st["llm_providers"]}
    assert {"groq", "gemini", "cerebras", "mistral", "openrouter", "ollama"} <= names
    assert all(p["free"] for p in st["llm_providers"])


def test_test_ai_endpoint(auth_client):
    r = auth_client.post("/api/system/test-ai").json()
    assert r["working"] == 1 and r["results"][0]["provider"] == "mock" and r["results"][0]["ok"]
