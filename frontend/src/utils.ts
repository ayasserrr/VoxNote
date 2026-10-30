export function fmtTime(seconds?: number | null): string {
  if (seconds == null || Number.isNaN(seconds)) return "--:--";
  const s = Math.max(0, Math.floor(seconds));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = s % 60;
  const pad = (n: number) => n.toString().padStart(2, "0");
  return h ? `${h}:${pad(m)}:${pad(sec)}` : `${pad(m)}:${pad(sec)}`;
}

export function fmtBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(0)} KB`;
  return `${(n / 1024 / 1024).toFixed(1)} MB`;
}

export function ytLink(youtubeId: string | null | undefined, start?: number | null): string | null {
  if (!youtubeId) return null;
  return `https://www.youtube.com/watch?v=${youtubeId}${start ? `&t=${Math.floor(start)}s` : ""}`;
}

export function timeAgo(iso: string): string {
  const diff = (Date.now() - new Date(iso).getTime()) / 1000;
  if (diff < 60) return "just now";
  if (diff < 3600) return `${Math.floor(diff / 60)} min ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)} h ago`;
  return new Date(iso).toLocaleDateString();
}

export const LANG_LABEL: Record<string, string> = {
  en: "English",
  ar: "Arabic",
  mixed: "Arabic + English",
  bilingual: "Bilingual",
};

export const STAGE_LABEL: Record<string, string> = {
  waiting: "Waiting",
  metadata: "Reading metadata",
  transcribing: "Transcribing",
  language: "Detecting language",
  extracting: "AI knowledge extraction",
  assembling: "Assembling knowledge",
  verifying: "Verifying against transcript",
  rendering: "Generating documents",
  synthesizing: "Cross-video synthesis",
  done: "Done",
};

export const PIPELINE = ["metadata", "transcribing", "language", "extracting", "assembling", "verifying", "rendering", "done"];

export const isActive = (status: string) => status === "queued" || status === "processing" || status === "pending";
