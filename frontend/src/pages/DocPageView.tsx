import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ArrowLeft, ExternalLink } from "lucide-react";
import { api } from "../api";
import Markdown from "../components/Markdown";
import { Spinner } from "../components/ui";
import type { PageDetail } from "../types";

export default function DocPageView() {
  const { id, pageId } = useParams();
  const [p, setP] = useState<PageDetail | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    setP(null);
    api.page(id!, pageId!).then(setP).catch((e) => setErr(e.message));
  }, [id, pageId]);
  if (err) return <div className="alert error">{err}</div>;
  if (!p) return <Spinner />;
  return (
    <div className="narrow">
      <Link to={`/collections/${id}`} className="back"><ArrowLeft size={14} /> All pages</Link>
      <article className="card doc-reader">
        <div className="muted small row">
          Page {p.position + 1} · {p.word_count.toLocaleString()} words ·
          <a href={p.url} target="_blank" rel="noreferrer">Open original <ExternalLink size={12} /></a>
        </div>
        <Markdown text={p.content} />
      </article>
    </div>
  );
}
