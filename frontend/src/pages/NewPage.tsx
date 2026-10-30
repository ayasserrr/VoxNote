import { useEffect, useState, type FormEvent } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { BookText, FileAudio, GraduationCap, ShieldCheck, Upload, Youtube } from "lucide-react";
import { api, isYouTubeUrl } from "../api";
import SettingsForm, { DEFAULT_SETTINGS } from "../components/SettingsForm";
import { useToast } from "../components/Toast";
import { PageHeader } from "../components/ui";
import type { LangChoice, Level, ProcessingSettings, SystemStatus, UrlPreview } from "../types";
import { fmtTime } from "../utils";

type Tab = "youtube" | "docs" | "upload";

const TABS: { id: Tab; label: string; icon: typeof Youtube; desc: string }[] = [
  { id: "youtube", label: "YouTube", icon: Youtube, desc: "Video or playlist → detailed notes, PDF book & Q&A" },
  { id: "docs", label: "Documentation", icon: BookText, desc: "Any docs website → step-by-step course with quizzes" },
  { id: "upload", label: "Upload", icon: FileAudio, desc: "Your own audio/video recording → notes & PDF" },
];

export default function NewPage() {
  const nav = useNavigate();
  const toast = useToast();
  const [params, setParams] = useSearchParams();
  const tab = (params.get("tab") as Tab) || "youtube";
  const setTab = (t: Tab) => setParams({ tab: t });

  const [status, setStatus] = useState<SystemStatus | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // youtube
  const [url, setUrl] = useState("");
  const [settings, setSettings] = useState<ProcessingSettings>(DEFAULT_SETTINGS);
  const [preview, setPreview] = useState<UrlPreview | null>(null);
  const [previewing, setPreviewing] = useState(false);
  // docs
  const [docUrl, setDocUrl] = useState("");
  const [maxPages, setMaxPages] = useState(40);
  const [samePath, setSamePath] = useState(true);
  const [level, setLevel] = useState<Level>("beginner");
  const [lang, setLang] = useState<LangChoice>("auto");
  // upload
  const [file, setFile] = useState<File | null>(null);

  useEffect(() => {
    api.status().then(setStatus).catch(() => undefined);
  }, []);
  useEffect(() => {
    setError(null);
  }, [tab]);

  useEffect(() => {
    setPreview(null);
    if (tab !== "youtube" || !isYouTubeUrl(url)) return;
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
  }, [url, tab]);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      let id: string;
      if (tab === "youtube") id = (await api.createCollection(url.trim(), settings)).id;
      else if (tab === "docs")
        id = (await api.createDocs({ url: docUrl.trim(), max_pages: maxPages, same_path_only: samePath, level, language: lang })).id;
      else id = (await api.upload(file!, settings)).id;
      toast(tab === "docs" ? "Reading the documentation — your course is being prepared" : "Processing started", "success");
      nav(`/collections/${id}`);
    } catch (err) {
      setError((err as Error).message);
      setBusy(false);
    }
  };

  const noLlm = status && !status.llm_providers.some((p) => p.configured && p.in_chain);
  const canSubmit = tab === "youtube" ? !!url.trim() : tab === "docs" ? !!docUrl.trim() : !!file;

  return (
    <div className="narrow">
      <PageHeader title="Add something to learn" subtitle="Choose a source. Everything runs on free AI models." />
      {noLlm && (
        <div className="alert warn">
          No AI provider is configured yet. Add a free <strong>GROQ_API_KEY</strong> or <strong>GEMINI_API_KEY</strong> to <code>.env</code> and restart
          the backend (see <a href="/settings">Settings</a>).
        </div>
      )}
      <div className="source-tabs">
        {TABS.map(({ id, label, icon: Icon, desc }) => (
          <button key={id} type="button" className={`source-tab ${tab === id ? "active" : ""}`} onClick={() => setTab(id)}>
            <Icon size={22} />
            <strong>{label}</strong>
            <small>{desc}</small>
          </button>
        ))}
      </div>

      <form className="card form-card" onSubmit={submit}>
        {tab === "youtube" && (
          <>
            <label className="field">
              <span>Video or playlist URL</span>
              <input className="input-lg" placeholder="https://www.youtube.com/playlist?list=…  or  https://youtu.be/…" value={url}
                onChange={(e) => setUrl(e.target.value)} autoFocus />
            </label>
            {previewing && <div className="muted small">Looking up the URL…</div>}
            {preview && (
              <div className="preview">
                {preview.thumbnail_url && <img src={preview.thumbnail_url} alt="" />}
                <div>
                  <span className="tag">{preview.kind === "playlist" ? "Playlist" : "Video"}</span>
                  <h3>{preview.title}</h3>
                  <div className="muted small">
                    {preview.channel}
                    {preview.kind === "playlist" && preview.video_count ? ` · ${preview.video_count} videos` : ""}
                    {preview.duration_seconds ? ` · ${fmtTime(preview.duration_seconds)}` : ""}
                  </div>
                </div>
              </div>
            )}
            <h4>Document settings</h4>
            <SettingsForm value={settings} onChange={setSettings} />
          </>
        )}

        {tab === "docs" && (
          <>
            <label className="field">
              <span>Documentation URL</span>
              <input className="input-lg" placeholder="https://docs.python.org/3/tutorial/  ·  https://fastapi.tiangolo.com/tutorial/" value={docUrl}
                onChange={(e) => setDocUrl(e.target.value)} autoFocus />
              <small className="muted">
                Start from the page where the docs begin. VoxNote reads every page under that section (following the sidebar order and the
                sitemap), then designs a course: short lessons explained simply, each followed by a quiz that is corrected for you.
              </small>
            </label>
            <div className="settings-grid">
              <label className="field">
                <span>Your level</span>
                <select value={level} onChange={(e) => setLevel(e.target.value as Level)}>
                  <option value="beginner">Beginner — explain everything from scratch</option>
                  <option value="intermediate">Intermediate — I know the basics</option>
                  <option value="advanced">Advanced — go deep</option>
                </select>
              </label>
              <label className="field">
                <span>Teaching language</span>
                <select value={lang} onChange={(e) => setLang(e.target.value as LangChoice)}>
                  <option value="auto">Same as the documentation</option>
                  <option value="en">English</option>
                  <option value="ar">Arabic (العربية)</option>
                  <option value="bilingual">Arabic with English technical terms</option>
                </select>
              </label>
              <label className="field">
                <span>Maximum pages to read: <strong>{maxPages}</strong></span>
                <input type="range" min={1} max={300} value={maxPages} onChange={(e) => setMaxPages(Number(e.target.value))} />
              </label>
              <label className="check">
                <input type="checkbox" checked={samePath} onChange={(e) => setSamePath(e.target.checked)} />
                <span>Only this section of the site (recommended)</span>
              </label>
            </div>
            <div className="hint">
              <GraduationCap size={18} />
              <span>Lessons are generated one at a time as you study, so even a 300-page site stays within free AI limits.</span>
            </div>
          </>
        )}

        {tab === "upload" && (
          <>
            <label className="dropzone">
              <input type="file" accept="audio/*,video/*" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
              <Upload size={28} />
              {file ? <strong>{file.name} ({(file.size / 1024 / 1024).toFixed(1)} MB)</strong> : <strong>Choose an audio or video file</strong>}
              <small className="muted">MP3, WAV, M4A, MP4, WEBM, MKV…</small>
            </label>
            {status && !status.stt_available && (
              <div className="alert warn">Uploads need speech-to-text: set GROQ_API_KEY (free Whisper) or STT_PROVIDER=local.</div>
            )}
            <h4>Document settings</h4>
            <SettingsForm value={settings} onChange={setSettings} showPlaylistOptions={false} />
          </>
        )}

        {error && <div className="alert error">{error}</div>}
        <button className="btn primary lg block" disabled={busy || !canSubmit}>
          {busy ? "Starting…" : tab === "docs" ? "Read docs & build my course" : "Start processing"}
        </button>
        <p className="muted small center">
          <ShieldCheck size={13} /> Only process content you're allowed to use. Docs crawling respects robots.txt.
        </p>
      </form>
    </div>
  );
}
