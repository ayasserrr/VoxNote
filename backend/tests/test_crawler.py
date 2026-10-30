import pytest

from app.services.crawler import Crawler, CrawlError, extract_page, in_scope, normalize_url, scope_prefix
from tests.docs_site import make_client


def test_normalize_and_scope():
    assert normalize_url("https://Site.dev/docs/index.html#x") == "https://site.dev/docs/"
    assert normalize_url("https://site.dev/a?utm_source=x") == "https://site.dev/a"
    assert normalize_url("mailto:a@b.c") == ""
    host, prefix = scope_prefix("https://site.dev/docs/intro", True)
    assert (host, prefix) == ("site.dev", "/docs/")
    assert in_scope("https://site.dev/docs/x", host, prefix)
    assert not in_scope("https://site.dev/blog/x", host, prefix)
    assert not in_scope("https://site.dev/docs/logo.png", host, prefix)
    assert not in_scope("https://other.dev/docs/x", host, prefix)


def test_crawl_fake_docs_site():
    res = Crawler("https://minilib.dev/docs/", client=make_client(), delay=0).crawl()
    urls = [p.url for p in res.pages]
    # sidebar order is preserved, sitemap adds the hidden page, robots.txt blocks /private/
    assert urls[:4] == ["https://minilib.dev/docs/", "https://minilib.dev/docs/install.html",
                        "https://minilib.dev/docs/quickstart", "https://minilib.dev/docs/concepts/models"]
    assert "https://minilib.dev/docs/hidden" in urls
    assert not any("private" in u or "blog" in u or "pricing" in u for u in urls)
    install = res.pages[1]
    assert "```bash\npip install minilib\n```" in install.content
    assert "| Python | Supported |" in install.content
    # navigation, cookie banner and footer are stripped
    for p in res.pages:
        assert "cookies" not in p.content and "Copyright" not in p.content and "Pricing" not in p.content


def test_max_pages_limit_and_warning():
    res = Crawler("https://minilib.dev/docs/", client=make_client(), delay=0, max_pages=2).crawl()
    assert len(res.pages) == 2
    assert any("page limit" in w for w in res.warnings)


def test_bad_start_page():
    with pytest.raises(CrawlError):
        Crawler("https://minilib.dev/docs/missing", client=make_client(), delay=0).crawl()


def test_extract_keeps_inline_code_and_lists():
    html = """<html><body><nav>menu</nav><main><h1>T</h1><p>Use <code>foo()</code> now.</p>
    <ol><li>first</li><li>second</li></ol></main></body></html>"""
    page = extract_page(html, "https://x.dev/a")
    assert "`foo()`" in page.content and "1. first" in page.content and "menu" not in page.content
