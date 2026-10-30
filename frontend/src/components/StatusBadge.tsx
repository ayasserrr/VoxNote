import { STAGE_LABEL } from "../utils";

export function StatusBadge({ status, stage }: { status: string; stage?: string }) {
  const label =
    status === "processing" && stage ? STAGE_LABEL[stage] ?? stage : status === "partial" ? "Partially done" : status;
  return (
    <span className={`badge badge-${status}`}>
      {status === "processing" && <i className="dot" />}
      {label}
    </span>
  );
}

export function ProgressBar({ value, status }: { value: number; status?: string }) {
  const pct = Math.round(Math.min(Math.max(value, 0), 1) * 100);
  return (
    <div className={`progress ${status === "failed" ? "progress-failed" : ""}`} title={`${pct}%`}>
      <div style={{ width: `${pct}%` }} />
    </div>
  );
}
