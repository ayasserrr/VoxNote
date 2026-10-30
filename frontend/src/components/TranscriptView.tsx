import { useEffect, useMemo, useState } from "react";
import { api } from "../api";
import type { Transcript } from "../types";
import { LANG_LABEL } from "../utils";
import Timestamp from "./Timestamp";

export default function TranscriptView({ videoId, youtubeId }: { videoId: string; youtubeId: string | null }) {
  const [tr, setTr] = useState<Transcript | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [q, setQ] = useState("");

  useEffect(() => {
    api.transcript(videoId).then(setTr).catch((e) => setErr(e.message));
  }, [videoId]);

  const segments = useMemo(() => {
    if (!tr) return [];
    if (!q.trim()) return tr.segments;
    const needle = q.toLowerCase();
    return tr.segments.filter((s) => s.text.toLowerCase().includes(needle));
  }, [tr, q]);

  if (err) return <p className="muted">{err}</p>;
  if (!tr) return <div className="spinner" />;
  return (
    <div className="transcript">
      <div className="transcript-head">
        <span className="muted">
          {tr.word_count.toLocaleString()} words · source: {tr.source} · {LANG_LABEL[tr.language ?? ""] ?? tr.language}
        </span>
        <input placeholder="Search transcript…" value={q} onChange={(e) => setQ(e.target.value)} />
      </div>
      <div className="segments">
        {segments.map((s) => (
          <div key={s.idx} className="segment">
            <Timestamp youtubeId={youtubeId} start={s.start} />
            <span dir="auto">{s.text}</span>
          </div>
        ))}
        {segments.length === 0 && <p className="muted">No matches.</p>}
      </div>
    </div>
  );
}
