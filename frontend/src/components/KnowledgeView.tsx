import { useState } from "react";
import type { Knowledge } from "../types";
import Timestamp from "./Timestamp";

const TABS = ["Overview", "Concepts", "Technical", "Examples", "Takeaways", "Glossary", "Questions"] as const;
type Tab = (typeof TABS)[number];

export default function KnowledgeView({ k, youtubeId }: { k: Knowledge; youtubeId: string | null }) {
  const [tab, setTab] = useState<Tab>("Overview");
  const rtl = k.output_language === "ar" || k.output_language === "bilingual";
  const counts: Partial<Record<Tab, number>> = {
    Concepts: k.concepts.length,
    Technical: k.technical.length,
    Examples: k.examples.length,
    Glossary: k.glossary.length,
    Questions: k.questions.length,
  };
  return (
    <div className="knowledge">
      <div className="tabs">
        {TABS.map((t) => (
          <button key={t} className={t === tab ? "active" : ""} onClick={() => setTab(t)}>
            {t}
            {counts[t] ? <span className="count">{counts[t]}</span> : null}
          </button>
        ))}
      </div>
      <div className="tab-body" dir={rtl ? "rtl" : "auto"}>
        {tab === "Overview" && (
          <>
            {k.overview.split("\n\n").map((p, i) => (
              <p key={i}>{p}</p>
            ))}
            {k.learning_objectives.length > 0 && (
              <>
                <h4>Learning objectives</h4>
                <ul>{k.learning_objectives.map((x, i) => <li key={i}>{x}</li>)}</ul>
              </>
            )}
            {k.prerequisites.length > 0 && (
              <>
                <h4>Prerequisites</h4>
                <ul>{k.prerequisites.map((x, i) => <li key={i}>{x}</li>)}</ul>
              </>
            )}
            <h4>Chapters</h4>
            <div className="chapters">
              {k.chapters.map((c, i) => (
                <div key={i} className="chapter">
                  <div className="chapter-head">
                    <strong>{c.title}</strong>
                    <Timestamp youtubeId={youtubeId} start={c.start} end={c.end} />
                  </div>
                  <p>{c.summary}</p>
                </div>
              ))}
            </div>
          </>
        )}
        {tab === "Concepts" &&
          k.concepts.map((c, i) => (
            <article key={i} className="concept">
              <header>
                <h3>{c.name}</h3>
                <Timestamp youtubeId={youtubeId} start={c.start} end={c.end} />
              </header>
              {c.definition && <p className="definition">{c.definition}</p>}
              {c.explanation && c.explanation.split("\n\n").map((p, j) => <p key={j}>{p}</p>)}
              {c.instructor_points.length > 0 && (
                <>
                  <h5>What the speaker said</h5>
                  <ul>{c.instructor_points.map((x, j) => <li key={j}>{x}</li>)}</ul>
                </>
              )}
              {c.examples.length > 0 && (
                <>
                  <h5>Examples</h5>
                  <ul>{c.examples.map((x, j) => <li key={j}>{x}</li>)}</ul>
                </>
              )}
              {c.ai_clarification && (
                <div className="ai-note">
                  <strong>AI-added clarification</strong> (not from the video)
                  <p>{c.ai_clarification}</p>
                </div>
              )}
              {c.related.length > 0 && <div className="tags">{c.related.map((r, j) => <span key={j} className="tag">{r}</span>)}</div>}
            </article>
          ))}
        {tab === "Technical" &&
          (k.technical.length ? (
            k.technical.map((t, i) => (
              <article key={i} className="concept">
                <header>
                  <h3>
                    {t.title || t.kind} <span className="tag">{t.kind}{t.language ? ` · ${t.language}` : ""}</span>
                  </h3>
                  <Timestamp youtubeId={youtubeId} start={t.start} />
                </header>
                {t.content && <pre dir="ltr"><code>{t.content}</code></pre>}
                {t.explanation && <p>{t.explanation}</p>}
              </article>
            ))
          ) : (
            <p className="muted">No code, equations or tools were detected.</p>
          ))}
        {tab === "Examples" &&
          (k.examples.length ? (
            k.examples.map((e, i) => (
              <div key={i} className="example">
                <div className="chapter-head">
                  <strong>{e.title || `Example ${i + 1}`}</strong>
                  <Timestamp youtubeId={youtubeId} start={e.start} />
                </div>
                <p>{e.description}</p>
              </div>
            ))
          ) : (
            <p className="muted">No examples recorded.</p>
          ))}
        {tab === "Takeaways" && (
          <>
            <ul className="takeaways">{k.takeaways.map((x, i) => <li key={i}>{x}</li>)}</ul>
            {k.key_points.length > 0 && (
              <>
                <h4>Key points</h4>
                <ul>
                  {k.key_points.map((p, i) => (
                    <li key={i}>
                      {p.text} <Timestamp youtubeId={youtubeId} start={p.start} />
                    </li>
                  ))}
                </ul>
              </>
            )}
          </>
        )}
        {tab === "Glossary" && (
          <table className="table">
            <thead>
              <tr><th>Term</th><th>Definition</th><th>Translation</th></tr>
            </thead>
            <tbody>
              {k.glossary.map((g, i) => (
                <tr key={i}><td><strong>{g.term}</strong></td><td>{g.definition}</td><td>{g.translation}</td></tr>
              ))}
            </tbody>
          </table>
        )}
        {tab === "Questions" && <Questions items={k.questions} />}
      </div>
    </div>
  );
}

export function Questions({ items }: { items: { question: string; answer: string; difficulty: string }[] }) {
  const [open, setOpen] = useState<Set<number>>(new Set());
  return (
    <ol className="questions">
      {items.map((q, i) => (
        <li key={i}>
          <div className="q">
            {q.question} <span className={`tag diff-${q.difficulty}`}>{q.difficulty}</span>
          </div>
          {q.answer &&
            (open.has(i) ? (
              <p className="answer">{q.answer}</p>
            ) : (
              <button className="btn ghost sm" onClick={() => setOpen(new Set(open).add(i))}>Show answer</button>
            ))}
        </li>
      ))}
    </ol>
  );
}
