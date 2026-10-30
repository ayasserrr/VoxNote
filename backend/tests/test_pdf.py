from app.services.knowledge import build_video_knowledge
from app.services.llm import LLMClient
from app.services.markdown import video_markdown
from app.services.pdf.renderer import RenderOptions, VideoInput, render_collection_pdf, render_video_pdf
from app.services.pdf.text import bidi_markup
from tests.conftest import AR_LINES, EN_LINES, make_segments


def _vi(lines, lang, out_lang):
    segs = make_segments(lines)
    vk, q = build_video_knowledge(LLMClient(), segs, title="T", channel="C", output_language=out_lang,
                                  detail_level="comprehensive", max_tokens=400, overlap=1)
    return VideoInput(title="Test video", youtube_id="dQw4w9WgXcQ", language=lang, knowledge=vk.model_dump(),
                      quality=q, segments=segs, duration_seconds=segs[-1].end)


def test_english_pdf():
    pdf, pages = render_video_pdf(_vi(EN_LINES, "en", "en"), RenderOptions(output_language="en"))
    assert pdf.startswith(b"%PDF") and pages >= 3


def test_arabic_pdf_and_collection_book():
    ar = _vi(AR_LINES, "mixed", "bilingual")
    pdf, pages = render_video_pdf(ar, RenderOptions(output_language="bilingual"))
    assert pdf.startswith(b"%PDF") and pages >= 3
    en = _vi(EN_LINES, "en", "en")
    en.position = 2
    book, book_pages = render_collection_pdf(
        "Course", "Chan",
        {"course_summary": "s", "concept_map": [{"source": "a", "target": "b", "relation": "r"}],
         "learning_path": [{"step": "x", "videos": [1, 2]}]},
        [ar, en], RenderOptions(output_language="en"),
    )
    assert book.startswith(b"%PDF") and book_pages > pages


def test_bidi_markup_wraps_rtl_lines_in_order():
    text = "التعلم الآلي هو فرع من الذكاء الاصطناعي " * 6
    from app.services.pdf.renderer import FONT, _register_fonts

    _register_fonts()
    markup, rtl = bidi_markup(text, FONT, 10, 200)
    assert rtl and markup.count("<br/>") >= 2
    plain, rtl2 = bidi_markup("plain <english> & text", FONT, 10, 200)
    assert not rtl2 and "&lt;english&gt;" in plain


def test_markdown_export():
    vi = _vi(EN_LINES, "en", "en")
    md = video_markdown("Title", "dQw4w9WgXcQ", {"channel": "C"}, vi.knowledge, vi.segments)
    assert md.startswith("# Title") and "## Transcript" in md and "youtube.com/watch" in md
