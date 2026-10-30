"""Application configuration.

All settings are read from environment variables (or a `.env` file in the
project root / backend folder). See `.env.example` for documentation of every
option.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_DIR = BACKEND_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(str(PROJECT_DIR / ".env"), str(BACKEND_DIR / ".env")),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ------------------------------------------------------------------ app
    app_name: str = "VoxNote"
    environment: str = "development"
    log_level: str = "INFO"
    api_prefix: str = "/api"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000"

    # ------------------------------------------------------------- database
    # SQLite works out of the box; docker-compose switches to PostgreSQL.
    database_url: str = f"sqlite:///{(BACKEND_DIR / 'data' / 'voxnote.db').as_posix()}"
    db_auto_create: bool = True

    # ----------------------------------------------------------------- auth
    jwt_secret: str = "change-me-in-production-please-use-a-long-random-string"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24 * 7
    allow_registration: bool = True

    # -------------------------------------------------------------- storage
    storage_backend: str = "local"  # local | s3
    storage_dir: str = str(BACKEND_DIR / "data" / "storage")
    s3_bucket: str | None = None
    s3_endpoint_url: str | None = None
    s3_region: str | None = None
    s3_access_key: str | None = None
    s3_secret_key: str | None = None

    # ------------------------------------------------------- background jobs
    task_backend: str = "thread"  # thread | celery
    worker_concurrency: int = 2
    redis_url: str = "redis://localhost:6379/0"
    max_retries: int = 3
    retry_base_delay: float = 5.0

    # ------------------------------------------------------------------ LLM
    # Ordered, comma separated list of FREE providers. Providers without a key
    # are skipped; when one is rate limited / out of quota / down, the next one
    # is used. Supported: groq, gemini, cerebras, mistral, openrouter, ollama,
    # openai_compat, mock
    llm_providers: str = "groq,gemini,cerebras,mistral,openrouter,ollama"
    llm_temperature: float = 0.2
    llm_max_output_tokens: int = 8192  # reasoning models need room to "think"
    llm_timeout: float = 180.0
    llm_max_retries: int = 4
    llm_min_interval: float = 0.0  # seconds between LLM calls (free-tier friendly)
    llm_models_per_provider: int = 3  # rotate between N free models per provider (separate quotas)
    llm_reasoning_effort: str = "low"  # for reasoning models (gpt-oss, Gemini 3): low | medium | high | none

    # Model settings: "auto" = discover the currently available FREE models from
    # the provider's live /models list (survives model retirements), or give an
    # explicit comma-separated list, e.g. GROQ_MODEL=openai/gpt-oss-120b,qwen/qwen3-32b
    groq_api_key: str | None = None
    groq_base_url: str = "https://api.groq.com/openai/v1"
    groq_model: str = "auto"

    gemini_api_key: str | None = None
    gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta/openai"
    gemini_model: str = "auto"

    cerebras_api_key: str | None = None
    cerebras_base_url: str = "https://api.cerebras.ai/v1"
    cerebras_model: str = "auto"

    mistral_api_key: str | None = None
    mistral_base_url: str = "https://api.mistral.ai/v1"
    mistral_model: str = "auto"

    openrouter_api_key: str | None = None
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_model: str = "openrouter/free"

    ollama_base_url: str = "http://localhost:11434/v1"
    ollama_model: str = "auto"
    ollama_enabled: bool = False

    # Any other OpenAI-compatible endpoint (LM Studio, vLLM, llama.cpp, ...)
    openai_compat_api_key: str | None = None
    openai_compat_base_url: str | None = None
    openai_compat_model: str | None = None

    # ------------------------------------------------------- speech-to-text
    stt_provider: str = "groq"  # groq | local | none
    groq_stt_model: str = "whisper-large-v3"  # falls back to whisper-large-v3-turbo automatically
    local_whisper_model: str = "small"
    allow_audio_download: bool = True
    audio_chunk_seconds: int = 600

    # ------------------------------------------------------------- youtube
    youtube_proxy_url: str | None = None
    youtube_cookies_file: str | None = None
    max_playlist_videos: int = 200
    preferred_caption_languages: str = "en,ar,en-US,en-GB,ar-EG,ar-SA"

    # ------------------------------------------------------------ pipeline
    chunk_max_tokens: int = 2500
    chunk_overlap_segments: int = 2
    max_upload_mb: int = 500

    # ------------------------------------------------------- learning hub
    quiz_pass_score: float = 0.7  # share of quiz points needed to complete a lesson
    crawl_delay: float = 0.3  # seconds between documentation page requests
    crawl_max_pages: int = 300
    prefetch_next_lesson: bool = True

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def provider_list(self) -> list[str]:
        return [p.strip().lower() for p in self.llm_providers.split(",") if p.strip()]

    @property
    def caption_languages(self) -> list[str]:
        return [x.strip() for x in self.preferred_caption_languages.split(",") if x.strip()]

    @property
    def storage_path(self) -> Path:
        p = Path(self.storage_dir)
        p.mkdir(parents=True, exist_ok=True)
        return p


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
