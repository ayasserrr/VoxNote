"""Token-aware transcript chunking.

Transcripts are split on segment boundaries (never mid-sentence) into chunks
that fit a token budget, with a small overlap so concepts that straddle a
boundary are not lost. Token counts are estimated without a tokenizer
dependency: ~4 chars/token for Latin text and ~2.5 chars/token for Arabic,
which is conservative for Llama/Gemini tokenizers.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from app.services.language import script_ratio


class _Seg(Protocol):
    start: float
    end: float
    text: str


def estimate_tokens(text: str) -> int:
    if not text:
        return 0
    ar, la = script_ratio(text)
    other = max(len(text) - ar - la, 0)
    return int(ar / 2.5 + la / 4 + other / 4) + 1


def fmt_ts(seconds: float | None) -> str:
    if seconds is None:
        return "--:--"
    s = int(max(seconds, 0))
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    return f"{h:d}:{m:02d}:{sec:02d}" if h else f"{m:02d}:{sec:02d}"


@dataclass
class Chunk:
    index: int
    start: float
    end: float
    segments: list[_Seg]

    @property
    def text(self) -> str:
        return " ".join(s.text for s in self.segments)

    def as_prompt_text(self) -> str:
        """Transcript lines prefixed with [mm:ss] so the LLM can cite times."""
        return "\n".join(f"[{fmt_ts(s.start)}] {s.text}" for s in self.segments)

    @property
    def tokens(self) -> int:
        return estimate_tokens(self.as_prompt_text())


def chunk_segments(segments: Sequence[_Seg], max_tokens: int = 2500, overlap: int = 2) -> list[Chunk]:
    chunks: list[Chunk] = []
    current: list[_Seg] = []
    current_tokens = 0
    i = 0
    segs = list(segments)
    while i < len(segs):
        seg = segs[i]
        t = estimate_tokens(seg.text) + 4  # timestamp prefix
        if current and current_tokens + t > max_tokens:
            chunks.append(Chunk(len(chunks), current[0].start, current[-1].end, current))
            # Start the next chunk with the last `overlap` segments for context.
            current = current[-overlap:] if overlap and len(current) > overlap else []
            current_tokens = sum(estimate_tokens(s.text) + 4 for s in current)
        current.append(seg)
        current_tokens += t
        i += 1
    if current:
        # Avoid a final chunk that only contains overlap segments.
        if chunks and all(s in chunks[-1].segments for s in current):
            pass
        else:
            chunks.append(Chunk(len(chunks), current[0].start, current[-1].end, current))
    return chunks


def merge_short_segments(segments: Sequence[_Seg], min_chars: int = 120, max_gap: float = 2.5):
    """Group tiny caption lines into readable paragraphs for documents."""
    from app.services.transcripts import Segment

    out: list[Segment] = []
    buf: list[_Seg] = []

    def flush():
        if buf:
            out.append(Segment(buf[0].start, buf[-1].end, " ".join(s.text for s in buf)))
            buf.clear()

    for seg in segments:
        if buf and (seg.start - buf[-1].end > max_gap or sum(len(s.text) for s in buf) >= min_chars * 4):
            flush()
        buf.append(seg)
        if sum(len(s.text) for s in buf) >= min_chars and seg.text.rstrip().endswith((".", "?", "!", "؟")):
            flush()
    flush()
    return out
