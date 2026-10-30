import { useEffect, useState } from "react";
import { CheckCircle2, ExternalLink, KeyRound, PlugZap, Settings, XCircle } from "lucide-react";
import { api } from "../api";
import { useToast } from "../components/Toast";
import { PageHeader, Spinner } from "../components/ui";
import type { AiTestResult, SystemStatus } from "../types";

const ENV_KEY: Record<string, string> = {
  groq: "GROQ_API_KEY=…",
  gemini: "GEMINI_API_KEY=…",
  cerebras: "CEREBRAS_API_KEY=…",
  mistral: "MISTRAL_API_KEY=…",
  openrouter: "OPENROUTER_API_KEY=…",
  ollama: "OLLAMA_ENABLED=true",
  openai_compat: "OPENAI_COMPAT_BASE_URL=… + OPENAI_COMPAT_MODEL=…",
  mock: "LLM_PROVIDERS=mock",
};

export default function SettingsPage() {
  const toast = useToast();
  const [s, setS] = useState<SystemStatus | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [testing, setTesting] = useState(false);
  const [results, setResults] = useState<AiTestResult[] | null>(null);

  useEffect(() => {
    api.status().then(setS).catch((e) => setErr(e.message));
  }, []);

  const test = async () => {
    setTesting(true);
    setResults(null);
    try {
      const r = await api.testAi();
      setResults(r.results);
      toast(r.working ? `${r.working} free model(s) working` : "No working model — check your keys", r.working ? "success" : "error");
      setS(await api.status());
    } catch (e) {
      toast((e as Error).message, "error");
    } finally {
      setTesting(false);
    }
  };

  if (err) return <div className="alert error">{err}</div>;
  if (!s) return <Spinner />;
  const active = s.llm_providers.filter((p) => p.configured && p.in_chain);
  const rows = s.llm_providers.filter((p) => p.name !== "mock" || p.configured);

  return (
    <div>
      <PageHeader
        icon={<Settings size={22} />}
        title="Settings & free AI"
        subtitle="VoxNote only uses FREE AI models — no paid API keys and no credit card. Add one or more free keys to the .env file in the project folder and restart the backend."
        actions={
          <button className="btn primary" onClick={test} disabled={testing || active.length === 0}>
            <PlugZap size={16} /> {testing ? "Testing…" : "Test my AI keys"}
          </button>
        }
      />

      {active.length === 0 ? (
        <div className="alert warn">
          <KeyRound size={18} />
          <div>
            <strong>No AI key configured yet.</strong> The quickest free option: create a key at{" "}
            <a href="https://console.groq.com/keys" target="_blank" rel="noreferrer">console.groq.com/keys</a> (no credit card), put{" "}
            <code>GROQ_API_KEY=your_key</code> in <code>.env</code> and restart the backend. Add <code>GEMINI_API_KEY</code> too for automatic fallback.
          </div>
        </div>
      ) : (
        <div className="alert ok">
          <CheckCircle2 size={18} />
          <div>
            Active free providers, in fallback order: <strong>{active.map((p) => p.label).join(" → ")}</strong>. Models are discovered automatically
            from each provider's live list, so retired free models are replaced without any change on your side.
          </div>
        </div>
      )}

      {results && (
        <div className="card">
          <h3 style={{ marginTop: 0 }}>Test results</h3>
          <div className="test-results">
            {results.map((r, i) => (
              <div key={i} className={`test-row ${r.ok ? "ok" : "bad"}`}>
                {r.ok ? <CheckCircle2 size={18} /> : <XCircle size={18} />}
                <code>{r.provider}/{r.model}</code>
                <span className="grow muted small">{r.ok ? `answered in ${r.seconds}s` : r.error}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="card">
        <h3 style={{ marginTop: 0 }}>Free AI providers</h3>
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr><th>Provider</th><th>Status</th><th>Models in use</th><th>How to enable (free)</th></tr>
            </thead>
            <tbody>
              {rows.map((p) => (
                <tr key={p.name}>
                  <td><strong>{p.label}</strong><div className="muted small">{p.note}</div></td>
                  <td>
                    {p.configured && p.in_chain ? (
                      <span className="badge badge-completed">active</span>
                    ) : p.configured ? (
                      <span className="badge">key set, not in LLM_PROVIDERS</span>
                    ) : (
                      <span className="badge">no key</span>
                    )}
                    <div><span className="tag free-tag">FREE</span></div>
                  </td>
                  <td className="small">
                    {p.models.length ? p.models.map((m) => <div key={m}><code>{m}</code></div>) : <span className="muted">auto</span>}
                    {p.selection && <div className="muted">({p.selection})</div>}
                  </td>
                  <td className="small">
                    <code>{ENV_KEY[p.name]}</code>
                    {p.signup_url && (
                      <div><a href={p.signup_url} target="_blank" rel="noreferrer">Get a free key <ExternalLink size={11} /></a></div>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="card">
        <h3 style={{ marginTop: 0 }}>System</h3>
        <div className="metrics">
          <div><strong>{s.stt_available ? "Ready" : "Off"}</strong><span>Speech-to-text ({s.stt_provider}, free Whisper)</span></div>
          <div><strong>{s.ffmpeg_available ? "Yes" : "No"}</strong><span>ffmpeg (long audio)</span></div>
          <div><strong>{s.task_backend}</strong><span>Job queue</span></div>
          <div><strong>{s.storage_backend}</strong><span>Storage</span></div>
          <div><strong>{s.version}</strong><span>Version</span></div>
        </div>
        {!s.stt_available && (
          <div className="alert warn">
            Speech-to-text is off, so only videos that have captions can be processed (documentation courses are not affected). The free Groq key also
            enables Whisper; or install <code>faster-whisper</code> and set <code>STT_PROVIDER=local</code> to run it on your computer.
          </div>
        )}
      </div>
    </div>
  );
}
