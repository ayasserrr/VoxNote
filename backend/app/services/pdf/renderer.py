"""Professional PDF knowledge documents (ReportLab).

Two document types:
* `render_video_pdf`      - one complete knowledge document per video
* `render_collection_pdf` - a "playlist knowledge book" with course synthesis
                            followed by every video's document

Features: cover page, clickable table of contents + PDF outline, page numbers,
Arabic RTL / English LTR / mixed text, code blocks, glossary tables, clickable
YouTube timestamps, and a clear visual marker for AI-added clarifications.
"""

from __future__ import annotations

import io
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate,
    CondPageBreak,
    Flowable,
    Frame,
    KeepTogether,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    XPreformatted,
)
from reportlab.platypus.tableofcontents import TableOfContents

from app.services.chunking import fmt_ts, merge_short_segments
from app.services.language import has_arabic
from app.services.pdf.text import bidi_markup, shape

FONT_DIR = Path(__file__).parent / "fonts"
FONT = "VoxSans"
FONT_BOLD = "VoxSans-Bold"
FONT_MONO = "VoxMono"

_fonts_ready = False


def _register_fonts() -> None:
    global _fonts_ready
    if _fonts_ready:
        return
    pdfmetrics.registerFont(TTFont(FONT, str(FONT_DIR / "DejaVuSans.ttf")))
    pdfmetrics.registerFont(TTFont(FONT_BOLD, str(FONT_DIR / "DejaVuSans-Bold.ttf")))
    pdfmetrics.registerFont(TTFont(FONT_MONO, str(FONT_DIR / "DejaVuSansMono.ttf")))
    pdfmetrics.registerFontFamily(FONT, normal=FONT, bold=FONT_BOLD, italic=FONT, boldItalic=FONT_BOLD)
    _fonts_ready = True


# ----------------------------------------------------------------- theme
INK = colors.HexColor("#0f172a")
MUTED = colors.HexColor("#64748b")
ACCENT = colors.HexColor("#4f46e5")
ACCENT_SOFT = colors.HexColor("#eef2ff")
AI_SOFT = colors.HexColor("#fff7ed")
AI_EDGE = colors.HexColor("#f97316")
CODE_BG = colors.HexColor("#f1f5f9")
RULE = colors.HexColor("#e2e8f0")
LINK = "#2563eb"

PAGE_W, PAGE_H = A4
MARGIN = 20 * mm
FRAME_W = PAGE_W - 2 * MARGIN

LABELS = {
    "en": {
        "subtitle": "Complete Video Knowledge Document",
        "book_subtitle": "Playlist Knowledge Book",
        "contents": "Contents",
        "info": "Video Information",
        "title": "Title",
        "channel": "Channel",
        "duration": "Duration",
        "published": "Published",
        "language": "Detected language",
        "doc_language": "Document language",
        "source": "Source",
        "transcript_source": "Transcript source",
        "generated": "Generated",
        "model": "AI model",
        "overview": "Overview",
        "objectives": "Learning Objectives",
        "prerequisites": "Prerequisites",
        "chapters": "Chapters & Timeline",
        "concepts": "Detailed Explanation of Concepts",
        "definition": "Definition",
        "explanation": "Explanation",
        "instructor": "What the speaker said",
        "examples_of": "Examples",
        "ai": "AI-added clarification (not from the video)",
        "related": "Related",
        "technical": "Technical Concepts",
        "examples": "Examples & Use Cases",
        "key_points": "Key Points",
        "takeaways": "Important Takeaways",
        "glossary": "Glossary",
        "term": "Term",
        "translation": "Translation",
        "questions": "Review Questions",
        "answer": "Answer",
        "transcript": "Complete Transcript",
        "quality": "Quality Report",
        "course_summary": "Course Summary",
        "learning_path": "Learning Path",
        "course_concepts": "Concepts Covered Across the Course",
        "concept_map": "Concept Relationship Map",
        "recurring": "Recurring Concepts",
        "course_glossary": "Unified Course Glossary",
        "final_questions": "Course Review Questions",
        "videos": "Videos",
        "video": "Video",
        "page": "Page",
        "none": "Nothing recorded for this section.",
        "watch": "Watch on YouTube",
        "videos_in": "videos",
    },
    "ar": {
        "subtitle": "وثيقة المعرفة الكاملة للفيديو",
        "book_subtitle": "كتاب المعرفة لقائمة التشغيل",
        "contents": "المحتويات",
        "info": "معلومات الفيديو",
        "title": "العنوان",
        "channel": "القناة",
        "duration": "المدة",
        "published": "تاريخ النشر",
        "language": "اللغة المكتشفة",
        "doc_language": "لغة الوثيقة",
        "source": "المصدر",
        "transcript_source": "مصدر النص",
        "generated": "تاريخ الإنشاء",
        "model": "نموذج الذكاء الاصطناعي",
        "overview": "نظرة عامة",
        "objectives": "أهداف التعلم",
        "prerequisites": "المتطلبات المسبقة",
        "chapters": "الفصول والخط الزمني",
        "concepts": "الشرح التفصيلي للمفاهيم",
        "definition": "التعريف",
        "explanation": "الشرح",
        "instructor": "ما قاله المتحدث",
        "examples_of": "أمثلة",
        "ai": "توضيح إضافي من الذكاء الاصطناعي (ليس من الفيديو)",
        "related": "مفاهيم مرتبطة",
        "technical": "المفاهيم التقنية",
        "examples": "الأمثلة وحالات الاستخدام",
        "key_points": "النقاط الأساسية",
        "takeaways": "أهم الخلاصات",
        "glossary": "مسرد المصطلحات",
        "term": "المصطلح",
        "translation": "الترجمة",
        "questions": "أسئلة المراجعة",
        "answer": "الإجابة",
        "transcript": "النص الكامل",
        "quality": "تقرير الجودة",
        "course_summary": "ملخص الدورة",
        "learning_path": "مسار التعلم",
        "course_concepts": "المفاهيم عبر الدورة",
        "concept_map": "خريطة العلاقات بين المفاهيم",
        "recurring": "المفاهيم المتكررة",
        "course_glossary": "مسرد الدورة الموحد",
        "final_questions": "أسئلة مراجعة الدورة",
        "videos": "الفيديوهات",
        "video": "فيديو",
        "page": "صفحة",
        "none": "لا يوجد محتوى في هذا القسم.",
        "watch": "مشاهدة على يوتيوب",
        "videos_in": "فيديو",
    },
}


@dataclass
class VideoInput:
    """Everything the renderer needs about one video."""

    title: str
    youtube_id: str | None = None
    url: str | None = None
    channel: str | None = None
    duration_seconds: float | None = None
    published_at: str | None = None
    language: str | None = None
    transcript_source: str | None = None
    model: str | None = None
    knowledge: dict[str, Any] = field(default_factory=dict)
    quality: dict[str, Any] = field(default_factory=dict)
    segments: list[Any] = field(default_factory=list)
    position: int = 1


@dataclass
class RenderOptions:
    output_language: str = "en"  # en | ar | bilingual
    include_transcript: bool = True
    include_timestamps: bool = True


def _yt_link(youtube_id: str | None, start: float | None) -> str | None:
    if not youtube_id or start is None:
        return None
    return f"https://www.youtube.com/watch?v={youtube_id}&t={int(max(start, 0))}s"


class _Heading(Paragraph):
    """Paragraph that registers itself in the TOC and PDF outline."""

    def __init__(self, text: str, style: ParagraphStyle, level: int, toc_text: str, plain: str):
        super().__init__(text, style)
        self.toc_level = level
        self.toc_text = toc_text
        self.plain = plain


class _DocTemplate(BaseDocTemplate):
    def __init__(self, buf, footer_title: str, rtl: bool, labels: dict[str, str], toc_max_level: int = 1, **kw):
        super().__init__(buf, pagesize=A4, leftMargin=MARGIN, rightMargin=MARGIN,
                         topMargin=MARGIN, bottomMargin=MARGIN, **kw)
        self.footer_title = footer_title
        self.rtl = rtl
        self.labels = labels
        self._seq = 0
        self.toc_max_level = toc_max_level
        self._outline_level = -1
        frame = Frame(MARGIN, MARGIN, FRAME_W, PAGE_H - 2 * MARGIN, id="body",
                      leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
        self.addPageTemplates([
            PageTemplate(id="cover", frames=[frame], onPage=self._cover_page),
            PageTemplate(id="body", frames=[frame], onPage=self._body_page),
        ])

    def _cover_page(self, canv, doc):
        canv.saveState()
        canv.setFillColor(ACCENT)
        canv.rect(0, PAGE_H - 12 * mm, PAGE_W, 12 * mm, stroke=0, fill=1)
        canv.setFillColor(MUTED)
        canv.setFont(FONT, 8)
        canv.drawCentredString(PAGE_W / 2, 10 * mm, "Generated by VoxNote · AI-Powered Video Knowledge Extraction")
        canv.restoreState()

    def _body_page(self, canv, doc):
        canv.saveState()
        canv.setStrokeColor(RULE)
        canv.setLineWidth(0.5)
        canv.line(MARGIN, PAGE_H - MARGIN + 6 * mm, PAGE_W - MARGIN, PAGE_H - MARGIN + 6 * mm)
        canv.setFont(FONT, 8)
        canv.setFillColor(MUTED)
        title = self.footer_title if len(self.footer_title) < 90 else self.footer_title[:87] + "..."
        title = shape(title)
        if self.rtl:
            canv.drawRightString(PAGE_W - MARGIN, PAGE_H - MARGIN + 8 * mm, title)
            canv.drawString(MARGIN, PAGE_H - MARGIN + 8 * mm, "VoxNote")
        else:
            canv.drawString(MARGIN, PAGE_H - MARGIN + 8 * mm, title)
            canv.drawRightString(PAGE_W - MARGIN, PAGE_H - MARGIN + 8 * mm, "VoxNote")
        canv.drawCentredString(PAGE_W / 2, 10 * mm, f"{doc.page}")
        canv.restoreState()

    def beforeDocument(self) -> None:
        self._seq = 0
        self._outline_level = -1

    def afterFlowable(self, flowable: Flowable) -> None:
        if isinstance(flowable, _Heading):
            self._seq += 1
            key = f"h{self._seq}"
            self.canv.bookmarkPage(key)
            level = min(flowable.toc_level, self._outline_level + 1)
            self._outline_level = level
            self.canv.addOutlineEntry(flowable.plain[:120], key, level=level, closed=True)
            if flowable.toc_level <= self.toc_max_level:
                self.notify("TOCEntry", (flowable.toc_level, flowable.toc_text, self.page, key))


class _Builder:
    def __init__(self, opts: RenderOptions):
        _register_fonts()
        self.opts = opts
        self.lang = "ar" if opts.output_language in {"ar", "bilingual"} else "en"
        self.rtl = self.lang == "ar"
        self.L = LABELS[self.lang]
        align = TA_RIGHT if self.rtl else TA_LEFT
        self.base_align = align
        s = {}
        s["body"] = ParagraphStyle("body", fontName=FONT, fontSize=10, leading=15.5, textColor=INK,
                                   alignment=align, spaceAfter=5)
        s["small"] = ParagraphStyle("small", parent=s["body"], fontSize=8.5, leading=12, textColor=MUTED)
        s["h1"] = ParagraphStyle("h1", fontName=FONT_BOLD, fontSize=18, leading=24, textColor=INK,
                                 alignment=align, spaceBefore=6, spaceAfter=10)
        s["h2"] = ParagraphStyle("h2", fontName=FONT_BOLD, fontSize=13.5, leading=19, textColor=ACCENT,
                                 alignment=align, spaceBefore=12, spaceAfter=6)
        s["h3"] = ParagraphStyle("h3", fontName=FONT_BOLD, fontSize=11.5, leading=16, textColor=INK,
                                 alignment=align, spaceBefore=9, spaceAfter=3)
        s["label"] = ParagraphStyle("label", fontName=FONT_BOLD, fontSize=9, leading=13, textColor=MUTED,
                                    alignment=align, spaceBefore=4, spaceAfter=1)
        s["cover_title"] = ParagraphStyle("ct", fontName=FONT_BOLD, fontSize=26, leading=34, textColor=INK,
                                          alignment=align, spaceAfter=10)
        s["cover_sub"] = ParagraphStyle("cs", fontName=FONT, fontSize=13, leading=18, textColor=ACCENT,
                                        alignment=align, spaceAfter=24)
        s["code"] = ParagraphStyle("code", fontName=FONT_MONO, fontSize=8.5, leading=11.5, textColor=INK,
                                   backColor=CODE_BG, borderPadding=6, leftIndent=6, rightIndent=6,
                                   spaceBefore=4, spaceAfter=8)
        s["cell"] = ParagraphStyle("cell", fontName=FONT, fontSize=9, leading=12.5, textColor=INK, alignment=align)
        s["cell_b"] = ParagraphStyle("cellb", parent=s["cell"], fontName=FONT_BOLD)
        s["ts"] = ParagraphStyle("ts", fontName=FONT_MONO, fontSize=8, leading=12, textColor=MUTED,
                                 alignment=align, spaceAfter=2)
        s["center"] = ParagraphStyle("center", parent=s["body"], alignment=TA_CENTER)
        self.s = s

    # ---------------------------------------------------------- primitives
    def p(self, text: str | None, style: str = "body", indent: float = 0, width: float | None = None) -> Paragraph:
        st = self.s[style]
        text = text or ""
        avail = (width or FRAME_W) - indent - st.leftIndent - st.rightIndent
        markup, rtl = bidi_markup(text, st.fontName, st.fontSize, avail)
        if has_arabic(text):
            st = ParagraphStyle(f"{st.name}_{'r' if rtl else 'l'}", parent=st,
                                alignment=TA_RIGHT if rtl else TA_LEFT)
        if indent:
            st = ParagraphStyle(f"{st.name}_i", parent=st,
                                leftIndent=st.leftIndent + (0 if (self.rtl or rtl) else indent),
                                rightIndent=st.rightIndent + (indent if (self.rtl or rtl) else 0))
        return Paragraph(markup, st)

    def heading(self, text: str, level: int, number: str | None = None) -> _Heading:
        style = {0: "h1", 1: "h2", 2: "h3"}.get(level, "h3")
        st = self.s[style]
        full = f"{number}  {text}" if number else text
        markup, _ = bidi_markup(full, st.fontName, st.fontSize, FRAME_W)
        toc_text = escape(shape(full))
        return _Heading(markup, st, level, toc_text, full)

    def ts_line(self, youtube_id: str | None, start: float | None, end: float | None = None) -> Paragraph | None:
        if not self.opts.include_timestamps or start is None:
            return None
        label = fmt_ts(start) + (f" – {fmt_ts(end)}" if end is not None and end > start else "")
        link = _yt_link(youtube_id, start)
        text = f'<a href="{link}" color="{LINK}">▶ {label}</a>' if link else f"⏱ {label}"
        return Paragraph(text, self.s["ts"])

    def bullets(self, items: list[str], style: str = "body") -> list[Flowable]:
        out: list[Flowable] = []
        for it in items:
            if not it:
                continue
            out.append(self.p(f"• {it}", style, indent=10))
        return out

    def code(self, text: str) -> Flowable:
        lines = []
        for line in (text or "").splitlines() or [""]:
            while len(line) > 92:
                lines.append(line[:92])
                line = "    " + line[92:]
            lines.append(line)
        return XPreformatted(escape("\n".join(lines)), self.s["code"])

    def callout(self, title: str, body: str) -> Flowable:
        inner = [self.p(title, "label", width=FRAME_W - 20), self.p(body, "body", width=FRAME_W - 20)]
        t = Table([[inner]], colWidths=[FRAME_W])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), AI_SOFT),
            ("LINEBEFORE" if not self.rtl else "LINEAFTER", (0, 0), (-1, -1), 3, AI_EDGE),
            ("LEFTPADDING", (0, 0), (-1, -1), 10),
            ("RIGHTPADDING", (0, 0), (-1, -1), 10),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        return t

    def table(self, header: list[str], rows: list[list[str]], widths: list[float]) -> Table:
        if self.rtl:
            header = header[::-1]
            rows = [r[::-1] for r in rows]
            widths = widths[::-1]
        data = [[self.p(h, "cell_b", width=w - 10) for h, w in zip(header, widths, strict=False)]]
        for r in rows:
            data.append([self.p(c, "cell", width=w - 10) for c, w in zip(r, widths, strict=False)])
        t = Table(data, colWidths=widths, repeatRows=1)
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), ACCENT_SOFT),
            ("LINEBELOW", (0, 0), (-1, -1), 0.4, RULE),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        return t

    def empty(self) -> Paragraph:
        return self.p(self.L["none"], "small")

    # ------------------------------------------------------------ sections
    def info_table(self, v: VideoInput) -> Table:
        L = self.L
        rows = [
            [L["title"], v.title],
            [L["channel"], v.channel or "—"],
            [L["duration"], fmt_ts(v.duration_seconds) if v.duration_seconds else "—"],
            [L["published"], v.published_at or "—"],
            [L["language"], {"ar": "Arabic / العربية", "en": "English", "mixed": "Mixed Arabic + English"}.get(
                v.language or "", v.language or "—")],
            [L["doc_language"], {"ar": "العربية", "en": "English", "bilingual": "Bilingual / ثنائي اللغة"}.get(
                self.opts.output_language, self.opts.output_language)],
            [L["transcript_source"], v.transcript_source or "—"],
            [L["model"], v.model or "—"],
            [L["generated"], datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")],
        ]
        if v.url:
            rows.insert(1, [L["source"], v.url])
        widths = [42 * mm, FRAME_W - 42 * mm]
        if self.rtl:
            rows = [r[::-1] for r in rows]
            widths = widths[::-1]
        data = []
        for r in rows:
            cells = []
            for i, (c, w) in enumerate(zip(r, widths, strict=False)):
                is_label = (i == 0) != self.rtl
                cells.append(self.p(c, "cell_b" if is_label else "cell", width=w - 10))
            data.append(cells)
        t = Table(data, colWidths=widths)
        t.setStyle(TableStyle([
            ("LINEBELOW", (0, 0), (-1, -1), 0.4, RULE),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        return t

    def video_sections(self, v: VideoInput, level: int, numbered: bool = True) -> list[Flowable]:
        """All knowledge sections of one video. `level` is the heading level of sections."""
        L = self.L
        k = v.knowledge or {}
        yid = v.youtube_id
        story: list[Flowable] = []
        n = 0

        def section(title: str) -> None:
            nonlocal n
            n += 1
            story.append(CondPageBreak(60 * mm))
            story.append(self.heading(title, level, f"{n:02d}" if numbered else None))

        # Overview
        section(L["overview"])
        if k.get("overview"):
            for para in str(k["overview"]).split("\n\n"):
                story.append(self.p(para.strip()))
        else:
            story.append(self.empty())
        if k.get("learning_objectives"):
            story.append(self.p(L["objectives"], "label"))
            story += self.bullets(k["learning_objectives"])
        if k.get("prerequisites"):
            story.append(self.p(L["prerequisites"], "label"))
            story += self.bullets(k["prerequisites"])

        # Chapters
        chapters = k.get("chapters") or []
        if chapters:
            section(L["chapters"])
            for ch in chapters:
                block: list[Flowable] = [self.p(ch.get("title", ""), "h3")]
                ts = self.ts_line(yid, ch.get("start"), ch.get("end"))
                if ts:
                    block.append(ts)
                if ch.get("summary"):
                    block.append(self.p(ch["summary"]))
                story.append(KeepTogether(block))

        # Concepts
        section(L["concepts"])
        concepts = k.get("concepts") or []
        if not concepts:
            story.append(self.empty())
        for c in concepts:
            head: list[Flowable] = [self.p(c.get("name", ""), "h3")]
            ts = self.ts_line(yid, c.get("start"), c.get("end"))
            if ts:
                head.append(ts)
            if c.get("definition"):
                head += [self.p(L["definition"], "label"), self.p(c["definition"])]
            story.append(KeepTogether(head))
            if c.get("explanation"):
                story.append(self.p(L["explanation"], "label"))
                for para in str(c["explanation"]).split("\n\n"):
                    story.append(self.p(para.strip()))
            if c.get("instructor_points"):
                story.append(self.p(L["instructor"], "label"))
                story += self.bullets(c["instructor_points"])
            if c.get("examples"):
                story.append(self.p(L["examples_of"], "label"))
                story += self.bullets(c["examples"])
            if c.get("ai_clarification"):
                story.append(Spacer(1, 3))
                story.append(self.callout(L["ai"], c["ai_clarification"]))
            if c.get("related"):
                story.append(self.p(f"{L['related']}: " + ", ".join(c["related"]), "small"))
            story.append(Spacer(1, 6))

        # Technical
        tech = k.get("technical") or []
        if tech:
            section(L["technical"])
            for t in tech:
                title = t.get("title") or t.get("kind", "").title()
                kind = t.get("kind", "other")
                lang = f" · {t['language']}" if t.get("language") else ""
                block = [self.p(f"{title}  [{kind}{lang}]", "h3")]
                ts = self.ts_line(yid, t.get("start"))
                if ts:
                    block.append(ts)
                story.append(KeepTogether(block))
                if t.get("content"):
                    if kind in {"code", "command", "equation"} or "\n" in t["content"]:
                        story.append(self.code(t["content"]))
                    else:
                        story.append(self.p(t["content"]))
                if t.get("explanation"):
                    story.append(self.p(t["explanation"]))

        # Examples
        section(L["examples"])
        examples = k.get("examples") or []
        if not examples:
            story.append(self.empty())
        for e in examples:
            block = []
            if e.get("title"):
                block.append(self.p(e["title"], "h3"))
            ts = self.ts_line(yid, e.get("start"))
            if ts:
                block.append(ts)
            block.append(self.p(e.get("description", "")))
            story.append(KeepTogether(block))

        # Key points & takeaways
        section(L["takeaways"])
        if k.get("takeaways"):
            story += self.bullets(k["takeaways"])
        kp = k.get("key_points") or []
        if kp:
            story.append(self.p(L["key_points"], "label"))
            for item in kp:
                text = item.get("text", "")
                if self.opts.include_timestamps and item.get("start") is not None:
                    text = f"{text}  ({fmt_ts(item['start'])})"
                story += self.bullets([text])
        if not k.get("takeaways") and not kp:
            story.append(self.empty())

        # Glossary
        glossary = k.get("glossary") or []
        section(L["glossary"])
        if glossary:
            show_tr = any(g.get("translation") for g in glossary)
            if show_tr:
                header = [L["term"], L["definition"], L["translation"]]
                widths = [40 * mm, FRAME_W - 80 * mm, 40 * mm]
                rows = [[g.get("term", ""), g.get("definition", ""), g.get("translation", "")] for g in glossary]
            else:
                header = [L["term"], L["definition"]]
                widths = [45 * mm, FRAME_W - 45 * mm]
                rows = [[g.get("term", ""), g.get("definition", "")] for g in glossary]
            story.append(self.table(header, rows, widths))
        else:
            story.append(self.empty())

        # Questions
        questions = k.get("questions") or []
        section(L["questions"])
        if not questions:
            story.append(self.empty())
        for i, q in enumerate(questions, 1):
            block = [self.p(f"{i}. {q.get('question', '')}", "h3")]
            if q.get("answer"):
                block.append(self.p(f"{L['answer']}: {q['answer']}"))
            story.append(KeepTogether(block))

        # Transcript
        if self.opts.include_transcript and v.segments:
            section(L["transcript"])
            story += self.transcript(v)

        # Quality
        qual = v.quality or {}
        if qual:
            section(L["quality"])
            rows = [
                ["Timeline coverage", f"{round(100 * qual.get('timeline_coverage', 0))}%"],
                ["Concept grounding", f"{round(100 * qual.get('concept_grounding', 0))}%"],
                ["Transcript parts analysed", f"{qual.get('chunks', 0) - len(qual.get('failed_chunks', []))}/"
                                              f"{qual.get('chunks', 0)}"],
                ["Concepts / technical items / examples",
                 f"{qual.get('concepts', 0)} / {qual.get('technical_items', 0)} / {qual.get('examples', 0)}"],
            ]
            story.append(self.table(["Metric", "Value"], rows, [90 * mm, FRAME_W - 90 * mm]))
            for w in qual.get("warnings", []):
                story.append(self.p(f"⚠ {w}", "small"))
        return story

    def transcript(self, v: VideoInput) -> list[Flowable]:
        out: list[Flowable] = []
        ts_w = 22 * mm
        txt_w = FRAME_W - ts_w
        for seg in merge_short_segments(v.segments):
            link = _yt_link(v.youtube_id, seg.start)
            label = fmt_ts(seg.start)
            ts_markup = f'<a href="{link}" color="{LINK}">{label}</a>' if link else label
            ts_p = Paragraph(ts_markup, self.s["ts"])
            text_p = self.p(seg.text, "body", width=txt_w - 6)
            row = [text_p, ts_p] if self.rtl else [ts_p, text_p]
            widths = [txt_w, ts_w] if self.rtl else [ts_w, txt_w]
            t = Table([row], colWidths=widths)
            t.setStyle(TableStyle([
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 1),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
            ]))
            out.append(t)
        return out

    def toc(self) -> list[Flowable]:
        toc = TableOfContents()
        toc.levelStyles = [
            ParagraphStyle("toc0", fontName=FONT_BOLD, fontSize=10.5, leading=16, leftIndent=0,
                           firstLineIndent=0, textColor=INK),
            ParagraphStyle("toc1", fontName=FONT, fontSize=9.5, leading=14, leftIndent=14,
                           firstLineIndent=0, textColor=INK),
        ]
        toc.dotsMinLevel = 0
        return [self.p(self.L["contents"], "h1"), toc]


def _build(story: list[Flowable], footer_title: str, builder: _Builder, title: str,
           toc_max_level: int = 1) -> tuple[bytes, int]:
    buf = io.BytesIO()
    doc = _DocTemplate(buf, footer_title, builder.rtl, builder.L, toc_max_level, title=title, author="VoxNote",
                       creator="VoxNote", subject="Video knowledge document")
    doc.multiBuild(story, maxPasses=6)
    return buf.getvalue(), doc.page


def _cover(b: _Builder, title: str, subtitle: str, extra: list[Flowable]) -> list[Flowable]:
    from reportlab.platypus import NextPageTemplate

    story: list[Flowable] = [Spacer(1, 40 * mm), b.p("VOXNOTE", "small"), b.p(title, "cover_title"),
                             b.p(subtitle, "cover_sub")]
    story += extra
    story += [NextPageTemplate("body"), PageBreak()]
    return story


def render_video_pdf(v: VideoInput, opts: RenderOptions) -> tuple[bytes, int]:
    b = _Builder(opts)
    story = _cover(b, v.title, b.L["subtitle"], [b.heading(b.L["info"], 1, "00"), b.info_table(v)])
    story += b.toc() + [PageBreak()]
    story += b.video_sections(v, level=1)
    return _build(story, v.title, b, v.title)


def render_collection_pdf(
    title: str,
    channel: str | None,
    synthesis: dict[str, Any] | None,
    videos: list[VideoInput],
    opts: RenderOptions,
) -> tuple[bytes, int]:
    b = _Builder(opts)
    L = b.L
    syn = synthesis or {}
    total = sum(v.duration_seconds or 0 for v in videos)
    meta = [
        b.p(f"{len(videos)} {L['videos_in']}" + (f" · {fmt_ts(total)}" if total else "")
            + (f" · {channel}" if channel else ""), "body"),
        Spacer(1, 8),
    ]
    for v in videos:
        meta.append(b.p(f"{v.position:02d}. {v.title}", "small"))
    story = _cover(b, syn.get("course_title") or title, L["book_subtitle"], meta)
    story += b.toc() + [PageBreak()]

    # ---- Course-level synthesis
    story.append(b.heading(L["course_summary"], 0))
    if syn.get("course_summary"):
        for para in str(syn["course_summary"]).split("\n\n"):
            story.append(b.p(para.strip()))
    else:
        story.append(b.empty())

    def vids(nums: list[int]) -> str:
        return ", ".join(f"#{n}" for n in nums)

    if syn.get("learning_path"):
        story.append(b.heading(L["learning_path"], 1))
        rows = [[f"{i}", s.get("step", ""), s.get("goal", ""), vids(s.get("videos", []))]
                for i, s in enumerate(syn["learning_path"], 1)]
        story.append(b.table(["#", L["learning_path"], "Goal" if b.lang == "en" else "الهدف", L["videos"]], rows,
                             [10 * mm, 70 * mm, FRAME_W - 110 * mm, 30 * mm]))
    if syn.get("concepts"):
        story.append(b.heading(L["course_concepts"], 1))
        rows = [[c.get("name", ""), c.get("description", ""), vids(c.get("videos", []))] for c in syn["concepts"]]
        story.append(b.table([L["term"], L["explanation"], L["videos"]], rows,
                             [45 * mm, FRAME_W - 75 * mm, 30 * mm]))
    if syn.get("concept_map"):
        story.append(b.heading(L["concept_map"], 1))
        rows = [[m.get("source", ""), m.get("relation", ""), m.get("target", "")] for m in syn["concept_map"]]
        story.append(b.table(["A", "→", "B"], rows, [60 * mm, FRAME_W - 120 * mm, 60 * mm]))
    if syn.get("recurring_concepts"):
        story.append(b.heading(L["recurring"], 1))
        story += b.bullets(syn["recurring_concepts"])
    if syn.get("glossary"):
        story.append(b.heading(L["course_glossary"], 1))
        rows = [[g.get("term", ""), g.get("definition", ""), g.get("translation", "")] for g in syn["glossary"]]
        story.append(b.table([L["term"], L["definition"], L["translation"]], rows,
                             [40 * mm, FRAME_W - 80 * mm, 40 * mm]))
    if syn.get("final_questions"):
        story.append(b.heading(L["final_questions"], 1))
        for i, q in enumerate(syn["final_questions"], 1):
            story.append(b.p(f"{i}. {q.get('question', '')}", "h3"))
            if q.get("answer"):
                story.append(b.p(f"{L['answer']}: {q['answer']}"))

    # ---- Every video
    for v in videos:
        story.append(PageBreak())
        story.append(b.heading(f"{L['video']} {v.position:02d} · {v.title}", 0))
        story.append(b.info_table(v))
        story += b.video_sections(v, level=1, numbered=True)
    return _build(story, syn.get("course_title") or title, b, title, toc_max_level=0)
