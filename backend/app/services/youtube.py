"""YouTube URL parsing and metadata extraction.

Metadata is retrieved with `yt-dlp` (free, no API key). Playlists are read
with `extract_flat` so listing a 200-video playlist is a single fast request.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from urllib.parse import parse_qs, urlparse

from app.config import settings

log = logging.getLogger(__name__)

_VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")
_PLAYLIST_ID_RE = re.compile(r"^[A-Za-z0-9_-]{10,64}$")


class YouTubeError(Exception):
    pass


@dataclass
class ParsedUrl:
    kind: str  # video | playlist
    video_id: str | None = None
    playlist_id: str | None = None


@dataclass
class VideoMeta:
    video_id: str
    title: str = "Untitled video"
    channel: str | None = None
    duration_seconds: float | None = None
    published_at: str | None = None
    thumbnail_url: str | None = None
    description: str | None = None
    url: str = ""
    chapters: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class PlaylistMeta:
    playlist_id: str
    title: str = "Untitled playlist"
    channel: str | None = None
    description: str | None = None
    thumbnail_url: str | None = None
    videos: list[VideoMeta] = field(default_factory=list)


def parse_youtube_url(url: str) -> ParsedUrl:
    """Classify a YouTube URL (or a bare id) as a video or a playlist.

    A watch URL that also carries `list=` is treated as a playlist, because
    that is what users usually mean when they copy it from a playlist page.
    """
    url = (url or "").strip()
    if not url:
        raise YouTubeError("Empty URL")
    if _VIDEO_ID_RE.match(url):
        return ParsedUrl(kind="video", video_id=url)
    if url.startswith(("PL", "UU", "OL", "FL", "RD")) and _PLAYLIST_ID_RE.match(url):
        return ParsedUrl(kind="playlist", playlist_id=url)
    if not re.match(r"^https?://", url):
        url = "https://" + url

    parsed = urlparse(url)
    host = (parsed.hostname or "").lower().removeprefix("www.").removeprefix("m.")
    qs = parse_qs(parsed.query)
    playlist_id = (qs.get("list") or [None])[0]
    video_id: str | None = None

    if host == "youtu.be":
        video_id = parsed.path.lstrip("/").split("/")[0] or None
    elif host in {"youtube.com", "music.youtube.com", "youtube-nocookie.com"}:
        path = parsed.path
        if path == "/watch":
            video_id = (qs.get("v") or [None])[0]
        elif path.startswith(("/shorts/", "/embed/", "/live/", "/v/")):
            video_id = path.split("/")[2] if len(path.split("/")) > 2 else None
        elif path == "/playlist":
            pass
        else:
            raise YouTubeError("Unsupported YouTube URL (use a video or playlist link)")
    else:
        raise YouTubeError("Not a YouTube URL")

    if playlist_id and _PLAYLIST_ID_RE.match(playlist_id) and not playlist_id.startswith("RD"):
        return ParsedUrl(kind="playlist", playlist_id=playlist_id, video_id=video_id)
    if video_id and _VIDEO_ID_RE.match(video_id):
        return ParsedUrl(kind="video", video_id=video_id)
    raise YouTubeError("Could not find a video or playlist id in the URL")


def video_url(video_id: str, start: float | None = None) -> str:
    base = f"https://www.youtube.com/watch?v={video_id}"
    if start is not None and start > 0:
        base += f"&t={int(start)}s"
    return base


def ydl_base_opts() -> dict[str, Any]:
    opts: dict[str, Any] = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "noplaylist": True,
        "socket_timeout": 30,
        "extractor_retries": 3,
    }
    if settings.youtube_proxy_url:
        opts["proxy"] = settings.youtube_proxy_url
    if settings.youtube_cookies_file:
        opts["cookiefile"] = settings.youtube_cookies_file
    return opts


def _fmt_date(raw: str | None) -> str | None:
    if not raw:
        return None
    try:
        return datetime.strptime(raw, "%Y%m%d").date().isoformat()
    except ValueError:
        return raw


def _best_thumb(info: dict[str, Any]) -> str | None:
    if info.get("thumbnail"):
        return info["thumbnail"]
    thumbs = info.get("thumbnails") or []
    if thumbs:
        return thumbs[-1].get("url")
    vid = info.get("id")
    return f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg" if vid else None


def _video_from_info(info: dict[str, Any]) -> VideoMeta:
    vid = info.get("id") or ""
    return VideoMeta(
        video_id=vid,
        title=info.get("title") or "Untitled video",
        channel=info.get("channel") or info.get("uploader"),
        duration_seconds=float(info["duration"]) if info.get("duration") else None,
        published_at=_fmt_date(info.get("upload_date")),
        thumbnail_url=_best_thumb(info),
        description=info.get("description"),
        url=video_url(vid) if vid else (info.get("webpage_url") or ""),
        chapters=info.get("chapters") or [],
    )


def fetch_video_metadata(video_id: str) -> VideoMeta:
    import yt_dlp

    try:
        with yt_dlp.YoutubeDL(ydl_base_opts()) as ydl:
            info = ydl.extract_info(video_url(video_id), download=False)
    except Exception as exc:  # yt_dlp raises many different error types
        raise YouTubeError(f"Could not read video metadata: {exc}") from exc
    return _video_from_info(info or {"id": video_id})


def fetch_playlist_metadata(playlist_id: str, limit: int | None = None) -> PlaylistMeta:
    import yt_dlp

    opts = ydl_base_opts() | {"extract_flat": "in_playlist", "noplaylist": False}
    limit = limit or settings.max_playlist_videos
    opts["playlistend"] = limit
    url = f"https://www.youtube.com/playlist?list={playlist_id}"
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as exc:
        raise YouTubeError(f"Could not read playlist: {exc}") from exc
    info = info or {}
    videos: list[VideoMeta] = []
    for entry in info.get("entries") or []:
        if not entry or not entry.get("id"):
            continue
        title = entry.get("title") or "Untitled video"
        if title in {"[Private video]", "[Deleted video]"}:
            continue
        meta = _video_from_info(entry)
        videos.append(meta)
        if len(videos) >= limit:
            break
    if not videos:
        raise YouTubeError("The playlist is empty, private, or unavailable")
    return PlaylistMeta(
        playlist_id=playlist_id,
        title=info.get("title") or "Untitled playlist",
        channel=info.get("channel") or info.get("uploader"),
        description=info.get("description"),
        thumbnail_url=_best_thumb(info) or videos[0].thumbnail_url,
        videos=videos,
    )
