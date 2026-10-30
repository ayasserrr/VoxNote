import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, Award, Brain, BookText, CheckCircle2, Circle, Clock, ExternalLink, Lock, PlayCircle, RotateCcw, Target, Trash2, Trophy, Youtube } from "lucide-react";
import { api } from "../api";
import { StatusBadge } from "../components/StatusBadge";
import { useToast } from "../components/Toast";
import { ProgressRing, Spinner, Stat } from "../components/ui";
import type { Course, LessonSummary } from "../types";
import { LEVEL_LABEL, pct } from "../utils";

export default function CoursePage() {
  const { courseId } = useParams();
  const nav = useNavigate();
  const toast = useToast();
  const [c, setC] = useState<Course | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const load = useCallback(() => api.course(courseId!).then(setC).catch((e) => setErr(e.message)), [courseId]);
  useEffect(() => {
    load();
  }, [load]);
  useEffect(() => {
    if (!c || (c.status !== "queued" && c.status !== "processing")) return;
    const t = setInterval(load, 2500);
    return () => clearInterval(t);
  }, [c, load]);

  const modules = useMemo(() => {
    const m = new Map<number, { title: string; lessons: LessonSummary[] }>();
    c?.lessons.forEach((l) => {
      if (!m.has(l.module_index)) m.set(l.module_index, { title: l.module_title, lessons: [] });
      m.get(l.module_index)!.lessons.push(l);
    });
    return [...m.values()];
  }, [c]);

  if (err) return <div className="alert error">{err}</div>;
  if (!c) return <Spinner />;
  const building = c.status === "queued" || c.status === "processing";
  const s = c.stats;
  const allDone = s.lesson_count > 0 && s.completed_count === s.lesson_count;
  const ringValue = (s.completed_count + (s.certified ? 1 : 0)) / Math.max(s.lesson_count + (s.exam_lesson_id ? 1 : 0), 1);

  return (
    <div>
      <Link to="/learn" className="back"><ArrowLeft size={14} /> Learning Hub</Link>
      <section className="course-hero card">
        <div className="grow">
          <div className="row">
            <span className="tag">{c.collection_kind === "docs" ? <><BookText size={12} /> Documentation</> : <><Youtube size={12} /> Video course</>}</span>
            <span className="tag">{LEVEL_LABEL[c.level]}</span>
            {building && <StatusBadge status="processing" stage="structuring" />}
          </div>
          <h1 dir="auto">{c.title}</h1>
          {c.description && <p className="lead" dir="auto">{c.description}</p>}
          {c.error && <div className="alert error">{c.error}</div>}
          <div className="row">
            {!building && s.next_lesson_id && (
              <button className="btn primary lg" onClick={() => nav(`/learn/${c.id}/lessons/${s.next_lesson_id}`)}>
                <PlayCircle size={18} /> {s.completed_count ? "Continue" : "Start learning"}
              </button>
            )}
            {allDone && !s.certified && s.exam_lesson_id && (
              <button className="btn primary lg" onClick={() => nav(`/learn/${c.id}/lessons/${s.exam_lesson_id}`)}>
                <Trophy size={18} /> Take the final exam
              </button>
            )}
            <Link className="btn ghost" to={`/review?course=${c.id}`}><Brain size={14} /> Review mistakes</Link>
            <Link className="btn ghost" to={`/collections/${c.collection_id}`}>Source material</Link>
            {c.source_url && <a className="btn ghost" href={c.source_url} target="_blank" rel="noreferrer"><ExternalLink size={14} /> Original</a>}
          </div>
        </div>
        <ProgressRing value={ringValue} size={120} stroke={10} label={<><strong>{Math.round(ringValue * 100)}%</strong><small>complete</small></>} />
      </section>

      {s.certified && (
        <section className="certificate">
          <Award size={44} />
          <div>
            <div className="cert-eyebrow">Certificate of completion</div>
            <h2 dir="auto">{c.title}</h2>
            <p>
              Completed all {s.lesson_count} lessons and passed the final exam with <strong>{pct(s.exam_score)}</strong>
              {s.certified_at ? ` on ${new Date(s.certified_at).toLocaleDateString()}` : ""}. Average lesson score {pct(s.average_score)} · {s.xp} XP.
            </p>
          </div>
        </section>
      )}

      {building ? (
        <div className="card center building">
          <Spinner label="Designing your course: reading the material and planning modules and lessons…" />
        </div>
      ) : (
        <div className="course-layout">
          <div>
            {modules.map((m, mi) => (
              <section key={mi} className="card module">
                <div className="module-head">
                  <span className="module-n">{mi + 1}</span>
                  <h3 dir="auto">{m.title}</h3>
                  <span className="muted small">{m.lessons.filter((l) => l.status === "completed").length}/{m.lessons.length}</span>
                </div>
                <ol className="lessons">
                  {m.lessons.map((l) => (
                    <li key={l.id}>
                      <Link to={`/learn/${c.id}/lessons/${l.id}`} className={`lesson-row st-${l.status} ${l.kind === "exam" ? "exam-row" : ""}`}>
                        <span className="lesson-icon">
                          {l.kind === "exam" ? <Trophy size={20} /> : l.status === "completed" ? <CheckCircle2 size={20} /> : l.status === "available" ? <PlayCircle size={20} /> : <Lock size={18} />}
                        </span>
                        <div className="grow">
                          <div className="lesson-title" dir="auto">{l.kind === "exam" ? l.title : `${l.position + 1}. ${l.title}`}</div>
                          {l.objectives.length > 0 && <div className="muted small" dir="auto">{l.objectives.slice(0, 2).join(" · ")}</div>}
                        </div>
                        <span className="muted small nowrap"><Clock size={12} /> {l.estimated_minutes} min</span>
                        {l.best_score != null && <span className={`score-chip ${l.best_score >= 0.7 ? "ok" : "low"}`}>{pct(l.best_score)}</span>}
                      </Link>
                    </li>
                  ))}
                </ol>
              </section>
            ))}
          </div>
          <aside className="course-side">
            <div className="stats-col">
              <Stat icon={<CheckCircle2 size={18} />} label="Lessons done" value={`${s.completed_count}/${s.lesson_count}`} tone="green" />
              <Stat icon={<Target size={18} />} label="Average score" value={pct(s.average_score)} tone="violet" />
              <Stat icon={<Trophy size={18} />} label="XP" value={s.xp} tone="amber" />
              <Stat icon={<Clock size={18} />} label="Total time" value={`~${s.minutes_total} min`} tone="blue" />
            </div>
            {c.outcomes.length > 0 && (
              <div className="card">
                <h4>After this course you can</h4>
                <ul className="checklist">
                  {c.outcomes.map((o, i) => (
                    <li key={i} dir="auto"><Circle size={8} /> {o}</li>
                  ))}
                </ul>
              </div>
            )}
            <div className="card side-actions">
              <button className="btn ghost sm" onClick={async () => {
                if (!confirm("Reset your progress for this course?")) return;
                setC(await api.resetCourse(c.id));
                toast("Progress reset", "info");
              }}><RotateCcw size={14} /> Reset progress</button>
              <button className="btn ghost sm danger" onClick={async () => {
                if (!confirm("Delete this course? (the source material is kept)")) return;
                await api.deleteCourse(c.id);
                nav("/learn");
              }}><Trash2 size={14} /> Delete course</button>
            </div>
          </aside>
        </div>
      )}
    </div>
  );
}
