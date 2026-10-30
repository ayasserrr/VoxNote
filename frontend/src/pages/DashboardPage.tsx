import { useEffect, useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ArrowRight, BookText, Brain, FileText, GraduationCap, ListChecks, Sparkles, Trophy, Youtube } from "lucide-react";
import { api, isYouTubeUrl } from "../api";
import { useAuth } from "../auth";
import CourseCard from "../components/CourseCard";
import { DEFAULT_SETTINGS } from "../components/SettingsForm";
import { ProgressBar, StatusBadge } from "../components/StatusBadge";
import { useToast } from "../components/Toast";
import { EmptyState, Skeleton, Stat } from "../components/ui";
import type { Dashboard } from "../types";
import { greeting, isActive, pct, timeAgo } from "../utils";

export default function DashboardPage() {
  const { user } = useAuth();
  const nav = useNavigate();
  const toast = useToast();
  const [d, setD] = useState<Dashboard | null>(null);
  const [url, setUrl] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let t: ReturnType<typeof setTimeout>;
    const load = () =>
      api
        .dashboard()
        .then((x) => {
          setD(x);
          if (x.recent.some((r) => isActive(r.status))) t = setTimeout(load, 4000);
        })
        .catch((e) => toast((e as Error).message, "error"));
    load();
    return () => clearTimeout(t);
  }, [toast]);

  const quickStart = async (e: FormEvent) => {
    e.preventDefault();
    const u = url.trim();
    if (!u) return;
    setBusy(true);
    try {
      const col = isYouTubeUrl(u)
        ? await api.createCollection(u, DEFAULT_SETTINGS)
        : await api.createDocs({ url: u, max_pages: 40, same_path_only: true, level: "beginner", language: "auto" });
      toast(isYouTubeUrl(u) ? "Processing started" : "Reading the documentation…", "success");
      nav(`/collections/${col.id}`);
    } catch (err) {
      toast((err as Error).message, "error");
      setBusy(false);
    }
  };

  const name = user?.full_name?.split(" ")[0];
  return (
    <div className="dashboard">
      <section className="hero-card">
        <div>
          <span className="eyebrow"><Sparkles size={14} /> Your AI learning hub</span>
          <h1>
            {greeting()}
            {name ? `, ${name}` : ""}!
          </h1>
          <p>Paste a YouTube video, a playlist, or a documentation website. VoxNote turns it into notes, a course and quizzes.</p>
          <form className="quick" onSubmit={quickStart}>
            <input
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="https://youtube.com/playlist?list=…   or   https://docs.python.org/3/tutorial/"
            />
            <button className="btn primary" disabled={busy || !url.trim()}>
              {busy ? "Starting…" : "Start"} <ArrowRight size={16} />
            </button>
          </form>
          <div className="quick-hints">
            {url.trim() && (
              <span className="tag">{isYouTubeUrl(url) ? <><Youtube size={12} /> YouTube → notes &amp; PDF</> : <><BookText size={12} /> Documentation → course</>}</span>
            )}
            <Link to="/new">More options</Link>
          </div>
        </div>
      </section>

      {!d ? (
        <Skeleton lines={4} />
      ) : (
        <>
          <section className="stats-grid">
            <Stat icon={<Trophy size={20} />} label="XP earned" value={d.xp} tone="amber" />
            <Stat icon={<ListChecks size={20} />} label="Lessons completed" value={d.lessons_completed} tone="green" />
            <Stat icon={<Brain size={20} />} label="Average quiz score" value={pct(d.average_score)} tone="violet" />
            <Stat icon={<FileText size={20} />} label="Documents generated" value={d.documents} tone="blue" />
          </section>

          <section>
            <div className="section-head">
              <h2>Continue learning</h2>
              <Link to="/learn">All courses <ArrowRight size={14} /></Link>
            </div>
            {d.continue_learning.length ? (
              <div className="grid">
                {d.continue_learning.map((c) => (
                  <CourseCard key={c.id} c={c} />
                ))}
              </div>
            ) : (
              <EmptyState
                icon={<GraduationCap size={28} />}
                title="No courses yet"
                text="Add a documentation site to get a step-by-step course, or open a processed video and click “Start learning”."
                action={<Link className="btn primary" to="/new?tab=docs">Learn from documentation</Link>}
              />
            )}
          </section>

          <section>
            <div className="section-head">
              <h2>Recent</h2>
              <Link to="/library">Library <ArrowRight size={14} /></Link>
            </div>
            {d.recent.length === 0 ? (
              <p className="muted">Nothing processed yet.</p>
            ) : (
              <div className="list-card card">
                {d.recent.map((c) => (
                  <Link key={c.id} to={`/collections/${c.id}`} className="list-row">
                    <div className={`source-icon ${c.kind === "docs" ? "docs" : "yt"}`}>
                      {c.kind === "docs" ? <BookText size={16} /> : <Youtube size={16} />}
                    </div>
                    <div className="grow">
                      <strong dir="auto">{c.title}</strong>
                      <div className="muted small">
                        {c.kind === "docs" ? `${c.page_count} pages` : `${c.video_count} video${c.video_count === 1 ? "" : "s"}`} · {timeAgo(c.created_at)}
                      </div>
                      {isActive(c.status) && <ProgressBar value={c.progress} />}
                    </div>
                    <StatusBadge status={c.status} stage={c.stage} />
                  </Link>
                ))}
              </div>
            )}
          </section>
        </>
      )}
    </div>
  );
}
