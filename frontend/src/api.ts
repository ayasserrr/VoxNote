import type {
  AskResponse,
  Collection,
  CollectionSummary,
  Course,
  CourseSummary,
  Dashboard,
  LangChoice,
  Lesson,
  Level,
  LogEntry,
  PageDetail,
  SubmitResult,
  ProcessingSettings,
  SearchHit,
  SystemStatus,
  Transcript,
  UrlPreview,
  VideoDetail,
} from "./types";

const BASE = (import.meta.env.VITE_API_URL as string | undefined) ?? "/api";
const TOKEN_KEY = "voxnote_token";

export const tokenStore = {
  get: () => localStorage.getItem(TOKEN_KEY),
  set: (t: string) => localStorage.setItem(TOKEN_KEY, t),
  clear: () => localStorage.removeItem(TOKEN_KEY),
};

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  const token = tokenStore.get();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (init.body && !(init.body instanceof FormData)) headers.set("Content-Type", "application/json");
  const res = await fetch(`${BASE}${path}`, { ...init, headers });
  if (res.status === 401 && token) {
    tokenStore.clear();
    window.dispatchEvent(new Event("voxnote:logout"));
  }
  if (!res.ok) {
    let msg = res.statusText;
    try {
      const body = await res.json();
      msg = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail ?? body);
    } catch {
      /* not json */
    }
    throw new ApiError(res.status, msg);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export const api = {
  register: (email: string, password: string, full_name?: string) =>
    request<{ access_token: string }>("/auth/register", {
      method: "POST",
      body: JSON.stringify({ email, password, full_name }),
    }),
  login: (email: string, password: string) =>
    request<{ access_token: string }>("/auth/login", { method: "POST", body: JSON.stringify({ email, password }) }),
  me: () => request<{ id: string; email: string; full_name: string | null }>("/auth/me"),

  preview: (url: string) => request<UrlPreview>("/collections/preview", { method: "POST", body: JSON.stringify({ url }) }),
  createCollection: (url: string, settings: ProcessingSettings) =>
    request<Collection>("/collections", { method: "POST", body: JSON.stringify({ url, settings }) }),
  upload: (file: File, settings: ProcessingSettings, title?: string) => {
    const fd = new FormData();
    fd.append("file", file);
    fd.append("settings", JSON.stringify(settings));
    if (title) fd.append("title", title);
    return request<Collection>("/collections/upload", { method: "POST", body: fd });
  },
  collections: () => request<CollectionSummary[]>("/collections"),
  collection: (id: string) => request<Collection>(`/collections/${id}`),
  deleteCollection: (id: string) => request<void>(`/collections/${id}`, { method: "DELETE" }),
  retryFailed: (id: string) => request<Collection>(`/collections/${id}/retry`, { method: "POST" }),
  regenerate: (id: string, settings: ProcessingSettings) =>
    request<Collection>(`/collections/${id}/regenerate`, { method: "POST", body: JSON.stringify(settings) }),
  logs: (id: string) => request<LogEntry[]>(`/collections/${id}/logs`),

  video: (id: string) => request<VideoDetail>(`/videos/${id}`),
  transcript: (id: string) => request<Transcript>(`/videos/${id}/transcript`),
  retryVideo: (id: string) => request<VideoDetail>(`/videos/${id}/retry`, { method: "POST" }),

  ask: (question: string, scope: { collection_id?: string; video_id?: string } = {}) =>
    request<AskResponse>("/ask", { method: "POST", body: JSON.stringify({ question, ...scope }) }),
  search: (q: string, collection_id?: string) =>
    request<SearchHit[]>(`/search?q=${encodeURIComponent(q)}${collection_id ? `&collection_id=${collection_id}` : ""}`),

  status: () => request<SystemStatus>("/system/status"),
  dashboard: () => request<Dashboard>("/dashboard"),

  // documentation & learning hub
  createDocs: (body: { url: string; max_pages: number; same_path_only: boolean; level: Level; language: LangChoice }) =>
    request<Collection>("/collections/docs", { method: "POST", body: JSON.stringify(body) }),
  recrawl: (id: string) => request<Collection>(`/collections/${id}/recrawl`, { method: "POST" }),
  page: (collectionId: string, pageId: string) => request<PageDetail>(`/collections/${collectionId}/pages/${pageId}`),
  createCourse: (collectionId: string, level: Level, language: LangChoice) =>
    request<Course>(`/collections/${collectionId}/course`, { method: "POST", body: JSON.stringify({ level, language }) }),
  courses: () => request<CourseSummary[]>("/courses"),
  course: (id: string) => request<Course>(`/courses/${id}`),
  deleteCourse: (id: string) => request<void>(`/courses/${id}`, { method: "DELETE" }),
  resetCourse: (id: string) => request<Course>(`/courses/${id}/reset`, { method: "POST" }),
  lesson: (id: string) => request<Lesson>(`/lessons/${id}`),
  prepareLesson: (id: string) => request<Lesson>(`/lessons/${id}/prepare`, { method: "POST" }),
  simplifyLesson: (id: string) => request<Lesson>(`/lessons/${id}/simplify`, { method: "POST" }),
  regenerateLesson: (id: string) => request<Lesson>(`/lessons/${id}/regenerate`, { method: "POST" }),
  newQuiz: (id: string) => request<Lesson>(`/lessons/${id}/new-quiz`, { method: "POST" }),
  submitQuiz: (id: string, answers: Record<string, unknown>) =>
    request<SubmitResult>(`/lessons/${id}/submit`, { method: "POST", body: JSON.stringify({ answers }) }),
  tutor: (id: string, question: string) =>
    request<{ answer: string; provider: string | null; model: string | null }>(`/lessons/${id}/tutor`, {
      method: "POST",
      body: JSON.stringify({ question }),
    }),
};

export function isYouTubeUrl(url: string): boolean {
  return /(^|\/\/)(www\.|m\.|music\.)?(youtube\.com|youtu\.be|youtube-nocookie\.com)\//i.test(url.trim()) || /^[\w-]{11}$/.test(url.trim());
}

/** Direct link for downloads/viewing (token passed as query param). */
export function documentUrl(documentId: string, inline = false): string {
  const t = tokenStore.get() ?? "";
  return `${BASE}/documents/${documentId}/download?token=${encodeURIComponent(t)}${inline ? "&inline=true" : ""}`;
}
