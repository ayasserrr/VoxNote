import pytest

from app.schemas.knowledge import ChunkKnowledge, Concept, TechnicalItem
from app.security import create_access_token, decode_access_token, hash_password, verify_password
from app.services.chunking import chunk_segments, estimate_tokens, fmt_ts
from app.services.knowledge import merge_concepts
from app.services.language import detect_language, resolve_output_language
from app.services.llm import extract_json
from app.services.search import tokenize
from app.services.youtube import YouTubeError, parse_youtube_url
from tests.conftest import AR_LINES, EN_LINES, make_segments


@pytest.mark.parametrize(
    "url,kind,vid,pid",
    [
        ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "video", "dQw4w9WgXcQ", None),
        ("https://youtu.be/dQw4w9WgXcQ?t=42", "video", "dQw4w9WgXcQ", None),
        ("youtube.com/shorts/dQw4w9WgXcQ", "video", "dQw4w9WgXcQ", None),
        ("https://m.youtube.com/embed/dQw4w9WgXcQ", "video", "dQw4w9WgXcQ", None),
        ("dQw4w9WgXcQ", "video", "dQw4w9WgXcQ", None),
        ("https://www.youtube.com/playlist?list=PLZHQObOWTQDNU6R1_67000Dx_ZCJB-3pi", "playlist", None,
         "PLZHQObOWTQDNU6R1_67000Dx_ZCJB-3pi"),
        ("https://www.youtube.com/watch?v=dQw4w9WgXcQ&list=PLZHQObOWTQDNU6R1_67000Dx_ZCJB-3pi", "playlist",
         "dQw4w9WgXcQ", "PLZHQObOWTQDNU6R1_67000Dx_ZCJB-3pi"),
    ],
)
def test_parse_youtube_url(url, kind, vid, pid):
    p = parse_youtube_url(url)
    assert p.kind == kind
    assert p.video_id == vid
    assert p.playlist_id == pid


@pytest.mark.parametrize("url", ["https://vimeo.com/123", "", "https://www.youtube.com/channel/abc"])
def test_parse_youtube_url_rejects(url):
    with pytest.raises(YouTubeError):
        parse_youtube_url(url)


def test_language_detection():
    assert detect_language(" ".join(EN_LINES)) == "en"
    assert detect_language("التعلم الآلي هو فرع من الذكاء الاصطناعي") == "ar"
    assert detect_language(" ".join(AR_LINES)) == "mixed"
    assert resolve_output_language("auto", "mixed") == "bilingual"
    assert resolve_output_language("auto", "ar") == "ar"
    assert resolve_output_language("en", "ar") == "en"


def test_chunking_respects_budget_and_overlap():
    segs = make_segments(EN_LINES, repeat=20)
    chunks = chunk_segments(segs, max_tokens=300, overlap=2)
    assert len(chunks) > 3
    for c in chunks:
        assert c.tokens <= 300 + 60
    # overlap: last 2 segments of a chunk start the next
    assert chunks[1].segments[:2] == chunks[0].segments[-2:]
    # every segment appears somewhere
    covered = {id(s) for c in chunks for s in c.segments}
    assert all(id(s) in covered for s in segs)


def test_estimate_tokens_and_fmt():
    assert estimate_tokens("") == 0
    assert estimate_tokens("hello world " * 10) > 20
    assert fmt_ts(65) == "01:05"
    assert fmt_ts(3725) == "1:02:05"


def test_extract_json_variants():
    assert extract_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert extract_json('Sure! here: {"a": [1,2,],} thanks') == {"a": [1, 2]}
    assert extract_json('<think>hmm</think>{"b": 2}') == {"b": 2}
    with pytest.raises(ValueError):
        extract_json("no json here")


def test_schema_is_lenient():
    ck = ChunkKnowledge.model_validate({
        "concepts": [{"name": "GD", "start": "02:05", "end": "180"}],
        "technical": [{"kind": "Library", "title": "sklearn"}],
        "unknown_field": 1,
    })
    assert ck.concepts[0].start == 125
    assert ck.concepts[0].end == 180
    assert ck.technical[0].kind == "tool"
    assert TechnicalItem(kind="weird").kind == "other"


def test_merge_concepts_dedupes_and_widens_time():
    merged = merge_concepts([
        Concept(name="Gradient Descent", definition="d1", start=100, end=200, examples=["e1"]),
        Concept(name="gradient descent", explanation="more", start=50, end=300, examples=["e1", "e2"]),
        Concept(name="Regression", start=10),
    ])
    assert len(merged) == 2
    gd = merged[0]
    assert gd.start == 50 and gd.end == 300
    assert gd.examples == ["e1", "e2"]
    assert gd.definition == "d1" and "more" in gd.explanation


def test_password_and_jwt():
    h = hash_password("pw123456")
    assert verify_password("pw123456", h)
    assert not verify_password("wrong", h)
    tok = create_access_token("user-1")
    assert decode_access_token(tok) == "user-1"
    assert decode_access_token("garbage") is None


def test_arabic_tokenize_normalizes():
    toks = tokenize("التعلم الآلي و الـ Machine Learning")
    assert "machine" in toks and "learning" in toks
    assert "تعلم" in toks
