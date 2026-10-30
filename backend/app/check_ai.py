"""Check which FREE AI providers/models work with your keys.

    cd backend
    python -m app.check_ai          (Windows: .venv\\Scripts\\python -m app.check_ai)
"""

from __future__ import annotations

from app.config import settings
from app.services.llm import provider_status, test_providers


def main() -> int:
    print("VoxNote — free AI provider check\n")
    print(f"Provider order (LLM_PROVIDERS): {settings.llm_providers}\n")
    for row in provider_status():
        if row["name"] in ("mock", "openai_compat") and not row["configured"]:
            continue
        mark = "✔ key found" if row["configured"] else "· no key"
        models = row["model"] or "-"
        print(f"  {row['label']:<16} {mark:<12} models: {models}  ({row['selection'] or 'not used'})")
        if not row["configured"] and row["signup_url"]:
            print(f"  {'':<16} get a free key: {row['signup_url']}")
    print("\nSending a tiny test prompt to every configured model…\n")
    results = test_providers()
    if not results:
        print("  No provider configured. Put at least one free key in the .env file (project root),")
        print("  e.g. GROQ_API_KEY=... from https://console.groq.com/keys")
        return 1
    for r in results:
        if r["ok"]:
            print(f"  ✔ {r['provider']}/{r['model']}  ({r['seconds']}s)  reply: {r['reply']!r}")
        else:
            print(f"  ✘ {r['provider']}/{r['model']}  {r['error']}")
    ok = sum(1 for r in results if r["ok"])
    print(f"\n{ok} of {len(results)} free models are working.", "You're all set!" if ok else "Check your keys.")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
