import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api";
import AskPanel from "../components/AskPanel";
import DocumentButtons from "../components/DocumentButtons";
import KnowledgeView from "../components/KnowledgeView";
import { ProgressBar, StatusBadge } from "../components/StatusBadge";
import TranscriptView from "../components/TranscriptView";
import type { VideoDetail } from "../types";
import { fmtTime, isActive, LANG_LABEL, PIPELINE, STAGE_LABEL } from "../utils";

export default function VideoPage() {
  const { id } = useParams();
  const [v, setV] = useState<VideoDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<"notes" | "transcript" | "ask" | "quality">("notes");

  const load = useCallback(() => api.video(id!).then(setV).catch((e) => setError(e.message)), [id]);
  useEffect(() => {
    load();
  }, [load]);
  useEffect(() => {
    if (!v || !isActive(v.status)) return;
    const t = setInterval(load, 2500);
    return () => clearInterval(t);
  }, [v, load]);

  if (error) return <div className="alert error">{error}</div>;
  if (!v) return <div className="spinner" />;

  const q = v.quality ?? {};
  const pct = (x: unknown) => (typeof x === "number" ? `${Math.round(x * 100)}%` : "—");

  return (
    <div>
      <Link to={`/collections/${v.collection_id}`} className="muted small">← Back to collection</Link>
      <div className="card video-header">
        {v.youtube_id ? (
          <iframe
            className="player"
            src={`https://www.youtube-nocookie.com/embed/${v.youtube_id}`}
            title={v.title}
            allow="accelerometer; encrypted-media; gyroscope; picture-in-picture"
            allowFullScreen
          />
        ) : (
          <div className="thumb-placeholder player">🎧</div>
        )}
        <div className="grow">
          <StatusBadge status={v.status} stage={v.stage} />
          <h1 dir="auto">{v.title}</h1>
          <div className="muted">
            {v.channel && <>{v.channel} · </>}
            {v.duration_seconds ? fmtTime(v.duration_seconds) : ""}
            {v.published_at ? ` · ${v.published_at}` : ""}
            {v.language ? ` · ${LANG_LABEL[v.language] ?? v.language}` : ""}
          </div>
          {v.llm_provider && <div className="muted small">Extracted with {v.llm_provider} · {v.llm_model}</div>}
          {isActive(v.status) && (
            <div className="pipeline">
              {PIPELINE.map((s) => {
                const idx = PIPELINE.indexOf(v.stage);
                const me = PIPELINE.indexOf(s);
                return (
                  <div key={s} className={`pstep ${me < idx ? "done" : me === idx ? "current" : ""}`}>
                    <i />
                    <span>{STAGE_LABEL[s]}</span>
                  </div>
                );
              })}
              <ProgressBar value={v.progress} />
            </div>
          )}
          {v.error && <div className={v.status === "failed" ? "alert error" : "alert warn"}>{v.error}</div>}
          {v.status === "failed" && <button className="btn" onClick={async () => setV(await api.retryVideo(v.id))}>↻ Retry this video</button>}
          <DocumentButtons docs={v.documents} />
        </div>
      </div>

      <div className="tabs big">
        <button className={tab === "notes" ? "active" : ""} onClick={() => setTab("notes")}>Knowledge notes</button>
        <button className={tab === "transcript" ? "active" : ""} onClick={() => setTab("transcript")}>Transcript</button>
        <button className={tab === "ask" ? "active" : ""} onClick={() => setTab("ask")}>Ask this video</button>
        <button className={tab === "quality" ? "active" : ""} onClick={() => setTab("quality")}>Quality</button>
      </div>

      <div className="card">
        {tab === "notes" && (v.knowledge ? <KnowledgeView k={v.knowledge} youtubeId={v.youtube_id} /> : <p className="muted">Notes will appear here once AI extraction finishes.</p>)}
        {tab === "transcript" && <TranscriptView videoId={v.id} youtubeId={v.youtube_id} />}
        {tab === "ask" && <AskPanel videoId={v.id} placeholder="Ask a question about this video…" />}
        {tab === "quality" && (
          <div>
            <div className="metrics">
              <div><strong>{pct(q.timeline_coverage)}</strong><span>Timeline coverage</span></div>
              <div><strong>{pct(q.concept_grounding)}</strong><span>Concepts grounded in transcript</span></div>
              <div><strong>{String(q.chunks ?? "—")}</strong><span>Transcript parts analysed</span></div>
              <div><strong>{String(q.llm_calls ?? "—")}</strong><span>LLM calls</span></div>
              <div><strong>{String(q.concepts ?? "—")}</strong><span>Concepts</span></div>
              <div><strong>{String(q.questions ?? "—")}</strong><span>Review questions</span></div>
            </div>
            {(q.warnings ?? []).map((w, i) => <div key={i} className="alert warn">{w}</div>)}
            {q.warnings && q.warnings.length === 0 && <div className="alert ok">No quality issues detected.</div>}
          </div>
        )}
      </div>
    </div>
  );
}
