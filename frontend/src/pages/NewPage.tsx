import { useEffect, useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api";
import SettingsForm, { DEFAULT_SETTINGS } from "../components/SettingsForm";
import type { ProcessingSettings, SystemStatus, UrlPreview } from "../types";
import { fmtTime } from "../utils";

export default function NewPage() {
  const nav = useNavigate();
  const [mode, setMode] = useState<"url" | "upload">("url");
  const [url, setUrl] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [settings, setSettings] = useState<ProcessingSettings>(DEFAULT_SETTINGS);
  const [preview, setPreview] = useState<UrlPreview | null>(null);
  const [previewing, setPreviewing] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<SystemStatus | null>(null);

  useEffect(() => {
    api.status().then(setStatus).catch(() => undefined);
  }, []);

  useEffect(() => {
    setPreview(null);
    if (!/youtu\.?be|^[\w-]{11}$/.test(url.trim())) return;
    const t = setTimeout(async () => {
      setPreviewing(true);
      try {
        setPreview(await api.preview(url.trim()));
        setError(null);
      } catch (e) {
        setError((e as Error).message);
      } finally {
        setPreviewing(false);
      }
    }, 600);
    return () => clearTimeout(t);
  }, [url]);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const col =
        mode === "url" ? await api.createCollection(url.trim(), settings) : await api.upload(file!, settings);
      nav(`/collections/${col.id}`);
    } catch (err) {
      setError((err as Error).message);
      setBusy(false);
    }
  };

  const noLlm = status && !status.llm_providers.some((p) => p.configured && p.in_chain);

  return (
    <div className="new-page">
      <section className="hero">
        <h1>What do you want to learn from?</h1>
        <p className="muted">
          Paste a YouTube video or playlist. VoxNote transcribes it, extracts every concept, example and piece of code, and builds a
          detailed, timestamped study document — in English, Arabic or both.
        </p>
      </section>

      {noLlm && (
        <div className="alert warn">
          No AI provider is configured yet. Add a free <strong>GROQ_API_KEY</strong> or <strong>GEMINI_API_KEY</strong> to your <code>.env</code> and
          restart the backend — see <a href="/settings">Settings</a>.
        </div>
      )}

      <form className="card process-card" onSubmit={submit}>
        <div className="segmented">
          <button type="button" className={mode === "url" ? "active" : ""} onClick={() => setMode("url")}>YouTube URL</button>
          <button type="button" className={mode === "upload" ? "active" : ""} onClick={() => setMode("upload")}>Upload audio / video</button>
        </div>

        {mode === "url" ? (
          <div className="url-row">
            <input
              className="url-input"
              placeholder="https://www.youtube.com/playlist?list=…  or  https://youtu.be/…"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              required
              autoFocus
            />
          </div>
        ) : (
          <label className="dropzone">
            <input type="file" accept="audio/*,video/*" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
            {file ? <span>📎 {file.name} ({(file.size / 1024 / 1024).toFixed(1)} MB)</span> : <span>Click to choose an audio or video file you own</span>}
            {status && !status.stt_available && (
              <small className="muted">Uploads need speech-to-text: set GROQ_API_KEY (free Whisper) or STT_PROVIDER=local.</small>
            )}
          </label>
        )}

        {previewing && <div className="muted small">Looking up URL…</div>}
        {preview && (
          <div className="preview">
            {preview.thumbnail_url && <img src={preview.thumbnail_url} alt="" />}
            <div>
              <span className="tag">{preview.kind === "playlist" ? "Playlist" : "Video"}</span>
              <h3>{preview.title}</h3>
              <div className="muted">
                {preview.channel}
                {preview.video_count && preview.kind === "playlist" ? ` · ${preview.video_count} videos` : ""}
                {preview.duration_seconds ? ` · ${fmtTime(preview.duration_seconds)}` : ""}
              </div>
            </div>
          </div>
        )}

        <h4>Document settings</h4>
        <SettingsForm value={settings} onChange={setSettings} showPlaylistOptions={mode === "url"} />

        {error && <div className="alert error">{error}</div>}
        <button className="btn primary lg block" disabled={busy || (mode === "url" ? !url.trim() : !file)}>
          {busy ? "Starting…" : "Start processing"}
        </button>
      </form>

      <section className="steps">
        {[
          ["1", "Ingest", "Video or playlist metadata via yt-dlp"],
          ["2", "Transcribe", "Captions, or free Whisper on Groq"],
          ["3", "Understand", "Chunked LLM extraction with validated JSON"],
          ["4", "Verify", "Coverage & grounding checks vs. transcript"],
          ["5", "Publish", "PDF + Markdown, playlist book, Q&A"],
        ].map(([n, t, d]) => (
          <div key={n} className="step">
            <span className="step-n">{n}</span>
            <strong>{t}</strong>
            <small className="muted">{d}</small>
          </div>
        ))}
      </section>
    </div>
  );
}
