import { Link } from "react-router-dom";
import { BookText, PlayCircle, Youtube } from "lucide-react";
import type { CourseSummary } from "../types";
import { hostOf, LEVEL_LABEL } from "../utils";
import { StatusBadge } from "./StatusBadge";
import { ProgressRing } from "./ui";

export default function CourseCard({ c }: { c: CourseSummary }) {
  const s = c.stats;
  const ready = c.status === "completed";
  const done = ready && s.lesson_count > 0 && s.completed_count === s.lesson_count;
  return (
    <Link to={`/learn/${c.id}`} className="card course-card">
      <div className="course-card-top">
        <div className={`source-icon ${c.collection_kind === "docs" ? "docs" : "yt"}`}>
          {c.collection_kind === "docs" ? <BookText size={18} /> : <Youtube size={18} />}
        </div>
        <ProgressRing value={s.progress} size={52} stroke={6} />
      </div>
      <h3 dir="auto">{c.title}</h3>
      <div className="muted small">
        {LEVEL_LABEL[c.level]} · {s.lesson_count} lessons · ~{s.minutes_total} min
        {c.collection_kind === "docs" && c.source_url ? ` · ${hostOf(c.source_url)}` : ""}
      </div>
      <div className="course-card-foot">
        {!ready ? (
          <StatusBadge status={c.status} stage="structuring" />
        ) : s.certified ? (
          <span className="badge badge-completed">🏆 Certified · exam {Math.round((s.exam_score ?? 0) * 100)}%</span>
        ) : done ? (
          <span className="continue"><PlayCircle size={16} /> Final exam unlocked</span>
        ) : (
          <span className="continue">
            <PlayCircle size={16} /> {s.completed_count ? "Continue" : "Start"}: <span dir="auto">{s.next_lesson_title}</span>
          </span>
        )}
      </div>
    </Link>
  );
}
