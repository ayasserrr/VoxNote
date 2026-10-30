import { useRef, useState, type FormEvent } from "react";
import { api } from "../api";
import type { AskResponse } from "../types";
import Markdown from "./Markdown";
import Timestamp from "./Timestamp";

interface Turn {
  question: string;
  response?: AskResponse;
  error?: string;
}

export default function AskPanel({
  collectionId,
  videoId,
  placeholder,
}: {
  collectionId?: string;
  videoId?: string;
  placeholder?: string;
}) {
  const [turns, setTurns] = useState<Turn[]>([]);
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(false);
  const refs = useRef<Record<string, HTMLLIElement | null>>({});

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    const question = q.trim();
    if (!question || busy) return;
    setBusy(true);
    setQ("");
    const idx = turns.length;
    setTurns((t) => [...t, { question }]);
    try {
      const response = await api.ask(question, { collection_id: collectionId, video_id: videoId });
      setTurns((t) => t.map((x, i) => (i === idx ? { ...x, response } : x)));
    } catch (err) {
      setTurns((t) => t.map((x, i) => (i === idx ? { ...x, error: (err as Error).message } : x)));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="ask">
      {turns.length === 0 && (
        <p className="muted">
          Ask anything about your processed videos and documentation. Answers are grounded in the sources and cite them — click a number to jump to it.
        </p>
      )}
      {turns.map((t, ti) => (
        <div key={ti} className="turn">
          <div className="question" dir="auto">{t.question}</div>
          {!t.response && !t.error && <div className="dots"><i /><i /><i /></div>}
          {t.error && <div className="alert error">{t.error}</div>}
          {t.response && (
            <div className="answer-card">
              <Markdown
                text={t.response.answer}
                onCite={(n) => refs.current[`${ti}-${n}`]?.scrollIntoView({ behavior: "smooth", block: "center" })}
              />
              {t.response.sources.length > 0 && (
                <details open>
                  <summary>Sources ({t.response.sources.length})</summary>
                  <ol className="sources">
                    {t.response.sources.map((s) => (
                      <li key={s.ref} ref={(el) => (refs.current[`${ti}-${s.ref}`] = el)}>
                        <div className="source-head">
                          <strong>[{s.ref}] {s.video_title}</strong>
                          {s.kind === "page" ? (
                            s.url && <a className="ts" href={s.url} target="_blank" rel="noreferrer">open page ↗</a>
                          ) : (
                            <Timestamp youtubeId={s.youtube_id} start={s.start} end={s.end} />
                          )}
                        </div>
                        <p dir="auto">{s.text.length > 320 ? s.text.slice(0, 320) + "…" : s.text}</p>
                      </li>
                    ))}
                  </ol>
                </details>
              )}
              {t.response.provider && <div className="muted small">Answered by {t.response.provider} · {t.response.model}</div>}
            </div>
          )}
        </div>
      ))}
      <form className="ask-form" onSubmit={submit}>
        <input
          dir="auto"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder={placeholder ?? "e.g. Explain the difference between linear and logistic regression"}
        />
        <button className="btn primary" disabled={busy || !q.trim()}>{busy ? "Thinking…" : "Ask"}</button>
      </form>
    </div>
  );
}
