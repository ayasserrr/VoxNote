import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { ProgressBar, StatusBadge } from "../components/StatusBadge";
import type { CollectionSummary, SearchHit } from "../types";
import { isActive, timeAgo } from "../utils";
import Timestamp from "../components/Timestamp";

export default function LibraryPage() {
  const [items, setItems] = useState<CollectionSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [q, setQ] = useState("");
  const [hits, setHits] = useState<SearchHit[] | null>(null);

  useEffect(() => {
    let timer: ReturnType<typeof setTimeout>;
    const load = async () => {
      try {
        const data = await api.collections();
        setItems(data);
        if (data.some((c) => isActive(c.status))) timer = setTimeout(load, 3000);
      } catch (e) {
        setError((e as Error).message);
      }
    };
    load();
    return () => clearTimeout(timer);
  }, []);

  const search = async (e: React.FormEvent) => {
    e.preventDefault();
    if (q.trim().length < 2) return setHits(null);
    setHits(await api.search(q.trim()));
  };

  return (
    <div>
      <div className="page-head">
        <h1>Your library</h1>
        <form onSubmit={search} className="search-form">
          <input dir="auto" placeholder="Search across all transcripts…" value={q} onChange={(e) => setQ(e.target.value)} />
          <button className="btn">Search</button>
        </form>
      </div>
      {hits && (
        <div className="card">
          <div className="page-head">
            <h3>Search results ({hits.length})</h3>
            <button className="btn ghost sm" onClick={() => setHits(null)}>Clear</button>
          </div>
          {hits.length === 0 && <p className="muted">Nothing found.</p>}
          <ul className="hits">
            {hits.map((h, i) => (
              <li key={i}>
                <div className="source-head">
                  <Link to={`/videos/${h.video_id}`}><strong>{h.video_title}</strong></Link>
                  <Timestamp youtubeId={h.youtube_id} start={h.start} end={h.end} />
                </div>
                <p dir="auto">{h.text.slice(0, 300)}…</p>
              </li>
            ))}
          </ul>
        </div>
      )}
      {error && <div className="alert error">{error}</div>}
      {!items && !error && <div className="spinner" />}
      {items && items.length === 0 && (
        <div className="empty card">
          <p>No documents yet.</p>
          <Link to="/" className="btn primary">Process your first video</Link>
        </div>
      )}
      <div className="grid">
        {items?.map((c) => (
          <Link key={c.id} to={`/collections/${c.id}`} className="card collection-card">
            <div className="thumb">
              {c.thumbnail_url ? <img src={c.thumbnail_url} alt="" /> : <div className="thumb-placeholder">🎧</div>}
              <span className="kind">{c.kind === "playlist" ? `Playlist · ${c.video_count}` : c.kind === "upload" ? "Upload" : "Video"}</span>
            </div>
            <div className="collection-body">
              <h3 dir="auto">{c.title}</h3>
              <div className="muted small">{c.channel ?? ""} · {timeAgo(c.created_at)}</div>
              <div className="row">
                <StatusBadge status={c.status} stage={c.stage} />
                <span className="muted small">{c.completed_count}/{c.video_count} done{c.failed_count ? ` · ${c.failed_count} failed` : ""}</span>
              </div>
              {isActive(c.status) && <ProgressBar value={c.progress} />}
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}
