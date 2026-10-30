import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import {
  AlertTriangle,
  ArrowLeft,
  ArrowRight,
  BookOpen,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Clock,
  ExternalLink,
  Lightbulb,
  ListChecks,
  MessageCircle,
  NotebookPen,
  PartyPopper,
  RefreshCw,
  Send,
  Shuffle,
  Sparkles,
  Target,
  Trophy,
  XCircle,
} from "lucide-react";
import { api } from "../api";
import Markdown from "../components/Markdown";
import { useToast } from "../components/Toast";
import { ProgressRing, Spinner } from "../components/ui";
import type { Attempt, Lesson, QuizQuestion } from "../types";
import { fmtTime, pct } from "../utils";

type Phase = "learn" | "quiz" | "result";
type Answer = number | boolean | string;

const MESSAGES = [
  "Reading the source material…",
  "Finding the simplest way to explain it…",
  "Writing examples…",
  "Preparing your quiz…",
];

export default function LessonPage() {
  const { courseId, lessonId } = useParams();
  const nav = useNavigate();
  const toast = useToast();
  const [lesson, setLesson] = useState<Lesson | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [phase, setPhase] = useState<Phase>("learn");
  const [busy, setBusy] = useState<string | null>(null);
  const [msg, setMsg] = useState(0);
  const [answers, setAnswers] = useState<Record<string, Answer>>({});
  const [qi, setQi] = useState(0);
  const [attempt, setAttempt] = useState<Attempt | null>(null);
  const [nextId, setNextId] = useState<string | null>(null);
  const [courseDone, setCourseDone] = useState(false);
  const [tutorOpen, setTutorOpen] = useState(false);
  const top = useRef<HTMLDivElement>(null);

  const prepare = useCallback(async () => {
    setError(null);
    try {
      let l = await api.lesson(lessonId!);
      setLesson(l);
      if (!l.content) {
        setBusy("prepare");
        l = await api.prepareLesson(lessonId!);
        // Someone else (background prefetch) is generating it: poll until ready.
        for (let i = 0; i < 90 && !l.content && l.generating; i++) {
          await new Promise((r) => setTimeout(r, 2000));
          l = await api.lesson(lessonId!);
        }
        if (!l.content) l = await api.prepareLesson(lessonId!);
        setLesson(l);
      }
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(null);
    }
  }, [lessonId]);

  useEffect(() => {
    setPhase("learn");
    setAnswers({});
    setQi(0);
    setAttempt(null);
    setLesson(null);
    setTutorOpen(false);
    prepare();
    top.current?.scrollIntoView();
  }, [prepare]);

  useEffect(() => {
    if (busy !== "prepare") return;
    const t = setInterval(() => setMsg((m) => (m + 1) % MESSAGES.length), 2500);
    return () => clearInterval(t);
  }, [busy]);

  const run = async (key: string, fn: () => Promise<Lesson>, done?: string) => {
    setBusy(key);
    try {
      const l = await fn();
      setLesson(l);
      setAnswers({});
      setQi(0);
      setAttempt(null);
      if (done) toast(done, "success");
      return l;
    } catch (e) {
      toast((e as Error).message, "error");
    } finally {
      setBusy(null);
    }
  };

  const submit = async () => {
    if (!lesson) return;
    setBusy("submit");
    try {
      const r = await api.submitQuiz(lesson.id, answers);
      setAttempt(r.attempt);
      setNextId(r.next_lesson_id);
      setCourseDone(r.course_completed);
      setLesson({ ...lesson, ...r.lesson });
      setPhase("result");
      top.current?.scrollIntoView({ behavior: "smooth" });
    } catch (e) {
      toast((e as Error).message, "error");
    } finally {
      setBusy(null);
    }
  };

  if (error)
    return (
      <div className="narrow">
        <Link to={`/learn/${courseId}`} className="back"><ArrowLeft size={14} /> Back to course</Link>
        <div className="card center">
          <AlertTriangle size={28} />
          <h3>This lesson couldn't be prepared</h3>
          <p className="muted">{error}</p>
          <button className="btn primary" onClick={prepare}><RefreshCw size={16} /> Try again</button>
        </div>
      </div>
    );

  if (!lesson || !lesson.content)
    return (
      <div className="narrow">
        <Link to={`/learn/${courseId}`} className="back"><ArrowLeft size={14} /> Back to course</Link>
        <div className="card lesson-loading">
          <div className="pulse-icon"><Sparkles size={30} /></div>
          <h2 dir="auto">{lesson?.title ?? "Preparing your lesson"}</h2>
          <p className="muted">{MESSAGES[msg]}</p>
          <div className="dots"><i /><i /><i /></div>
        </div>
      </div>
    );

  const c = lesson.content;
  const rtl = lesson.language === "ar" || lesson.language === "bilingual";
  const quiz = lesson.quiz;
  const answered = quiz.filter((q) => answers[q.id] !== undefined && answers[q.id] !== "").length;

  return (
    <div className="lesson-page" ref={top}>
      <div className="lesson-topbar">
        <Link to={`/learn/${courseId}`} className="back"><ArrowLeft size={14} /> {lesson.course_title}</Link>
        <div className="steps-mini">
          <span className={phase === "learn" ? "on" : "done"}><BookOpen size={14} /> Learn</span>
          <ChevronRight size={14} />
          <span className={phase === "quiz" ? "on" : phase === "result" ? "done" : ""}><ListChecks size={14} /> Practice</span>
          <ChevronRight size={14} />
          <span className={phase === "result" ? "on" : ""}><Target size={14} /> Result</span>
        </div>
      </div>

      <div className={`lesson-layout ${tutorOpen ? "with-tutor" : ""}`}>
        <article className="lesson-main" dir={rtl ? "rtl" : "auto"}>
          <header className="lesson-header">
            <div className="muted small" dir="auto">
              {lesson.module_title} · Lesson {lesson.position + 1} · <Clock size={12} /> {lesson.estimated_minutes} min
              {lesson.status === "completed" && <span className="badge badge-completed"> <CheckCircle2 size={12} /> Completed {pct(lesson.best_score)}</span>}
            </div>
            {lesson.kind === "exam" && <span className="exam-badge"><Trophy size={14} /> Final exam · pass to earn your course certificate</span>}
            <h1 dir="auto">{lesson.title}</h1>
            {c.summary && <div className="lead"><Markdown text={c.summary} /></div>}
            {lesson.status === "locked" && phase === "learn" && (
              <div className="alert info">Tip: this lesson builds on the previous ones. You can study it now, but completing earlier lessons first is recommended.</div>
            )}
          </header>

          {phase === "learn" && (
            <>
              {lesson.objectives.length > 0 && (
                <div className="objectives">
                  <strong><Target size={16} /> In this lesson you will</strong>
                  <ul>{lesson.objectives.map((o, i) => <li key={i}>{o}</li>)}</ul>
                </div>
              )}
              {lesson.simplicity > 0 && <div className="alert info"><Sparkles size={14} /> Simplified explanation (level {lesson.simplicity})</div>}
              <section className="lesson-body"><Markdown text={c.explanation} /></section>

              {c.analogy && (
                <div className="callout callout-idea">
                  <Lightbulb size={20} />
                  <div><strong>Think of it like this</strong><Markdown text={c.analogy} /></div>
                </div>
              )}
              {c.example && c.example.content && (
                <section className="example-card">
                  <h3>{c.example.title || "Worked example"}</h3>
                  <Markdown text={c.example.content} />
                </section>
              )}
              {c.key_points.length > 0 && (
                <section className="keypoints">
                  <h3><CheckCircle2 size={18} /> Remember</h3>
                  <ul>{c.key_points.map((k, i) => <li key={i}><Markdown text={k} /></li>)}</ul>
                </section>
              )}
              {c.common_mistakes.length > 0 && (
                <div className="callout callout-warn">
                  <AlertTriangle size={20} />
                  <div>
                    <strong>Common mistakes</strong>
                    <ul>{c.common_mistakes.map((k, i) => <li key={i}><Markdown text={k} /></li>)}</ul>
                  </div>
                </div>
              )}
              <NotesPanel lessonId={lesson.id} initial={lesson.notes ?? ""} />
              {lesson.sources.length > 0 && (
                <div className="sources-box">
                  <strong>Based on</strong>
                  {lesson.sources.map((s, i) =>
                    s.url ? (
                      <a key={i} href={s.url} target="_blank" rel="noreferrer" dir="auto">
                        <ExternalLink size={12} /> {s.title}{s.kind === "video" && s.start != null ? ` @ ${fmtTime(s.start)}` : ""}
                      </a>
                    ) : (
                      <span key={i}>{s.title}</span>
                    ),
                  )}
                </div>
              )}

              <div className="lesson-actions">
                <button className="btn ghost" disabled={!!busy} onClick={() => run("simplify", () => api.simplifyLesson(lesson.id), "Here's a simpler explanation")}>
                  {busy === "simplify" ? <Spinner /> : <Sparkles size={16} />} Explain it more simply
                </button>
                <button className="btn ghost" onClick={() => setTutorOpen(!tutorOpen)}>
                  <MessageCircle size={16} /> Ask the tutor
                </button>
                <button className="btn primary lg" disabled={!quiz.length} onClick={() => { setPhase("quiz"); top.current?.scrollIntoView({ behavior: "smooth" }); }}>
                  {lesson.kind === "exam" ? "Start the final exam" : "I'm ready — test me"} <ArrowRight size={16} />
                </button>
              </div>
            </>
          )}

          {phase === "quiz" && quiz.length > 0 && (
            <QuizView
              quiz={quiz}
              qi={qi}
              setQi={setQi}
              answers={answers}
              setAnswer={(id, v) => setAnswers((a) => ({ ...a, [id]: v }))}
              answered={answered}
              busy={busy === "submit"}
              onSubmit={submit}
              onBack={() => setPhase("learn")}
            />
          )}

          {phase === "result" && attempt && (
            <ResultView
              attempt={attempt}
              passScore={lesson.pass_score}
              courseDone={courseDone}
              busy={busy}
              onNext={() => nextId && nav(`/learn/${courseId}/lessons/${nextId}`)}
              hasNext={!!nextId}
              onRetry={() => { setAnswers({}); setQi(0); setPhase("quiz"); }}
              onNewQuestions={async () => { const l = await run("newquiz", () => api.newQuiz(lesson.id), "New questions ready"); if (l) setPhase("quiz"); }}
              onReview={() => { setPhase("learn"); top.current?.scrollIntoView({ behavior: "smooth" }); }}
              onSimplify={async () => { const l = await run("simplify", () => api.simplifyLesson(lesson.id), "Here's a simpler explanation"); if (l) setPhase("learn"); }}
              onCourse={() => nav(`/learn/${courseId}`)}
            />
          )}

          <nav className="lesson-nav">
            {lesson.prev_lesson_id ? (
              <Link to={`/learn/${courseId}/lessons/${lesson.prev_lesson_id}`}><ChevronLeft size={16} /> Previous lesson</Link>
            ) : <span />}
            {lesson.next_lesson_id && (
              <Link to={`/learn/${courseId}/lessons/${lesson.next_lesson_id}`}>Next lesson <ChevronRight size={16} /></Link>
            )}
          </nav>
        </article>

        {tutorOpen && <TutorPanel lessonId={lesson.id} onClose={() => setTutorOpen(false)} />}
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ quiz */
function QuizView(props: {
  quiz: QuizQuestion[];
  qi: number;
  setQi: (i: number) => void;
  answers: Record<string, Answer>;
  setAnswer: (id: string, v: Answer) => void;
  answered: number;
  busy: boolean;
  onSubmit: () => void;
  onBack: () => void;
}) {
  const { quiz, qi, setQi, answers, setAnswer, answered, busy, onSubmit, onBack } = props;
  const q = quiz[qi];
  const last = qi === quiz.length - 1;
  const value = answers[q.id];
  return (
    <section className="quiz">
      <div className="quiz-progress">
        <span>Question {qi + 1} of {quiz.length}</span>
        <div className="quiz-dots">
          {quiz.map((x, i) => (
            <button key={x.id} className={`${i === qi ? "on" : ""} ${answers[x.id] !== undefined && answers[x.id] !== "" ? "filled" : ""}`} onClick={() => setQi(i)} aria-label={`Question ${i + 1}`} />
          ))}
        </div>
      </div>
      <div className="question-card">
        <span className={`tag diff-${q.difficulty}`}>{q.type === "mcq" ? "Multiple choice" : q.type === "true_false" ? "True or false" : "Short answer"}</span>
        <h2 dir="auto"><Markdown text={q.question} /></h2>
        {q.type === "mcq" && (
          <div className="options">
            {q.options.map((o, i) => (
              <button key={i} className={`option ${value === i ? "selected" : ""}`} onClick={() => setAnswer(q.id, i)} dir="auto">
                <span className="opt-letter">{String.fromCharCode(65 + i)}</span>
                <span className="grow"><Markdown text={o} /></span>
              </button>
            ))}
          </div>
        )}
        {q.type === "true_false" && (
          <div className="options tf">
            {[true, false].map((v) => (
              <button key={String(v)} className={`option ${value === v ? "selected" : ""}`} onClick={() => setAnswer(q.id, v)}>
                {v ? <CheckCircle2 size={18} /> : <XCircle size={18} />} {v ? "True" : "False"}
              </button>
            ))}
          </div>
        )}
        {q.type === "short" && (
          <textarea dir="auto" rows={4} placeholder="Write your answer in your own words (any language)…" value={(value as string) ?? ""}
            onChange={(e) => setAnswer(q.id, e.target.value)} />
        )}
      </div>
      <div className="quiz-actions">
        <button className="btn ghost" onClick={qi === 0 ? onBack : () => setQi(qi - 1)}>
          <ChevronLeft size={16} /> {qi === 0 ? "Back to lesson" : "Previous"}
        </button>
        {!last ? (
          <button className="btn primary" onClick={() => setQi(qi + 1)}>Next <ChevronRight size={16} /></button>
        ) : (
          <button className="btn primary lg" disabled={busy || answered === 0} onClick={onSubmit}>
            {busy ? "Checking your answers…" : `Check my answers (${answered}/${quiz.length})`}
          </button>
        )}
      </div>
    </section>
  );
}

/* ---------------------------------------------------------------- result */
function ResultView(props: {
  attempt: Attempt;
  passScore: number;
  courseDone: boolean;
  busy: string | null;
  hasNext: boolean;
  onNext: () => void;
  onRetry: () => void;
  onNewQuestions: () => void;
  onReview: () => void;
  onSimplify: () => void;
  onCourse: () => void;
}) {
  const { attempt: a, passScore, courseDone, busy, hasNext } = props;
  const correct = a.results.filter((r) => r.correct).length;
  return (
    <section className="result">
      <div className={`result-hero ${a.passed ? "pass" : "fail"}`}>
        <ProgressRing value={a.score} size={110} stroke={10} label={<strong>{Math.round(a.score * 100)}%</strong>} />
        <div>
          {a.passed ? (
            <>
              <h2><PartyPopper size={22} /> {courseDone ? "Course completed!" : "Great job — lesson completed!"}</h2>
              <p>
                You got {correct} of {a.results.length} right{hasNext ? ". The next lesson is unlocked." : "."}
                {correct < a.results.length && " The questions you missed were added to your Review."}
              </p>
            </>
          ) : (
            <>
              <h2>Almost there — let's review</h2>
              <p>
                You need {Math.round(passScore * 100)}% to complete this lesson. Read the corrections below, then try again. The questions you
                missed were also added to your <Link to="/review">Review</Link> for spaced practice.
              </p>
            </>
          )}
          <div className="row">
            {a.passed && hasNext && <button className="btn primary lg" onClick={props.onNext}>Next lesson <ArrowRight size={16} /></button>}
            {a.passed && !hasNext && <button className="btn primary lg" onClick={props.onCourse}>Back to course</button>}
            {!a.passed && <button className="btn primary" onClick={props.onReview}><BookOpen size={16} /> Review the lesson</button>}
            {!a.passed && <button className="btn" disabled={!!busy} onClick={props.onSimplify}><Sparkles size={16} /> Explain more simply</button>}
            <button className="btn ghost" onClick={props.onRetry}><RefreshCw size={16} /> Retry</button>
            <button className="btn ghost" disabled={!!busy} onClick={props.onNewQuestions}>
              {busy === "newquiz" ? <Spinner /> : <Shuffle size={16} />} New questions
            </button>
          </div>
        </div>
      </div>

      <h3>Corrections</h3>
      <ol className="corrections">
        {a.results.map((r) => (
          <li key={r.id} className={r.correct ? "ok" : r.score > 0 ? "partial" : "bad"}>
            <div className="corr-head">
              {r.correct ? <CheckCircle2 size={20} /> : <XCircle size={20} />}
              <div className="grow" dir="auto"><Markdown text={r.question} /></div>
              {r.type === "short" && <span className="score-chip">{Math.round(r.score * 100)}%</span>}
            </div>
            <div className="corr-body" dir="auto">
              <div><span className="muted">Your answer:</span> {r.your_answer === null || r.your_answer === "" ? <em className="muted">no answer</em> : String(r.your_answer)}</div>
              {!r.correct && (
                <div>
                  <span className="muted">{r.type === "short" ? "Model answer:" : "Correct answer:"}</span>{" "}
                  <strong className="inline-md"><Markdown text={r.correct_answer} /></strong>
                </div>
              )}
              {r.feedback && <div className="feedback"><MessageCircle size={14} /> {r.feedback}</div>}
              {r.explanation && <div className="why"><Lightbulb size={14} /> {r.explanation}</div>}
            </div>
          </li>
        ))}
      </ol>
    </section>
  );
}

/* ----------------------------------------------------------------- tutor */
function TutorPanel({ lessonId, onClose }: { lessonId: string; onClose: () => void }) {
  const [msgs, setMsgs] = useState<{ role: "user" | "tutor"; text: string }[]>([]);
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(false);
  const end = useRef<HTMLDivElement>(null);
  useEffect(() => {
    end.current?.scrollIntoView({ behavior: "smooth" });
  }, [msgs]);
  const send = async (e: FormEvent) => {
    e.preventDefault();
    const question = q.trim();
    if (!question || busy) return;
    setQ("");
    setMsgs((m) => [...m, { role: "user", text: question }]);
    setBusy(true);
    try {
      const r = await api.tutor(lessonId, question);
      setMsgs((m) => [...m, { role: "tutor", text: r.answer }]);
    } catch (err) {
      setMsgs((m) => [...m, { role: "tutor", text: `⚠️ ${(err as Error).message}` }]);
    } finally {
      setBusy(false);
    }
  };
  return (
    <aside className="tutor card">
      <div className="tutor-head">
        <strong><MessageCircle size={16} /> Tutor</strong>
        <button className="icon-btn" onClick={onClose} aria-label="Close">×</button>
      </div>
      <div className="tutor-msgs">
        {msgs.length === 0 && (
          <div className="muted small">
            Stuck? Ask anything about this lesson — e.g. <em>"Why do we need this?"</em> or <em>"Can you give another example?"</em>
          </div>
        )}
        {msgs.map((m, i) => (
          <div key={i} className={`bubble ${m.role}`}>{m.role === "tutor" ? <Markdown text={m.text} /> : m.text}</div>
        ))}
        {busy && <div className="bubble tutor"><div className="dots"><i /><i /><i /></div></div>}
        <div ref={end} />
      </div>
      <form onSubmit={send} className="tutor-form">
        <input dir="auto" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Ask a question…" />
        <button className="btn primary icon" disabled={busy || !q.trim()} aria-label="Send"><Send size={16} /></button>
      </form>
    </aside>
  );
}

/* ----------------------------------------------------------------- notes */
function NotesPanel({ lessonId, initial }: { lessonId: string; initial: string }) {
  const [open, setOpen] = useState(!!initial);
  const [text, setText] = useState(initial);
  const [state, setState] = useState<"idle" | "saving" | "saved">("idle");
  const first = useRef(true);
  useEffect(() => {
    if (first.current) {
      first.current = false;
      return;
    }
    setState("saving");
    const t = setTimeout(async () => {
      try {
        await api.saveNotes(lessonId, text);
        setState("saved");
      } catch {
        setState("idle");
      }
    }, 800);
    return () => clearTimeout(t);
  }, [text, lessonId]);
  return (
    <section className="notes">
      <button className="notes-toggle" onClick={() => setOpen(!open)}>
        <NotebookPen size={16} /> My notes {text && !open ? `(${text.split(/\s+/).filter(Boolean).length} words)` : ""}
        <span className="muted small">{state === "saving" ? "Saving…" : state === "saved" ? "Saved" : ""}</span>
      </button>
      {open && (
        <textarea dir="auto" rows={5} value={text} onChange={(e) => setText(e.target.value)}
          placeholder="Write what you learned in your own words — explaining it yourself is the best way to remember it." />
      )}
    </section>
  );
}
