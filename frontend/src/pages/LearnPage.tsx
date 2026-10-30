import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { GraduationCap, Plus } from "lucide-react";
import { api } from "../api";
import CourseCard from "../components/CourseCard";
import { useToast } from "../components/Toast";
import { EmptyState, PageHeader, Skeleton } from "../components/ui";
import type { CourseSummary } from "../types";

export default function LearnPage() {
  const [courses, setCourses] = useState<CourseSummary[] | null>(null);
  const toast = useToast();
  useEffect(() => {
    let t: ReturnType<typeof setTimeout>;
    const load = () =>
      api
        .courses()
        .then((c) => {
          setCourses(c);
          if (c.some((x) => x.status === "queued" || x.status === "processing")) t = setTimeout(load, 3000);
        })
        .catch((e) => toast((e as Error).message, "error"));
    load();
    return () => clearTimeout(t);
  }, [toast]);

  const active = courses?.filter((c) => c.stats.completed_count < c.stats.lesson_count || c.status !== "completed") ?? [];
  const done = courses?.filter((c) => c.status === "completed" && c.stats.lesson_count > 0 && c.stats.completed_count === c.stats.lesson_count) ?? [];
  return (
    <div>
      <PageHeader
        icon={<GraduationCap size={22} />}
        title="Learning Hub"
        subtitle="Step-by-step courses built from your documentation and videos: learn a small part, take a quiz, get corrected, move on."
        actions={<Link className="btn primary" to="/new?tab=docs"><Plus size={16} /> New course from docs</Link>}
      />
      {!courses && <Skeleton lines={4} />}
      {courses && courses.length === 0 && (
        <EmptyState
          icon={<GraduationCap size={28} />}
          title="Start your first course"
          text="Paste a documentation URL (for example a framework tutorial) — VoxNote reads it and teaches it to you lesson by lesson. You can also create a course from any processed video or playlist."
          action={<Link className="btn primary" to="/new?tab=docs">Learn from documentation</Link>}
        />
      )}
      {active.length > 0 && (
        <>
          <h2 className="section-title">In progress</h2>
          <div className="grid">{active.map((c) => <CourseCard key={c.id} c={c} />)}</div>
        </>
      )}
      {done.length > 0 && (
        <>
          <h2 className="section-title">Completed</h2>
          <div className="grid">{done.map((c) => <CourseCard key={c.id} c={c} />)}</div>
        </>
      )}
    </div>
  );
}
