"""Transcript acquisition.

Strategy (first one that works wins):

1. Captions via `youtube-transcript-api` (manual captions preferred over
   auto-generated ones, preferred languages first).
2. Subtitles via `yt-dlp` (different code path, useful when (1) is blocked).
3. Audio download via `yt-dlp` + speech-to-text (Groq Whisper, free tier, or
   local faster-whisper). Can be disabled with ALLOW_AUDIO_DOWNLOAD=false.

Uploaded audio/video files skip straight to step 3.

Only process content you are allowed to process; see README "Responsible use".
"""

from __future__ import annotations

import html
import json
import logging
import re
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

import httpx

from app.config import settings
from app.services import stt
from app.services.youtube import video_url, ydl_base_opts

log = logging.getLogger(__name__)


class TranscriptUnavailable(Exception):
    pass


@dataclass
class Segment:
    start: float
    end: float
    text: str


@dataclass
class TranscriptResult:
    source: str  # captions | auto_captions | ytdlp_subtitles | whisper | upload
    language_code: str | None
    segments: list[Segment] = field(default_factory=list)

    @property
    def text(self) -> str:
        return " ".join(s.text for s in self.segments)


_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def clean_text(text: str) -> str:
    text = html.unescape(_TAG_RE.sub("", text or ""))
    text = text.replace("​", "")
    return _WS_RE.sub(" ", text).strip()


def normalize_segments(raw: list[Segment]) -> list[Segment]:
    """Drop empty/duplicate lines and make sure end >= start."""
    out: list[Segment] = []
    prev = ""
    for seg in sorted(raw, key=lambda s: s.start):
        text = clean_text(seg.text)
        if not text or text in {"[Music]", "[موسيقى]", "[Applause]"}:
            continue
        if text == prev:
            continue
        end = seg.end if seg.end and seg.end > seg.start else seg.start + 2.0
        out.append(Segment(round(seg.start, 2), round(end, 2), text))
        prev = text
    return out


# ------------------------------------------------------------ captions API
def _proxy_config():
    if not settings.youtube_proxy_url:
        return None
    from youtube_transcript_api.proxies import GenericProxyConfig

    return GenericProxyConfig(http_url=settings.youtube_proxy_url, https_url=settings.youtube_proxy_url)


def fetch_captions(video_id: str) -> TranscriptResult:
    from youtube_transcript_api import YouTubeTranscriptApi

    api = YouTubeTranscriptApi(proxy_config=_proxy_config())
    try:
        listing = api.list(video_id)
    except Exception as exc:
        raise TranscriptUnavailable(f"captions list failed: {exc.__class__.__name__}") from exc

    langs = settings.caption_languages
    transcript = None
    source = "captions"
    for finder, src in (
        (listing.find_manually_created_transcript, "captions"),
        (listing.find_generated_transcript, "auto_captions"),
    ):
        try:
            transcript = finder(langs)
            source = src
            break
        except Exception:
            continue
    if transcript is None:
        # Any language at all (the LLM can still write the doc in en/ar).
        available = list(listing)
        if not available:
            raise TranscriptUnavailable("no captions available")
        transcript = available[0]
        source = "auto_captions" if transcript.is_generated else "captions"

    try:
        fetched = transcript.fetch()
    except Exception as exc:
        raise TranscriptUnavailable(f"captions fetch failed: {exc.__class__.__name__}") from exc

    segments: list[Segment] = []
    for snip in fetched:
        start = float(getattr(snip, "start", 0.0))
        dur = float(getattr(snip, "duration", 0.0) or 0.0)
        segments.append(Segment(start, start + dur, getattr(snip, "text", "")))
    segments = normalize_segments(segments)
    if not segments:
        raise TranscriptUnavailable("captions are empty")
    return TranscriptResult(source=source, language_code=transcript.language_code, segments=segments)


# ------------------------------------------------------- yt-dlp subtitles
def _parse_json3(data: dict) -> list[Segment]:
    segs: list[Segment] = []
    for ev in data.get("events", []):
        if "segs" not in ev:
            continue
        text = "".join(s.get("utf8", "") for s in ev["segs"]).strip()
        if not text:
            continue
        start = ev.get("tStartMs", 0) / 1000
        dur = ev.get("dDurationMs", 2000) / 1000
        segs.append(Segment(start, start + dur, text))
    return segs


def fetch_subtitles_ytdlp(video_id: str) -> TranscriptResult:
    import yt_dlp

    opts = ydl_base_opts()
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(video_url(video_id), download=False)
    except Exception as exc:
        raise TranscriptUnavailable(f"yt-dlp failed: {exc}") from exc

    for kind, source in (("subtitles", "captions"), ("automatic_captions", "auto_captions")):
        tracks: dict = (info or {}).get(kind) or {}
        if not tracks:
            continue
        lang = next((lang for lang in settings.caption_languages if lang in tracks), None)
        if lang is None:
            # automatic_captions lists every translation; prefer the original.
            orig = [k for k in tracks if k.endswith("-orig")]
            lang = orig[0] if orig else next(iter(tracks))
        fmt = next((f for f in tracks[lang] if f.get("ext") == "json3"), None)
        if not fmt:
            continue
        try:
            resp = httpx.get(fmt["url"], timeout=30, proxy=settings.youtube_proxy_url)
            resp.raise_for_status()
            segments = normalize_segments(_parse_json3(resp.json()))
        except (httpx.HTTPError, json.JSONDecodeError) as exc:
            log.warning("subtitle download failed: %s", exc)
            continue
        if segments:
            return TranscriptResult(source=source, language_code=lang.replace("-orig", ""), segments=segments)
    raise TranscriptUnavailable("no subtitles via yt-dlp")


# ------------------------------------------------------- audio + whisper
def download_audio(video_id: str, workdir: Path) -> Path:
    import yt_dlp

    opts = ydl_base_opts() | {
        "skip_download": False,
        "format": "bestaudio[abr<=96]/bestaudio/worstaudio/worst",
        "outtmpl": str(workdir / "%(id)s.%(ext)s"),
    }
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(video_url(video_id), download=True)
            path = Path(ydl.prepare_filename(info))
    except Exception as exc:
        raise TranscriptUnavailable(f"audio download failed: {exc}") from exc
    if not path.exists():
        matches = list(workdir.glob(f"{video_id}.*"))
        if not matches:
            raise TranscriptUnavailable("audio file missing after download")
        path = matches[0]
    return path


def transcribe_media(path: Path, source: str = "whisper") -> TranscriptResult:
    if not stt.is_available():
        raise TranscriptUnavailable(
            "speech-to-text is not configured (set GROQ_API_KEY or STT_PROVIDER=local)"
        )
    result = stt.transcribe(path)
    segments = normalize_segments([Segment(s["start"], s["end"], s["text"]) for s in result["segments"]])
    if not segments:
        raise TranscriptUnavailable("speech-to-text returned no speech")
    return TranscriptResult(source=source, language_code=result.get("language"), segments=segments)


def get_youtube_transcript(video_id: str) -> TranscriptResult:
    errors: list[str] = []
    for fn in (fetch_captions, fetch_subtitles_ytdlp):
        try:
            return fn(video_id)
        except TranscriptUnavailable as exc:
            errors.append(str(exc))
            log.info("transcript strategy %s failed for %s: %s", fn.__name__, video_id, exc)

    if settings.allow_audio_download and stt.is_available():
        with tempfile.TemporaryDirectory(prefix="voxnote-") as tmp:
            try:
                audio = download_audio(video_id, Path(tmp))
                return transcribe_media(audio)
            except TranscriptUnavailable as exc:
                errors.append(str(exc))
    elif not stt.is_available():
        errors.append("audio fallback skipped: no speech-to-text provider configured")
    raise TranscriptUnavailable("; ".join(errors))
