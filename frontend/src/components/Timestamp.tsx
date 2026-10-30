import { fmtTime, ytLink } from "../utils";

export default function Timestamp({ youtubeId, start, end }: { youtubeId?: string | null; start?: number | null; end?: number | null }) {
  if (start == null) return null;
  const label = fmtTime(start) + (end != null && end > start ? ` – ${fmtTime(end)}` : "");
  const href = ytLink(youtubeId, start);
  return href ? (
    <a className="ts" href={href} target="_blank" rel="noreferrer" title="Open this moment on YouTube">
      ▶ {label}
    </a>
  ) : (
    <span className="ts">⏱ {label}</span>
  );
}
