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
  kind: "video" | "playlist" | "upload" | "docs";
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
  page_count: number;
  progress: number;
  course_id: string | null;
}

export interface Collection extends CollectionSummary {
  description: string | null;
  error: string | null;
  settings: ProcessingSettings;
  synthesis: CollectionSynthesis | null;
  meta: { pages?: number; words?: number; visited?: number; skipped?: number; warnings?: string[]; pages_found?: number; current_url?: string };
  videos: Video[];
  documents: DocumentInfo[];
  pages: PageInfo[];
}

export interface PageInfo {
  id: string;
  position: number;
  url: string;
  title: string;
  headings: string[];
  word_count: number;
  language: string | null;
}

export interface PageDetail extends PageInfo {
  content: string;
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
  kind: "video" | "page";
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

/* ------------------------------------------------------------ learning hub */
export type Level = "beginner" | "intermediate" | "advanced";
export type LangChoice = "auto" | "en" | "ar" | "bilingual";

export interface CourseStats {
  lesson_count: number;
  completed_count: number;
  progress: number;
  average_score: number | null;
  xp: number;
  next_lesson_id: string | null;
  next_lesson_title: string | null;
  minutes_total: number;
  exam_lesson_id: string | null;
  exam_status: LessonStatus | null;
  exam_score: number | null;
  certified: boolean;
  certified_at: string | null;
}

export interface CourseSummary {
  id: string;
  collection_id: string;
  collection_kind: string;
  source_url: string | null;
  thumbnail_url: string | null;
  title: string;
  description: string;
  level: Level;
  language: string;
  status: Status;
  error: string | null;
  created_at: string;
  updated_at: string;
  last_opened_at: string | null;
  stats: CourseStats;
}

export type LessonStatus = "locked" | "available" | "completed";

export interface LessonSummary {
  id: string;
  position: number;
  module_index: number;
  module_title: string;
  kind: "lesson" | "exam";
  title: string;
  objectives: string[];
  estimated_minutes: number;
  status: LessonStatus;
  best_score: number | null;
  attempts: number;
  has_content: boolean;
}

export interface Course extends CourseSummary {
  outcomes: string[];
  lessons: LessonSummary[];
}

export interface QuizQuestion {
  id: string;
  type: "mcq" | "true_false" | "short";
  question: string;
  options: string[];
  difficulty: string;
}

export interface QuizResult {
  id: string;
  type: string;
  question: string;
  your_answer: string | number | boolean | null;
  correct_answer: string;
  explanation: string;
  feedback: string;
  score: number;
  correct: boolean;
}

export interface Attempt {
  id: string;
  score: number;
  passed: boolean;
  results: QuizResult[];
  created_at: string;
}

export interface LessonContent {
  title: string;
  summary: string;
  explanation: string;
  analogy: string;
  key_points: string[];
  example: { title: string; content: string } | null;
  common_mistakes: string[];
}

export interface LessonSource {
  kind: "page" | "video";
  title: string;
  url: string | null;
  page_id: string | null;
  video_id: string | null;
  youtube_id: string | null;
  start: number | null;
  end: number | null;
}

export interface Lesson extends LessonSummary {
  course_id: string;
  course_title: string;
  language: string;
  content: LessonContent | null;
  quiz: QuizQuestion[];
  sources: LessonSource[];
  generating: boolean;
  simplicity: number;
  prev_lesson_id: string | null;
  next_lesson_id: string | null;
  last_attempt: Attempt | null;
  pass_score: number;
  notes: string | null;
}

export interface SubmitResult {
  attempt: Attempt;
  lesson: LessonSummary;
  next_lesson_id: string | null;
  course_completed: boolean;
}

export interface Dashboard {
  collections: number;
  videos_processed: number;
  pages_read: number;
  documents: number;
  courses: number;
  lessons_completed: number;
  quizzes_taken: number;
  average_score: number | null;
  xp: number;
  streak_days: number;
  due_reviews: number;
  certificates: number;
  continue_learning: CourseSummary[];
  recent: CollectionSummary[];
}

export interface ReviewCard {
  id: string;
  box: number;
  reviews: number;
  course_id: string;
  course_title: string;
  lesson_id: string;
  lesson_title: string;
  question: QuizQuestion;
}

export interface ReviewQueue {
  cards: ReviewCard[];
  due: number;
  upcoming: number;
  mastered: number;
  total: number;
}

export interface ReviewAnswer {
  result: QuizResult;
  box: number;
  mastered: boolean;
  next_due_at: string;
}
