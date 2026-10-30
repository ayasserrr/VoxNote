import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, BookText, ExternalLink, FileText, GraduationCap, RefreshCw } from "lucide-react";
import { api } from "../api";
import AskPanel from "../components/AskPanel";
import DocumentButtons from "../components/DocumentButtons";
import { Questions } from "../components/KnowledgeView";
import SettingsForm from "../components/SettingsForm";
import { ProgressBar, StatusBadge } from "../components/StatusBadge";
import { useToast } from "../components/Toast";
import { Spinner } from "../components/ui";
import type { Collection, LangChoice, Level, LogEntry, ProcessingSettings } from "../types";
import { fmtTime, hostOf, isActive, LANG_LABEL, STAGE_LABEL } from "../utils";

type Tab = "videos" | "pages" | "course" | "ask" | "logs";

export default function CollectionPage() {
  const { id } = useParams();
  const nav = useNavigate();
  const [col, setCol] = useState<Collection | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>("videos");
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [regen, setRegen] = useState<ProcessingSettings | null>(null);
  const [learnOpen, setLearnOpen] = useState(false);
  const [level, setLevel] = useState<Level>("beginner");
  const [lang, setLang] = useState<LangChoice>("auto");
  const [creating, setCreating] = useState(false);
  const toast = useToast();

  const load = useCallback(async () => {
    try {
      setCol(await api.collection(id!));
    } catch (e) {
      setError((e as Error).message);
    }
  }, [id]);

  const running = col
    ? isActive(col.status) || col.videos.some((v) => isActive(v.status)) || ["synthesizing", "rendering", "crawling", "structuring"].includes(col.stage)
    : false;

  useEffect(() => {
    if (col?.kind === "docs" && tab === "videos") setTab("pages");
  }, [col?.kind, tab]);

  const startCourse = async () => {
    if (!col) return;
    setCreating(true);
    try {
      const c = await api.createCourse(col.id, level, lang);
      toast("Your course is being designed…", "success");
      nav(`/learn/${c.id}`);
    } catch (e) {
      toast((e as Error).message, "error");
    } finally {
      setCreating(false);
    }
  };

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    if (!running) return;
    const t = setInterval(load, 2500);
    return () => clearInterval(t);
  }, [running, load]);

  useEffect(() => {
    if (tab === "logs" && id) api.logs(id).then(setLogs).catch(() => undefined);
  }, [tab, id, col?.updated_at]);

  if (error) return <div className="alert error">{error}</div>;
  if (!col) return <Spinner />;
  if (col.kind === "docs") return <DocsCollection col={col} running={running} tab={tab} setTab={setTab} logs={logs} reload={load} />;

  const bookDocs = col.documents.filter((d) => d.kind === "collection");
  const docsFor = (vid: string) => col.documents.filter((d) => d.video_id === vid);
  const totalDuration = col.videos.reduce((s, v) => s + (v.duration_seconds ?? 0), 0);
  const failed = col.videos.filter((v) => v.status === "failed").length;
  const progress = col.videos.reduce((s, v) => s + (v.status === "failed" ? 1 : v.progress), 0) / Math.max(col.videos.length, 1);

  const doDelete = async () => {
    if (!confirm("Delete this collection and all its documents?")) return;
    await api.deleteCollection(col.id);
    nav("/library");
  };

  return (
    <div>
      <Link to="/library" className="back"><ArrowLeft size={14} /> Library</Link>
      <div className="collection-header card">
        {col.thumbnail_url && <img className="cover" src={col.thumbnail_url} alt="" />}
        <div className="grow">
          <div className="row">
            <span className="tag">{col.kind}</span>
            <StatusBadge status={col.status} stage={col.stage === "synthesizing" || col.stage === "rendering" ? col.stage : undefined} />
          </div>
          <h1 dir="auto">{col.title}</h1>
          <div className="muted">
            {col.channel && <>{col.channel} · </>}
            {col.videos.length} video{col.videos.length > 1 ? "s" : ""}
            {totalDuration ? ` · ${fmtTime(totalDuration)}` : ""}
            {col.source_url && (
              <> · <a href={col.source_url} target="_blank" rel="noreferrer">source</a></>
            )}
          </div>
          {running && (
            <div className="overall">
              <ProgressBar value={progress} />
              <span className="muted small">
                {col.videos.filter((v) => v.status === "completed").length}/{col.videos.length} completed
                {col.stage === "synthesizing" && " · building cross-video knowledge…"}
                {col.stage === "rendering" && " · generating playlist book…"}
              </span>
            </div>
          )}
          {col.error && <div className="alert error">{col.error}</div>}
          <div className="row actions">
            {bookDocs.length > 0 && (
              <div>
                <div className="muted small">Playlist knowledge book</div>
                <DocumentButtons docs={bookDocs} />
              </div>
            )}
            {col.kind !== "playlist" && col.videos[0] && docsFor(col.videos[0].id).length > 0 && (
              <DocumentButtons docs={docsFor(col.videos[0].id)} />
            )}
          </div>
          <div className="row">
            {col.course_id ? (
              <Link className="btn primary sm" to={`/learn/${col.course_id}`}><GraduationCap size={14} /> Open course</Link>
            ) : (
              col.videos.some((v) => v.status === "completed") && (
                <button className="btn primary sm" onClick={() => setLearnOpen(!learnOpen)}><GraduationCap size={14} /> Learn this as a course</button>
              )
            )}
            {failed > 0 && !running && (
              <button className="btn sm" onClick={async () => setCol(await api.retryFailed(col.id))}>
                ↻ Retry {failed} failed
              </button>
            )}
            {!running && (
              <button className="btn ghost sm" onClick={() => setRegen(regen ? null : col.settings)}>
                ⚙ Regenerate with new settings
              </button>
            )}
            <button className="btn ghost sm danger" onClick={doDelete}>Delete</button>
          </div>
          {learnOpen && (
            <div className="regen">
              <p className="small muted">VoxNote will design a step-by-step course from these videos: short lessons explained simply, each with a quiz that is corrected for you.</p>
              <div className="settings-grid">
                <label className="field"><span>Your level</span>
                  <select value={level} onChange={(e) => setLevel(e.target.value as Level)}>
                    <option value="beginner">Beginner</option><option value="intermediate">Intermediate</option><option value="advanced">Advanced</option>
                  </select>
                </label>
                <label className="field"><span>Teaching language</span>
                  <select value={lang} onChange={(e) => setLang(e.target.value as LangChoice)}>
                    <option value="auto">Same as the videos</option><option value="en">English</option><option value="ar">Arabic</option><option value="bilingual">Arabic + English terms</option>
                  </select>
                </label>
              </div>
              <button className="btn primary sm" disabled={creating} onClick={startCourse}>{creating ? "Creating…" : "Create my course"}</button>
            </div>
          )}
          {regen && (
            <div className="regen">
              <SettingsForm value={regen} onChange={setRegen} showPlaylistOptions={col.kind === "playlist"} />
              <button
                className="btn primary sm"
                onClick={async () => {
                  setCol(await api.regenerate(col.id, regen));
                  setRegen(null);
                }}
              >
                Regenerate (reuses transcripts)
              </button>
            </div>
          )}
        </div>
      </div>

      <div className="tabs big">
        <button className={tab === "videos" ? "active" : ""} onClick={() => setTab("videos")}>Videos</button>
        {col.synthesis && <button className={tab === "course" ? "active" : ""} onClick={() => setTab("course")}>Course overview</button>}
        <button className={tab === "ask" ? "active" : ""} onClick={() => setTab("ask")}>Ask {col.kind === "playlist" ? "your playlist" : "this video"}</button>
        <button className={tab === "logs" ? "active" : ""} onClick={() => setTab("logs")}>Processing log</button>
      </div>

      {tab === "videos" && (
        <div className="video-list">
          {col.videos.map((v) => (
            <div key={v.id} className={`card video-row status-${v.status}`}>
              <span className="pos">{v.position + 1}</span>
              {v.thumbnail_url ? <img src={v.thumbnail_url} alt="" /> : <div className="thumb-placeholder sm">🎧</div>}
              <div className="grow">
                <Link to={`/videos/${v.id}`} className="title" dir="auto">{v.title}</Link>
                <div className="muted small">
                  {v.duration_seconds ? fmtTime(v.duration_seconds) : ""}
                  {v.language ? ` · ${LANG_LABEL[v.language] ?? v.language}` : ""}
                  {v.attempts > 1 ? ` · attempt ${v.attempts}` : ""}
                </div>
                {isActive(v.status) && (
                  <div className="row">
                    <ProgressBar value={v.progress} />
                    <span className="muted small nowrap">{v.status === "queued" ? "Waiting" : STAGE_LABEL[v.stage] ?? v.stage}</span>
                  </div>
                )}
                {v.error && <div className={`small ${v.status === "failed" ? "error-text" : "muted"}`}>{v.error}</div>}
              </div>
              <div className="video-actions">
                <StatusBadge status={v.status} stage={v.stage} />
                {v.status === "completed" && <DocumentButtons docs={docsFor(v.id)} />}
                {v.status === "failed" && (
                  <button className="btn sm" onClick={async () => { await api.retryVideo(v.id); load(); }}>↻ Retry</button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {tab === "course" && col.synthesis && (
        <div className="card course" dir="auto">
          {col.synthesis.course_summary && (
            <>
              <h3>Course summary</h3>
              {col.synthesis.course_summary.split("\n\n").map((p, i) => <p key={i}>{p}</p>)}
            </>
          )}
          {col.synthesis.learning_path.length > 0 && (
            <>
              <h3>Learning path</h3>
              <ol className="path">
                {col.synthesis.learning_path.map((s, i) => (
                  <li key={i}>
                    <strong>{s.step}</strong> {s.goal && <span className="muted">— {s.goal}</span>}{" "}
                    {s.videos.map((n) => <span key={n} className="tag">#{n}</span>)}
                  </li>
                ))}
              </ol>
            </>
          )}
          {col.synthesis.concept_map.length > 0 && (
            <>
              <h3>Concept relationships</h3>
              <div className="concept-map">
                {col.synthesis.concept_map.map((m, i) => (
                  <div key={i} className="edge">
                    <span className="node">{m.source}</span>
                    <span className="rel">{m.relation} →</span>
                    <span className="node">{m.target}</span>
                  </div>
                ))}
              </div>
            </>
          )}
          {col.synthesis.concepts.length > 0 && (
            <>
              <h3>Concepts across the course</h3>
              <table className="table">
                <thead><tr><th>Concept</th><th>Description</th><th>Videos</th></tr></thead>
                <tbody>
                  {col.synthesis.concepts.map((c, i) => (
                    <tr key={i}><td><strong>{c.name}</strong></td><td>{c.description}</td><td>{c.videos.map((n) => `#${n}`).join(", ")}</td></tr>
                  ))}
                </tbody>
              </table>
            </>
          )}
          {col.synthesis.recurring_concepts.length > 0 && (
            <>
              <h3>Recurring concepts</h3>
              <div className="tags">{col.synthesis.recurring_concepts.map((c, i) => <span key={i} className="tag">{c}</span>)}</div>
            </>
          )}
          {col.synthesis.glossary.length > 0 && (
            <>
              <h3>Unified glossary</h3>
              <table className="table">
                <thead><tr><th>Term</th><th>Definition</th><th>Translation</th></tr></thead>
                <tbody>
                  {col.synthesis.glossary.map((g, i) => (
                    <tr key={i}><td><strong>{g.term}</strong></td><td>{g.definition}</td><td>{g.translation}</td></tr>
                  ))}
                </tbody>
              </table>
            </>
          )}
          {col.synthesis.final_questions.length > 0 && (
            <>
              <h3>Course review questions</h3>
              <Questions items={col.synthesis.final_questions} />
            </>
          )}
        </div>
      )}

      {tab === "ask" && (
        <div className="card">
          <AskPanel collectionId={col.id} />
        </div>
      )}

      {tab === "logs" && (
        <div className="card logs">
          {logs.length === 0 && <p className="muted">No log entries yet.</p>}
          {logs.map((l) => (
            <div key={l.id} className={`log log-${l.level}`}>
              <span className="muted small nowrap">{new Date(l.created_at).toLocaleTimeString()}</span>
              {l.stage && <span className="tag">{l.stage}</span>}
              {l.video_id && <span className="muted small">#{(col.videos.find((v) => v.id === l.video_id)?.position ?? 0) + 1}</span>}
              <span>{l.message}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}


/* ------------------------------------------------------------ docs view */
function DocsCollection({ col, running, tab, setTab, logs, reload }: {
  col: Collection;
  running: boolean;
  tab: Tab;
  setTab: (t: Tab) => void;
  logs: LogEntry[];
  reload: () => void;
}) {
  const nav = useNavigate();
  const toast = useToast();
  const words = col.meta?.words ?? col.pages.reduce((s, p) => s + p.word_count, 0);
  return (
    <div>
      <Link to="/library" className="back"><ArrowLeft size={14} /> Library</Link>
      <div className="collection-header card">
        <div className="docs-icon"><BookText size={36} /></div>
        <div className="grow">
          <div className="row">
            <span className="tag">Documentation</span>
            <StatusBadge status={col.status} stage={col.stage} />
          </div>
          <h1 dir="auto">{col.title}</h1>
          <div className="muted">
            {col.source_url && <a href={col.source_url} target="_blank" rel="noreferrer">{hostOf(col.source_url)} <ExternalLink size={12} /></a>}
            {col.pages.length > 0 && <> · {col.pages.length} pages · {words.toLocaleString()} words · ~{Math.max(1, Math.round(words / 230))} min read</>}
          </div>
          {running && (
            <div className="overall">
              <ProgressBar value={col.progress} />
              <span className="muted small">
                {col.stage === "crawling" ? `Reading pages… ${col.meta?.pages_found ?? 0} found` : col.stage === "structuring" ? "Designing your course…" : "Waiting…"}
              </span>
            </div>
          )}
          {col.stage === "crawling" && col.meta?.current_url && <div className="muted small ellipsis">{col.meta.current_url}</div>}
          {col.error && <div className="alert error">{col.error}</div>}
          {(col.meta?.warnings ?? []).map((w, i) => <div key={i} className="alert warn">{w}</div>)}
          <div className="row">
            {col.course_id && !running && (
              <button className="btn primary" onClick={() => nav(`/learn/${col.course_id}`)}><GraduationCap size={16} /> Open my course</button>
            )}
            {!running && (
              <button className="btn ghost sm" onClick={async () => {
                try { await api.recrawl(col.id); toast("Re-reading the documentation…", "info"); reload(); } catch (e) { toast((e as Error).message, "error"); }
              }}><RefreshCw size={14} /> Re-crawl</button>
            )}
            <button className="btn ghost sm danger" onClick={async () => {
              if (!confirm("Delete this documentation and its course?")) return;
              await api.deleteCollection(col.id);
              nav("/library");
            }}>Delete</button>
          </div>
        </div>
      </div>

      <div className="tabs big">
        <button className={tab === "pages" ? "active" : ""} onClick={() => setTab("pages")}>Pages ({col.pages.length})</button>
        <button className={tab === "ask" ? "active" : ""} onClick={() => setTab("ask")}>Ask the docs</button>
        <button className={tab === "logs" ? "active" : ""} onClick={() => setTab("logs")}>Processing log</button>
      </div>

      {tab === "pages" && (
        <div className="card list-card">
          {col.pages.length === 0 && <p className="muted">{running ? "Pages will appear here as they are read…" : "No pages."}</p>}
          {col.pages.map((p) => (
            <Link key={p.id} to={`/collections/${col.id}/pages/${p.id}`} className="list-row">
              <span className="pos">{p.position + 1}</span>
              <FileText size={16} />
              <div className="grow">
                <strong dir="auto">{p.title}</strong>
                <div className="muted small ellipsis">{p.headings.slice(1, 6).join(" · ") || p.url}</div>
              </div>
              <span className="muted small nowrap">{p.word_count.toLocaleString()} words</span>
            </Link>
          ))}
        </div>
      )}
      {tab === "ask" && <div className="card"><AskPanel collectionId={col.id} placeholder="e.g. How do I install it? What does this option do?" /></div>}
      {tab === "logs" && (
        <div className="card logs">
          {logs.length === 0 && <p className="muted">No log entries yet.</p>}
          {logs.map((l) => (
            <div key={l.id} className={`log log-${l.level}`}>
              <span className="muted small nowrap">{new Date(l.created_at).toLocaleTimeString()}</span>
              {l.stage && <span className="tag">{l.stage}</span>}
              <span>{l.message}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
