import { useEffect, useState } from "react";
import { api } from "../api";
import type { SystemStatus } from "../types";

const KEYS: Record<string, { env: string; url: string; note: string }> = {
  groq: { env: "GROQ_API_KEY", url: "https://console.groq.com/keys", note: "Free tier · very fast Llama 3.3 70B + free Whisper speech-to-text" },
  gemini: { env: "GEMINI_API_KEY", url: "https://aistudio.google.com/apikey", note: "Free tier · Gemini Flash, large context, strong Arabic" },
  openrouter: { env: "OPENROUTER_API_KEY", url: "https://openrouter.ai/keys", note: "Many ':free' models; openrouter/free auto-picks one" },
  ollama: { env: "OLLAMA_ENABLED=true", url: "https://ollama.com/download", note: "100% local and offline, no key needed" },
  openai_compat: { env: "OPENAI_COMPAT_BASE_URL", url: "https://lmstudio.ai", note: "Any OpenAI-compatible server (LM Studio, vLLM…)" },
  mock: { env: "LLM_PROVIDERS=mock", url: "", note: "Offline demo / tests — extractive, low quality" },
};

export default function SettingsPage() {
  const [s, setS] = useState<SystemStatus | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    api.status().then(setS).catch((e) => setErr(e.message));
  }, []);
  if (err) return <div className="alert error">{err}</div>;
  if (!s) return <div className="spinner" />;
  return (
    <div>
      <h1>Settings &amp; system status</h1>
      <p className="muted">
        VoxNote runs on free AI providers. Keys live in the <code>.env</code> file at the project root — edit it and restart the backend.
        Providers are tried in the order of <code>LLM_PROVIDERS</code>; if one is rate-limited, the next one is used automatically.
      </p>
      <div className="card">
        <h3>AI language models</h3>
        <table className="table">
          <thead><tr><th>Provider</th><th>Model</th><th>Status</th><th>How to enable</th></tr></thead>
          <tbody>
            {s.llm_providers.map((p) => (
              <tr key={p.name}>
                <td><strong>{p.name}</strong></td>
                <td><code>{p.model || "—"}</code></td>
                <td>
                  {p.configured ? <span className="badge badge-completed">active</span> : p.in_chain ? <span className="badge badge-queued">no key</span> : <span className="badge">not in chain</span>}
                </td>
                <td className="small">
                  <code>{KEYS[p.name]?.env}</code>{" "}
                  {KEYS[p.name]?.url && <a href={KEYS[p.name].url} target="_blank" rel="noreferrer">get it</a>}
                  <div className="muted">{KEYS[p.name]?.note}</div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="card">
        <h3>System</h3>
        <div className="metrics">
          <div><strong>{s.stt_available ? "Ready" : "Off"}</strong><span>Speech-to-text ({s.stt_provider})</span></div>
          <div><strong>{s.ffmpeg_available ? "Yes" : "No"}</strong><span>ffmpeg (long audio)</span></div>
          <div><strong>{s.task_backend}</strong><span>Job queue</span></div>
          <div><strong>{s.storage_backend}</strong><span>Storage</span></div>
          <div><strong>{s.version}</strong><span>Version</span></div>
        </div>
        {!s.stt_available && (
          <div className="alert warn">
            Speech-to-text is not available, so only videos with captions can be processed. Set <code>GROQ_API_KEY</code> (free Whisper large-v3) or
            install <code>faster-whisper</code> and set <code>STT_PROVIDER=local</code>.
          </div>
        )}
      </div>
    </div>
  );
}
