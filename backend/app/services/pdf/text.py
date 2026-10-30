"""Bidirectional text helpers for ReportLab.

ReportLab draws glyphs left-to-right and knows nothing about Arabic shaping
or the Unicode bidi algorithm. Naively applying `get_display()` to a whole
paragraph and letting ReportLab wrap it puts the *end* of the sentence on the
first line. We therefore:

1. wrap the paragraph ourselves in *logical* order, measuring shaped widths,
2. reshape (connect letters) and reorder (bidi) each line separately,
3. hand ReportLab pre-broken lines joined by <br/>.

This gives correct RTL Arabic, LTR English and mixed Arabic/English lines.
"""

from __future__ import annotations

from xml.sax.saxutils import escape

import arabic_reshaper
from bidi.algorithm import get_display
from reportlab.pdfbase.pdfmetrics import stringWidth

from app.services.language import has_arabic, is_mostly_arabic

_reshaper = arabic_reshaper.ArabicReshaper(
    configuration={"delete_harakat": False, "support_ligatures": True, "use_unshaped_instead_of_isolated": True}
)


def shape(text: str, rtl: bool | None = None) -> str:
    """Shape + reorder a single visual line."""
    if not has_arabic(text):
        return text
    if rtl is None:
        rtl = is_mostly_arabic(text)
    return get_display(_reshaper.reshape(text), base_dir="R" if rtl else "L")


def wrap_logical(text: str, font: str, size: float, width: float) -> list[str]:
    lines: list[str] = []
    for para in text.split("\n"):
        words = para.split()
        if not words:
            lines.append("")
            continue
        cur = words[0]
        for w in words[1:]:
            trial = f"{cur} {w}"
            if stringWidth(_reshaper.reshape(trial), font, size) <= width:
                cur = trial
            else:
                lines.append(cur)
                cur = w
        lines.append(cur)
    return lines


def bidi_markup(text: str, font: str, size: float, width: float, rtl: bool | None = None) -> tuple[str, bool]:
    """Return (ReportLab markup, is_rtl) for possibly-Arabic text."""
    text = (text or "").strip()
    if not has_arabic(text):
        return escape(text).replace("\n", "<br/>"), False
    if rtl is None:
        rtl = is_mostly_arabic(text)
    lines = wrap_logical(text, font, size, width * 0.97)
    return "<br/>".join(escape(shape(line, rtl)) for line in lines), rtl
