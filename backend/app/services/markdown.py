"""Markdown export (for Notion, Obsidian, GitHub...)."""

from __future__ import annotations

from typing import Any

from app.services.chunking import fmt_ts, merge_short_segments


def _ts(youtube_id: str | None, start: float | None, end: float | None = None) -> str:
    if start is None:
        return ""
    label = fmt_ts(start) + (f"–{fmt_ts(end)}" if end and end > start else "")
    if youtube_id:
        return f" [▶ {label}](https://www.youtube.com/watch?v={youtube_id}&t={int(start)}s)"
    return f" ({label})"


def video_markdown(title: str, youtube_id: str | None, meta: dict[str, Any], k: dict[str, Any],
                   segments: list[Any] | None, include_transcript: bool = True, heading: str = "#") -> str:
    h2, h3 = heading + "#", heading + "##"
    out = [f"{heading} {title}", ""]
    for label, key in (("Channel", "channel"), ("Duration", "duration"), ("Language", "language"),
                       ("Source", "url")):
        if meta.get(key):
            out.append(f"- **{label}:** {meta[key]}")
    out.append("")
    if k.get("overview"):
        out += [f"{h2} Overview", "", k["overview"], ""]
    if k.get("learning_objectives"):
        out += [f"{h3} Learning objectives", ""] + [f"- {x}" for x in k["learning_objectives"]] + [""]
    if k.get("chapters"):
        out += [f"{h2} Chapters", ""]
        for ch in k["chapters"]:
            out += [f"{h3} {ch.get('title', '')}{_ts(youtube_id, ch.get('start'), ch.get('end'))}", "",
                    ch.get("summary", ""), ""]
    if k.get("concepts"):
        out += [f"{h2} Concepts", ""]
        for c in k["concepts"]:
            out += [f"{h3} {c.get('name', '')}{_ts(youtube_id, c.get('start'), c.get('end'))}", ""]
            if c.get("definition"):
                out += [f"**Definition:** {c['definition']}", ""]
            if c.get("explanation"):
                out += [c["explanation"], ""]
            if c.get("instructor_points"):
                out += ["**What the speaker said:**", ""] + [f"- {p}" for p in c["instructor_points"]] + [""]
            if c.get("examples"):
                out += ["**Examples:**", ""] + [f"- {p}" for p in c["examples"]] + [""]
            if c.get("ai_clarification"):
                out += [f"> **AI-added clarification:** {c['ai_clarification']}", ""]
    if k.get("technical"):
        out += [f"{h2} Technical concepts", ""]
        for t in k["technical"]:
            out += [f"{h3} {t.get('title') or t.get('kind', '')}{_ts(youtube_id, t.get('start'))}", ""]
            if t.get("content"):
                out += [f"```{t.get('language', '')}", t["content"], "```", ""]
            if t.get("explanation"):
                out += [t["explanation"], ""]
    if k.get("examples"):
        out += [f"{h2} Examples & use cases", ""]
        for e in k["examples"]:
            stamp = _ts(youtube_id, e.get("start"))
            out.append(f"- **{e.get('title') or 'Example'}**{stamp}: {e.get('description', '')}")
        out.append("")
    if k.get("takeaways"):
        out += [f"{h2} Important takeaways", ""] + [f"- {x}" for x in k["takeaways"]] + [""]
    if k.get("glossary"):
        out += [f"{h2} Glossary", "", "| Term | Definition | Translation |", "|---|---|---|"]
        for g in k["glossary"]:
            cells = [str(g.get(x, "")).replace("|", "\\|").replace("\n", " ")
                     for x in ("term", "definition", "translation")]
            out.append("| " + " | ".join(cells) + " |")
        out.append("")
    if k.get("questions"):
        out += [f"{h2} Review questions", ""]
        for i, q in enumerate(k["questions"], 1):
            out.append(f"{i}. **{q.get('question', '')}**")
            if q.get("answer"):
                out.append(f"   <details><summary>Answer</summary>{q['answer']}</details>")
        out.append("")
    if include_transcript and segments:
        out += [f"{h2} Transcript", ""]
        for seg in merge_short_segments(segments):
            stamp = (f"[{fmt_ts(seg.start)}](https://www.youtube.com/watch?v={youtube_id}&t={int(seg.start)}s)"
                     if youtube_id else fmt_ts(seg.start))
            out += [f"**{stamp}** {seg.text}", ""]
    return "\n".join(out)


def collection_markdown(title: str, synthesis: dict[str, Any] | None, video_blocks: list[str]) -> str:
    syn = synthesis or {}
    out = [f"# {syn.get('course_title') or title}", ""]
    if syn.get("course_summary"):
        out += ["## Course summary", "", syn["course_summary"], ""]
    if syn.get("learning_path"):
        out += ["## Learning path", ""]
        for i, s in enumerate(syn["learning_path"], 1):
            vids = ", ".join(f"#{v}" for v in s.get("videos", []))
            out.append(f"{i}. **{s.get('step', '')}** {('— ' + s['goal']) if s.get('goal') else ''} ({vids})")
        out.append("")
    if syn.get("concept_map"):
        out += ["## Concept map", ""] + [
            f"- {m.get('source')} → *{m.get('relation')}* → {m.get('target')}" for m in syn["concept_map"]
        ] + [""]
    if syn.get("recurring_concepts"):
        out += ["## Recurring concepts", ""] + [f"- {c}" for c in syn["recurring_concepts"]] + [""]
    if syn.get("glossary"):
        out += ["## Course glossary", "", "| Term | Definition | Translation |", "|---|---|---|"]
        for g in syn["glossary"]:
            out.append(f"| {g.get('term', '')} | {g.get('definition', '')} | {g.get('translation', '')} |")
        out.append("")
    for block in video_blocks:
        out += ["---", "", block, ""]
    return "\n".join(out)
