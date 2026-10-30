import { useCallback, useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { ArrowRight, Brain, CheckCircle2, Lightbulb, MessageCircle, PartyPopper, RefreshCw, XCircle } from "lucide-react";
import { api } from "../api";
import Markdown from "../components/Markdown";
import { useToast } from "../components/Toast";
import { EmptyState, PageHeader, Skeleton, Stat } from "../components/ui";
import type { ReviewAnswer, ReviewCard, ReviewQueue } from "../types";

const BOX_LABEL = ["New mistake", "Learning", "Getting there", "Almost", "Strong", "Mastered"];

export default function ReviewPage() {
  const toast = useToast();
  const [params] = useSearchParams();
  const courseId = params.get("course") ?? undefined;
  const [queue, setQueue] = useState<ReviewQueue | null>(null);
  const [cards, setCards] = useState<ReviewCard[]>([]);
  const [i, setI] = useState(0);
  const [answer, setAnswer] = useState<number | boolean | string | undefined>(undefined);
  const [result, setResult] = useState<ReviewAnswer | null>(null);
  const [busy, setBusy] = useState(false);
  const [session, setSession] = useState({ right: 0, wrong: 0 });

  const load = useCallback(async () => {
    try {
      const q = await api.review(courseId);
      setQueue(q);
      setCards(q.cards);
      setI(0);
      setAnswer(undefined);
      setResult(null);
      setSession({ right: 0, wrong: 0 });
    } catch (e) {
      toast((e as Error).message, "error");
    }
  }, [courseId, toast]);
  useEffect(() => {
    load();
  }, [load]);

  const check = async () => {
    const card = cards[i];
    if (answer === undefined || answer === "") return;
    setBusy(true);
    try {
      const r = await api.answerReview(card.id, answer);
      setResult(r);
      setSession((s) => (r.result.correct ? { ...s, right: s.right + 1 } : { ...s, wrong: s.wrong + 1 }));
    } catch (e) {
      toast((e as Error).message, "error");
    } finally {
      setBusy(false);
    }
  };
  const next = () => {
    setI(i + 1);
    setAnswer(undefined);
    setResult(null);
  };

  if (!queue) return <Skeleton lines={5} />;
  const card = cards[i];
  const finished = cards.length > 0 && i >= cards.length;

  return (
    <div className="narrow">
      <PageHeader
        icon={<Brain size={22} />}
        title="Review"
        subtitle="Spaced repetition: questions you got wrong come back here — first after 10 minutes, then after 1, 3, 7 and 16 days — until you master them."
      />
      <div className="stats-grid three">
        <Stat icon={<RefreshCw size={18} />} label="Due now" value={queue.due} tone="amber" />
        <Stat icon={<Brain size={18} />} label="Scheduled later" value={queue.upcoming} tone="blue" />
        <Stat icon={<CheckCircle2 size={18} />} label="Mastered" value={queue.mastered} tone="green" />
      </div>

      {cards.length === 0 && (
        <EmptyState
          icon={<PartyPopper size={28} />}
          title={queue.total ? "All caught up!" : "Nothing to review yet"}
          text={
            queue.total
              ? "No questions are due right now. Come back later — reviewing at the right time is what makes knowledge stick."
              : "When you miss a quiz question in a lesson, it is added here so you can practise it again later."
          }
          action={<Link className="btn primary" to="/learn">Go to my courses</Link>}
        />
      )}

      {finished && (
        <div className="card center review-done">
          <PartyPopper size={34} />
          <h2>Session complete</h2>
          <p className="muted">
            {session.right} correct · {session.wrong} to practise again
          </p>
          <div className="row" style={{ justifyContent: "center" }}>
            <button className="btn primary" onClick={load}><RefreshCw size={16} /> Check for more</button>
            <Link className="btn ghost" to="/learn">Back to courses</Link>
          </div>
        </div>
      )}

      {card && !finished && (
        <section className="card review-card">
          <div className="review-meta">
            <span className="muted small">
              Card {i + 1} of {cards.length} · <Link to={`/learn/${card.course_id}/lessons/${card.lesson_id}`}>{card.lesson_title}</Link>
            </span>
            <span className={`tag box-${card.box}`}>{BOX_LABEL[card.box]}</span>
          </div>
          <div className="review-progress"><div style={{ width: `${(i / cards.length) * 100}%` }} /></div>
          <h2 dir="auto"><Markdown text={card.question.question} /></h2>

          {card.question.type === "mcq" && (
            <div className="options">
              {card.question.options.map((o, k) => (
                <button key={k} disabled={!!result}
                  className={`option ${answer === k ? "selected" : ""} ${result && result.result.correct_answer === o ? "right" : ""} ${result && answer === k && !result.result.correct ? "wrong" : ""}`}
                  onClick={() => setAnswer(k)} dir="auto">
                  <span className="opt-letter">{String.fromCharCode(65 + k)}</span>
                  <span className="grow"><Markdown text={o} /></span>
                </button>
              ))}
            </div>
          )}
          {card.question.type === "true_false" && (
            <div className="options tf">
              {[true, false].map((v) => (
                <button key={String(v)} disabled={!!result} className={`option ${answer === v ? "selected" : ""}`} onClick={() => setAnswer(v)}>
                  {v ? <CheckCircle2 size={18} /> : <XCircle size={18} />} {v ? "True" : "False"}
                </button>
              ))}
            </div>
          )}
          {card.question.type === "short" && (
            <textarea dir="auto" rows={3} disabled={!!result} placeholder="Your answer…" value={(answer as string) ?? ""}
              onChange={(e) => setAnswer(e.target.value)} />
          )}

          {result && (
            <div className={`review-result ${result.result.correct ? "ok" : "bad"}`}>
              <strong>
                {result.result.correct ? <><CheckCircle2 size={18} /> Correct!</> : <><XCircle size={18} /> Not quite</>}
              </strong>
              {!result.result.correct && (
                <div>Correct answer: <strong className="inline-md"><Markdown text={result.result.correct_answer} /></strong></div>
              )}
              {result.result.feedback && <div className="feedback"><MessageCircle size={14} /> {result.result.feedback}</div>}
              {result.result.explanation && <div className="why"><Lightbulb size={14} /> {result.result.explanation}</div>}
              <div className="muted small">
                {result.mastered ? "Mastered — this card is retired. 🎉" : `Next review: ${new Date(result.next_due_at).toLocaleString()}`}
              </div>
            </div>
          )}

          <div className="quiz-actions">
            <span />
            {!result ? (
              <button className="btn primary" disabled={busy || answer === undefined || answer === ""} onClick={check}>
                {busy ? "Checking…" : "Check"}
              </button>
            ) : (
              <button className="btn primary" onClick={next}>
                {i + 1 < cards.length ? "Next card" : "Finish"} <ArrowRight size={16} />
              </button>
            )}
          </div>
        </section>
      )}
    </div>
  );
}
