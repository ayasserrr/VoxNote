export type Status = "pending" | "queued" | "processing" | "completed" | "partial" | "failed" | "cancelled";

export interface ProcessingSettings {
  output_language: "auto" | "en" | "ar" | "bilingual";
  detail_level: "standard" | "comprehensive";
  include_transcript: boolean;
  include_timestamps: boolean;
  per_video_documents: boolean;
  combined_document: boolean;
  max_videos?: number | null;
}

export interface DocumentInfo {
  id: string;
  kind: "video" | "collection";
  format: "pdf" | "md";
  title: string;
  size_bytes: number;
  pages: number | null;
  language: string | null;
  video_id: string | null;
  created_at: string;
}

export interface Video {
  id: string;
  position: number;
  youtube_id: string | null;
  url: string | null;
  title: string;
  channel: string | null;
  duration_seconds: number | null;
  published_at: string | null;
  thumbnail_url: string | null;
  language: string | null;
  status: Status;
  stage: string;
  progress: number;
  attempts: number;
  error: string | null;
  started_at: string | null;
  finished_at: string | null;
}

export interface CollectionSummary {
  id: string;
  kind: "video" | "playlist" | "upload";
  title: string;
  channel: string | null;
  thumbnail_url: string | null;
  source_url: string | null;
  status: Status;
  stage: string;
  created_at: string;
  updated_at: string;
  video_count: number;
  completed_count: number;
  failed_count: number;
  progress: number;
}

export interface Collection extends CollectionSummary {
  description: string | null;
  error: string | null;
  settings: ProcessingSettings;
  synthesis: CollectionSynthesis | null;
  videos: Video[];
  documents: DocumentInfo[];
}

export interface TimeRef {
  start?: number | null;
  end?: number | null;
}

export interface Concept extends TimeRef {
  name: string;
  definition: string;
  explanation: string;
  instructor_points: string[];
  ai_clarification: string;
  examples: string[];
  related: string[];
}

export interface TechnicalItem extends TimeRef {
  kind: string;
  title: string;
  content: string;
  language: string;
  explanation: string;
}

export interface Knowledge {
  title: string;
  output_language: string;
  overview: string;
  learning_objectives: string[];
  prerequisites: string[];
  chapters: ({ title: string; summary: string } & TimeRef)[];
  concepts: Concept[];
  technical: TechnicalItem[];
  examples: ({ title: string; description: string } & TimeRef)[];
  key_points: ({ text: string } & TimeRef)[];
  takeaways: string[];
  glossary: { term: string; definition: string; translation: string }[];
  questions: { question: string; answer: string; difficulty: string }[];
}

export interface CollectionSynthesis {
  course_title: string;
  course_summary: string;
  concepts: { name: string; description: string; videos: number[] }[];
  concept_map: { source: string; target: string; relation: string }[];
  recurring_concepts: string[];
  learning_path: { step: string; goal: string; videos: number[] }[];
  glossary: { term: string; definition: string; translation: string }[];
  final_questions: { question: string; answer: string; difficulty: string }[];
}

export interface VideoDetail extends Video {
  collection_id: string;
  description: string | null;
  knowledge: Knowledge | null;
  quality: Record<string, unknown> & { warnings?: string[] };
  llm_provider: string | null;
  llm_model: string | null;
  documents: DocumentInfo[];
}

export interface Segment {
  idx: number;
  start: number;
  end: number;
  text: string;
}

export interface Transcript {
  source: string;
  language: string | null;
  language_code: string | null;
  word_count: number;
  segments: Segment[];
}

export interface SourceRef {
  ref: number;
  video_id: string;
  video_title: string;
  youtube_id: string | null;
  start: number;
  end: number;
  text: string;
  url: string | null;
}

export interface AskResponse {
  answer: string;
  sources: SourceRef[];
  provider: string | null;
  model: string | null;
}

export interface SearchHit extends SourceRef {
  score: number;
  collection_id: string;
}

export interface LogEntry {
  id: number;
  video_id: string | null;
  level: string;
  stage: string | null;
  message: string;
  created_at: string;
}

export interface SystemStatus {
  app: string;
  version: string;
  task_backend: string;
  llm_providers: { name: string; model: string; configured: boolean; in_chain: boolean }[];
  stt_provider: string;
  stt_available: boolean;
  ffmpeg_available: boolean;
  storage_backend: string;
}

export interface UrlPreview {
  kind: "video" | "playlist";
  video_id: string | null;
  playlist_id: string | null;
  title: string | null;
  channel: string | null;
  thumbnail_url: string | null;
  video_count: number | null;
  duration_seconds: number | null;
}
