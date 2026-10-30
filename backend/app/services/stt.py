"""Speech-to-text.

Providers:
* `groq`  - Whisper large-v3 on Groq's free tier (OpenAI-compatible
            `/audio/transcriptions`, `verbose_json` gives segment timestamps).
* `local` - faster-whisper running on your machine (`pip install faster-whisper`).
* `none`  - disabled; only videos with captions can be processed.

Long audio is normalised with ffmpeg (mono, 16 kHz, 32 kbps) and split into
chunks so each request stays under the free-tier upload limit; timestamps of
every chunk are shifted back onto the original timeline.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

import httpx

from app.config import settings

log = logging.getLogger(__name__)

_MAX_UPLOAD_BYTES = 24 * 1024 * 1024


class STTError(Exception):
    pass


def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


def is_available() -> bool:
    provider = settings.stt_provider.lower()
    if provider == "groq":
        return bool(settings.groq_api_key)
    if provider == "local":
        try:
            import faster_whisper  # noqa: F401

            return True
        except ImportError:
            return False
    return False


def _run(cmd: list[str]) -> None:
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise STTError(f"ffmpeg failed: {proc.stderr[-500:]}")


def split_audio(path: Path, workdir: Path, chunk_seconds: int) -> list[tuple[Path, float]]:
    """Return [(chunk_path, offset_seconds)]; requires ffmpeg for long files."""
    if not ffmpeg_available():
        if path.stat().st_size > _MAX_UPLOAD_BYTES:
            raise STTError("ffmpeg is required to split audio larger than 24 MB")
        return [(path, 0.0)]
    pattern = workdir / "chunk_%04d.mp3"
    _run(
        [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(path),
            "-vn", "-ac", "1", "-ar", "16000", "-b:a", "32k",
            "-f", "segment", "-segment_time", str(chunk_seconds), "-reset_timestamps", "1",
            str(pattern),
        ]
    )
    chunks = sorted(workdir.glob("chunk_*.mp3"))
    if not chunks:
        raise STTError("ffmpeg produced no audio chunks")
    return [(c, i * float(chunk_seconds)) for i, c in enumerate(chunks)]


_STT_FALLBACK_MODELS = ("whisper-large-v3", "whisper-large-v3-turbo")


def _groq_transcribe_file(path: Path) -> dict[str, Any]:
    """Free Whisper on Groq; if the configured model is retired, try the other free Whisper models."""
    models = list(dict.fromkeys([settings.groq_stt_model, *_STT_FALLBACK_MODELS]))
    last: STTError | None = None
    for model in models:
        try:
            return _groq_transcribe_with(path, model)
        except STTError as exc:
            msg = str(exc).lower()
            if "404" in msg or "decommission" in msg or "does not exist" in msg or "model" in msg and "400" in msg:
                log.warning("Groq STT model %s unavailable, trying the next free model", model)
                last = exc
                continue
            raise
    raise last or STTError("no Groq speech-to-text model available")


def _groq_transcribe_with(path: Path, model: str) -> dict[str, Any]:
    url = f"{settings.groq_base_url.rstrip('/')}/audio/transcriptions"
    headers = {"Authorization": f"Bearer {settings.groq_api_key}"}
    for attempt in range(1, 6):
        with path.open("rb") as fh:
            files = {"file": (path.name, fh, "audio/mpeg")}
            data = {"model": model, "response_format": "verbose_json", "temperature": "0"}
            try:
                resp = httpx.post(url, headers=headers, files=files, data=data, timeout=600)
            except httpx.HTTPError as exc:
                if attempt == 5:
                    raise STTError(f"Groq STT request failed: {exc}") from exc
                time.sleep(2**attempt)
                continue
        if resp.status_code == 429 or resp.status_code >= 500:
            wait = float(resp.headers.get("retry-after", 2**attempt * 5))
            log.warning("Groq STT %s, retrying in %.0fs", resp.status_code, wait)
            time.sleep(min(wait, 120))
            continue
        if resp.status_code >= 400:
            raise STTError(f"Groq STT error {resp.status_code}: {resp.text[:300]}")
        return resp.json()
    raise STTError("Groq STT: too many retries")


_LANG_NAMES = {"english": "en", "arabic": "ar"}


def _transcribe_groq(path: Path) -> dict[str, Any]:
    segments: list[dict[str, Any]] = []
    language: str | None = None
    with tempfile.TemporaryDirectory(prefix="voxnote-stt-") as tmp:
        for chunk, offset in split_audio(path, Path(tmp), settings.audio_chunk_seconds):
            res = _groq_transcribe_file(chunk)
            lang = (res.get("language") or "").lower()
            language = language or _LANG_NAMES.get(lang, lang or None)
            for s in res.get("segments") or []:
                segments.append(
                    {
                        "start": float(s.get("start", 0)) + offset,
                        "end": float(s.get("end", 0)) + offset,
                        "text": s.get("text", ""),
                    }
                )
            if not res.get("segments") and res.get("text"):
                segments.append({"start": offset, "end": offset + settings.audio_chunk_seconds, "text": res["text"]})
    return {"language": language, "segments": segments}


_local_model = None


def _transcribe_local(path: Path) -> dict[str, Any]:
    global _local_model
    from faster_whisper import WhisperModel

    if _local_model is None:
        _local_model = WhisperModel(settings.local_whisper_model, device="auto", compute_type="int8")
    segs, info = _local_model.transcribe(str(path), vad_filter=True)
    return {
        "language": info.language,
        "segments": [{"start": s.start, "end": s.end, "text": s.text} for s in segs],
    }


def transcribe(path: Path) -> dict[str, Any]:
    provider = settings.stt_provider.lower()
    if provider == "groq":
        return _transcribe_groq(path)
    if provider == "local":
        return _transcribe_local(path)
    raise STTError("Speech-to-text is disabled (STT_PROVIDER=none)")
