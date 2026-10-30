"""AI knowledge engine: hierarchical extraction, assembly and verification.

    transcript ──chunk──▶ [chunk 1] [chunk 2] ... [chunk N]      (token-aware)
                              │         │             │
                         LLM extract (structured, validated, per chunk)
                              └─────────┴──────┬──────┘
                                    deterministic merge
                              (dedupe concepts, keep timestamps)
                                               │
                                 LLM video synthesis (overview,
                                 objectives, takeaways)
                                               │
                                 verification against transcript
"""

from __future__ import annotations

import logging
import re
import unicodedata
from collections.abc import Callable, Sequence
from typing import Any

from app.schemas.knowledge import (
    Chapter,
    ChunkKnowledge,
    CollectionSynthesis,
    Concept,
    GlossaryTerm,
    VideoKnowledge,
    VideoSynthesis,
)
from app.services.chunking import Chunk, chunk_segments, fmt_ts
from app.services.llm import LLMClient
from app.services.prompts import CHUNK_USER, chunk_system, collection_system, video_system

log = logging.getLogger(__name__)

ProgressFn = Callable[[float, str], None]


def _norm(name: str) -> str:
    """Normalisation key for deduplicating concepts across chunks."""
    s = unicodedata.normalize("NFKC", name or "").lower().strip()
    s = re.sub(r"^(the|a|an|ال)\s*", "", s)
    s = re.sub(r"[ً-ْ]", "", s)  # Arabic diacritics
    s = re.sub(r"[^\w\s]", "", s)
    s = re.sub(r"\s+", " ", s)
    return s.rstrip("s") if len(s) > 4 else s


def _merge_text(a: str, b: str) -> str:
    if not b or b.strip() in (a or ""):
        return a
    if not a:
        return b
    return f"{a}\n\n{b}"


def _merge_list(a: list[str], b: list[str]) -> list[str]:
    seen = {x.strip().lower() for x in a}
    out = list(a)
    for x in b:
        if x and x.strip().lower() not in seen:
            out.append(x)
            seen.add(x.strip().lower())
    return out


def merge_concepts(items: Sequence[Concept]) -> list[Concept]:
    merged: dict[str, Concept] = {}
    for c in items:
        if not c.name.strip():
            continue
        key = _norm(c.name)
        if key not in merged:
            merged[key] = c.model_copy(deep=True)
            continue
        m = merged[key]
        m.definition = m.definition or c.definition
        m.explanation = _merge_text(m.explanation, c.explanation)
        m.ai_clarification = _merge_text(m.ai_clarification, c.ai_clarification)
        m.instructor_points = _merge_list(m.instructor_points, c.instructor_points)
        m.examples = _merge_list(m.examples, c.examples)
        m.related = _merge_list(m.related, c.related)
        if c.start is not None and (m.start is None or c.start < m.start):
            m.start = c.start
        if c.end is not None and (m.end is None or c.end > m.end):
            m.end = c.end
    return list(merged.values())


def merge_glossary(items: Sequence[GlossaryTerm]) -> list[GlossaryTerm]:
    out: dict[str, GlossaryTerm] = {}
    for g in items:
        key = _norm(g.term)
        if not key:
            continue
        if key not in out:
            out[key] = g.model_copy()
        else:
            out[key].definition = out[key].definition or g.definition
            out[key].translation = out[key].translation or g.translation
    return sorted(out.values(), key=lambda g: g.term.lower())


def _dedupe_by(items: list[Any], key: Callable[[Any], str]) -> list[Any]:
    seen: set[str] = set()
    out = []
    for it in items:
        k = key(it)
        if k and k not in seen:
            seen.add(k)
            out.append(it)
    return out


def _clamp_times(obj: Any, lo: float, hi: float) -> None:
    """Keep model-provided timestamps inside the chunk they came from."""
    for attr in ("start", "end"):
        v = getattr(obj, attr, None)
        if v is None:
            continue
        if v < lo - 5 or v > hi + 5:
            setattr(obj, attr, lo if attr == "start" else hi)


def extract_chunk(llm: LLMClient, chunk: Chunk, total: int, title: str, channel: str | None,
                  output_language: str, detail_level: str) -> ChunkKnowledge:
    user = CHUNK_USER.format(
        title=title,
        channel=f' by {channel}' if channel else "",
        part=chunk.index + 1,
        total=total,
        start=fmt_ts(chunk.start),
        end=fmt_ts(chunk.end),
        transcript=chunk.as_prompt_text(),
    )
    ck = llm.structured(chunk_system(output_language, detail_level), user, ChunkKnowledge)
    for group in (ck.concepts, ck.technical, ck.examples, ck.key_points):
        for item in group:
            _clamp_times(item, chunk.start, chunk.end)
            if item.start is None:
                item.start = chunk.start
    return ck


def assemble(chunks: Sequence[Chunk], parts: Sequence[ChunkKnowledge]) -> VideoKnowledge:
    vk = VideoKnowledge()
    all_concepts: list[Concept] = []
    glossary: list[GlossaryTerm] = []
    for chunk, ck in zip(chunks, parts, strict=False):
        vk.chapters.append(
            Chapter(title=ck.section_title or f"Part {chunk.index + 1}", summary=ck.summary,
                    start=chunk.start, end=chunk.end)
        )
        all_concepts.extend(ck.concepts)
        vk.technical.extend(ck.technical)
        vk.examples.extend(ck.examples)
        vk.key_points.extend(ck.key_points)
        glossary.extend(ck.glossary)
        vk.questions.extend(ck.questions)
    vk.concepts = merge_concepts(all_concepts)
    vk.glossary = merge_glossary(glossary)
    vk.technical = _dedupe_by(vk.technical, lambda t: (t.content or t.title).strip().lower()[:200])
    vk.examples = _dedupe_by(vk.examples, lambda e: (e.description or e.title).strip().lower()[:200])
    vk.key_points = _dedupe_by(vk.key_points, lambda k: k.text.strip().lower())
    vk.questions = _dedupe_by(vk.questions, lambda q: q.question.strip().lower())
    return vk


def synthesize_video(llm: LLMClient, vk: VideoKnowledge, title: str, output_language: str) -> VideoSynthesis:
    lines = [f'Video title: "{title}"', ""]
    for ch in vk.chapters:
        lines.append(f"## [{fmt_ts(ch.start)}] {ch.title}\n{ch.summary}")
    lines.append("\nKey concepts: " + ", ".join(c.name for c in vk.concepts[:60]))
    lines.append("Key points:\n" + "\n".join(f"- {k.text}" for k in vk.key_points[:40]))
    user = "\n".join(lines)[:24000]
    return llm.structured(video_system(output_language), user, VideoSynthesis, max_tokens=2048)


def verify(vk: VideoKnowledge, segments: Sequence[Any], chunks: Sequence[Chunk],
           failed_chunks: Sequence[int]) -> dict[str, Any]:
    """Quality checks against the source transcript.

    * coverage: share of transcript time covered by at least one extracted item
    * grounding: share of concepts whose name (or a word of it) occurs in the transcript
    * timestamp validity: references inside the video duration
    """
    duration = segments[-1].end if segments else 0
    transcript_lower = " ".join(s.text for s in segments).lower()
    warnings: list[str] = []

    covered = set()
    for item in [*vk.concepts, *vk.examples, *vk.key_points, *vk.technical]:
        if item.start is not None:
            covered.add(int(item.start // 60))
    minutes = max(int(duration // 60) + 1, 1)
    coverage = min(len(covered) / minutes, 1.0)

    grounded = 0
    for c in vk.concepts:
        words = [w for w in re.findall(r"\w+", c.name.lower()) if len(w) > 2]
        if not words or any(w in transcript_lower for w in words):
            grounded += 1
    grounding = grounded / len(vk.concepts) if vk.concepts else 1.0

    bad_ts = sum(
        1
        for it in [*vk.concepts, *vk.examples, *vk.key_points]
        if it.start is not None and duration and it.start > duration + 5
    )
    if failed_chunks:
        warnings.append(
            f"{len(failed_chunks)} transcript part(s) could not be analysed by the AI "
            f"({', '.join(str(i + 1) for i in failed_chunks)}); their transcript is still included."
        )
    if coverage < 0.35 and duration > 300:
        warnings.append("Extracted notes cover less than 35% of the video timeline.")
    if grounding < 0.7:
        warnings.append("Some concept names were not found in the transcript; review them.")
    if bad_ts:
        warnings.append(f"{bad_ts} timestamp(s) were outside the video duration.")
    return {
        "chunks": len(chunks),
        "failed_chunks": list(failed_chunks),
        "timeline_coverage": round(coverage, 3),
        "concept_grounding": round(grounding, 3),
        "invalid_timestamps": bad_ts,
        "concepts": len(vk.concepts),
        "technical_items": len(vk.technical),
        "examples": len(vk.examples),
        "questions": len(vk.questions),
        "warnings": warnings,
    }


def build_video_knowledge(
    llm: LLMClient,
    segments: Sequence[Any],
    *,
    title: str,
    channel: str | None,
    output_language: str,
    detail_level: str,
    max_tokens: int,
    overlap: int,
    progress: ProgressFn | None = None,
) -> tuple[VideoKnowledge, dict[str, Any]]:
    progress = progress or (lambda p, s: None)
    budget = max_tokens if detail_level == "comprehensive" else int(max_tokens * 1.6)
    chunks = chunk_segments(segments, max_tokens=budget, overlap=overlap)
    if not chunks:
        raise ValueError("Transcript is empty")

    parts: list[ChunkKnowledge] = []
    failed: list[int] = []
    for ch in chunks:
        progress(ch.index / len(chunks), "extracting")
        try:
            parts.append(extract_chunk(llm, ch, len(chunks), title, channel, output_language, detail_level))
        except Exception as exc:  # keep going: one bad chunk must not kill a 2h lecture
            log.warning("chunk %s failed: %s", ch.index, exc)
            failed.append(ch.index)
            parts.append(ChunkKnowledge(section_title=f"Part {ch.index + 1}", summary=""))
    if len(failed) == len(chunks):
        raise RuntimeError("AI extraction failed for every part of the transcript")

    progress(1.0, "assembling")
    vk = assemble(chunks, parts)
    vk.title = title
    vk.output_language = output_language
    try:
        syn = synthesize_video(llm, vk, title, output_language)
        vk.overview = syn.overview
        vk.learning_objectives = syn.learning_objectives
        vk.takeaways = syn.takeaways
        vk.prerequisites = syn.prerequisites
    except Exception as exc:
        log.warning("video synthesis failed: %s", exc)
        vk.overview = "\n\n".join(c.summary for c in vk.chapters if c.summary)
        vk.takeaways = [k.text for k in vk.key_points[:10]]

    progress(1.0, "verifying")
    quality = verify(vk, segments, chunks, failed)
    return vk, quality


def condense_for_collection(position: int, title: str, vk: dict[str, Any]) -> str:
    """Compact representation of one video's knowledge for playlist synthesis."""
    concepts = ", ".join(c.get("name", "") for c in vk.get("concepts", [])[:25])
    takeaways = "; ".join(vk.get("takeaways", [])[:8])
    overview = (vk.get("overview") or "")[:1200]
    return f"### VIDEO {position}: {title}\nOverview: {overview}\nConcepts: {concepts}\nTakeaways: {takeaways}"


def build_collection_synthesis(llm: LLMClient, videos: list[tuple[int, str, dict[str, Any]]],
                               output_language: str, title: str) -> CollectionSynthesis:
    blocks = [condense_for_collection(pos, t, vk) for pos, t, vk in videos]
    # Keep the request inside free-tier context windows.
    budget = 28000
    text = "\n\n".join(blocks)
    if len(text) > budget:
        per = max(budget // max(len(blocks), 1), 400)
        text = "\n\n".join(b[:per] for b in blocks)
    user = f'Course / playlist: "{title}" ({len(videos)} videos)\n\n{text}'
    return llm.structured(collection_system(output_language), user, CollectionSynthesis, max_tokens=4096)
