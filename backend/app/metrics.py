"""Prometheus metrics (exposed at GET /metrics)."""

from prometheus_client import Counter, Histogram

VIDEOS_PROCESSED = Counter("voxnote_videos_processed_total", "Videos processed", ["status"])
STAGE_SECONDS = Histogram(
    "voxnote_stage_seconds",
    "Time spent per pipeline stage",
    ["stage"],
    buckets=(0.5, 1, 2, 5, 10, 30, 60, 120, 300, 600, 1800),
)
LLM_REQUESTS = Counter("voxnote_llm_requests_total", "LLM requests", ["provider", "outcome"])
LLM_TOKENS = Counter("voxnote_llm_tokens_total", "LLM tokens", ["provider", "kind"])
TRANSCRIPT_SOURCE = Counter("voxnote_transcript_source_total", "Transcript sources used", ["source"])
DOCUMENTS_GENERATED = Counter("voxnote_documents_generated_total", "Documents generated", ["kind", "format"])
