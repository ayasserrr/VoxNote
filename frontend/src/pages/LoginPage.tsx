import { useState, type FormEvent } from "react";
import { useAuth } from "../auth";

export default function LoginPage() {
  const { login, register } = useAuth();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      if (mode === "login") await login(email, password);
      else await register(email, password, name || undefined);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="auth-page">
      <div className="auth-hero">
        <div className="logo big">V</div>
        <h1>VoxNote</h1>
        <p className="tagline">Turn every video into a complete learning resource.</p>
        <ul className="features">
          <li>🎬 YouTube videos &amp; whole playlists</li>
          <li>🌍 Arabic, Egyptian Arabic, English &amp; mixed speech</li>
          <li>🧠 Detailed concepts, code, examples, glossary &amp; quizzes</li>
          <li>📄 Professional PDFs with clickable timestamps</li>
          <li>💬 Ask questions across your whole playlist</li>
          <li>🆓 Runs on free AI models (Groq, Gemini, OpenRouter, Ollama)</li>
        </ul>
      </div>
      <form className="card auth-card" onSubmit={submit}>
        <h2>{mode === "login" ? "Sign in" : "Create your account"}</h2>
        {mode === "register" && (
          <label>
            <span>Name</span>
            <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Optional" />
          </label>
        )}
        <label>
          <span>Email</span>
          <input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} autoFocus />
        </label>
        <label>
          <span>Password</span>
          <input type="password" required minLength={6} value={password} onChange={(e) => setPassword(e.target.value)} />
        </label>
        {error && <div className="alert error">{error}</div>}
        <button className="btn primary block" disabled={busy}>
          {busy ? "Please wait…" : mode === "login" ? "Sign in" : "Create account"}
        </button>
        <p className="muted center">
          {mode === "login" ? "No account yet? " : "Already have an account? "}
          <button type="button" className="link" onClick={() => setMode(mode === "login" ? "register" : "login")}>
            {mode === "login" ? "Create one" : "Sign in"}
          </button>
        </p>
      </form>
    </div>
  );
}
