"""Documentation crawler.

Given the URL of a documentation site (or a single article), discover the
pages that belong to it and extract their *main content* as clean,
Markdown-like text (headings, paragraphs, lists, tables and code blocks are
preserved; navigation, sidebars, footers and cookie banners are removed).

Discovery
---------
* Scope = same host + the "directory" of the start URL
  (``https://site.dev/docs/intro`` -> everything under ``/docs/``).
  ``same_path_only=False`` widens the scope to the whole host.
* Breadth-first crawl following links in document order. Documentation sites
  list their sidebar in reading order, so BFS from the start page yields a
  sensible learning order.
* ``sitemap.xml`` (and sitemaps listed in robots.txt) add pages that are not
  linked from the start page.
* robots.txt is respected, requests are throttled, and the crawl stops at
  ``max_pages``.

Limitations: sites that render content only with JavaScript return little
text; this is detected and reported as a warning.
"""

from __future__ import annotations

import hashlib
import logging
import re
import time
import xml.etree.ElementTree as ET
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from urllib.parse import urldefrag, urljoin, urlparse
from urllib.robotparser import RobotFileParser

import httpx
from bs4 import BeautifulSoup, NavigableString, Tag

log = logging.getLogger(__name__)

USER_AGENT = "VoxNoteBot/1.0 (+https://github.com/ayasserrr/VoxNote; learning assistant)"

_SKIP_EXT = re.compile(
    r"\.(png|jpe?g|gif|svg|webp|ico|pdf|zip|gz|tar|tgz|whl|exe|dmg|mp4|mp3|wav|webm|css|js|json|xml|txt|"
    r"woff2?|ttf|eot|map|ipynb|py|rst|md)$",
    re.I,
)
_SKIP_PATH = re.compile(
    r"/(genindex|search|_sources|_static|_images|assets|static|login|signin|signup|logout|tag|tags|"
    r"category|author|feed|rss|print)(/|$|\.)",
    re.I,
)
_NOISE_CLASS = re.compile(
    r"(^|[\s_-])(nav|navbar|navigation|sidebar|side-bar|menu|toc|breadcrumbs?|footer|header|cookie|banner|"
    r"edit-?this|edit-page|feedback|pagination|prev-next|skip|share|social|announcement|version-?switcher|"
    r"theme-?toggle|search|ads?|advert|sponsor|newsletter|related|on-this-page|headerlink|copy)([\s_-]|$)",
    re.I,
)
_CONTENT_HINT = re.compile(r"(content|markdown|article|documentation|docs?-?body|main|post|prose|rst-content)", re.I)


class CrawlError(Exception):
    pass


@dataclass
class CrawledPage:
    url: str
    title: str
    content: str
    headings: list[str] = field(default_factory=list)
    links: list[str] = field(default_factory=list)

    @property
    def word_count(self) -> int:
        return len(self.content.split())


@dataclass
class CrawlResult:
    pages: list[CrawledPage]
    visited: int
    skipped: int
    warnings: list[str] = field(default_factory=list)


# --------------------------------------------------------------------- URLs
def normalize_url(url: str) -> str:
    url, _ = urldefrag(url.strip())
    p = urlparse(url)
    if p.scheme not in ("http", "https"):
        return ""
    path = re.sub(r"/index\.html?$", "/", p.path or "/")
    path = re.sub(r"/{2,}", "/", path)
    query = f"?{p.query}" if p.query and not re.search(r"(utm_|ref=|source=)", p.query) else ""
    return f"{p.scheme}://{p.netloc.lower()}{path}{query}"


def scope_prefix(start_url: str, same_path_only: bool) -> tuple[str, str]:
    p = urlparse(start_url)
    if not same_path_only:
        return p.netloc.lower(), "/"
    path = p.path or "/"
    if not path.endswith("/"):
        # /docs/intro.html -> /docs/ ; /docs/intro -> /docs/
        path = path.rsplit("/", 1)[0] + "/"
    return p.netloc.lower(), path


def in_scope(url: str, host: str, prefix: str) -> bool:
    p = urlparse(url)
    if p.netloc.lower() != host:
        return False
    if _SKIP_EXT.search(p.path) or _SKIP_PATH.search(p.path):
        return False
    return (p.path or "/").startswith(prefix)


# --------------------------------------------------------------- extraction
def _is_noise(tag: Tag) -> bool:
    if tag.name in {"nav", "header", "footer", "aside", "form", "button", "noscript", "script", "style",
                    "svg", "iframe", "template", "dialog"}:
        return True
    role = (tag.get("role") or "").lower()
    if role in {"navigation", "banner", "contentinfo", "search", "complementary"}:
        return True
    if tag.get("aria-hidden") == "true" and tag.name not in {"span"}:
        return True
    ident = " ".join(tag.get("class") or []) + " " + (tag.get("id") or "")
    return bool(ident.strip() and _NOISE_CLASS.search(ident))


def _pick_main(soup: BeautifulSoup) -> Tag:
    for sel in ("main", "article", "[role=main]", "#content", ".rst-content", ".markdown-body", ".theme-doc-markdown",
                ".md-content", ".content", ".document", ".docs-content", ".prose"):
        node = soup.select_one(sel)
        if node and len(node.get_text(" ", strip=True)) > 200:
            return node
    # Largest content-looking block.
    best, best_len = None, 0
    for div in soup.find_all(["div", "section"]):
        ident = " ".join(div.get("class") or []) + " " + (div.get("id") or "")
        if not _CONTENT_HINT.search(ident):
            continue
        n = len(div.get_text(" ", strip=True))
        if n > best_len:
            best, best_len = div, n
    return best or soup.body or soup


def _text(node: Tag | NavigableString) -> str:
    return re.sub(r"\s+", " ", node.get_text(" ", strip=True) if isinstance(node, Tag) else str(node)).strip()


def _inline(node: Tag) -> str:
    """Inline text keeping `code` spans."""
    parts: list[str] = []
    for child in node.children:
        if isinstance(child, NavigableString):
            parts.append(str(child))
        elif isinstance(child, Tag):
            if child.name == "code":
                t = child.get_text()
                parts.append(f"`{t.strip()}`" if t.strip() else "")
            elif child.name == "br":
                parts.append("\n")
            elif child.name in {"strong", "b"}:
                inner = _inline(child).strip()
                parts.append(f"**{inner}**" if inner else "")
            elif not _is_noise(child):
                parts.append(_inline(child))
    return re.sub(r"[ \t\r\f\v]+", " ", "".join(parts)).strip()


def _code_language(pre: Tag) -> str:
    for el in (pre, pre.find("code"), pre.parent):
        if not isinstance(el, Tag):
            continue
        for cls in el.get("class") or []:
            m = re.match(r"(?:language|lang|highlight)-(\w+)", cls)
            if m:
                return m.group(1)
    return ""


def html_to_text(root: Tag) -> tuple[str, list[str]]:
    """Convert the main content to Markdown-like text. Returns (text, headings)."""
    for tag in list(root.find_all(True)):
        if tag.parent is None:  # already removed with an ancestor
            continue
        if tag.name == "header" and tag.find(["h1", "h2"]):
            tag.unwrap()  # article headers often wrap the page title
        elif _is_noise(tag):
            tag.decompose()
    lines: list[str] = []
    headings: list[str] = []

    def walk(node: Tag, list_depth: int = 0) -> None:
        for child in node.children:
            if isinstance(child, NavigableString):
                t = str(child).strip()
                if t and node.name in {"div", "section", "main", "article", "body"}:
                    lines.append(re.sub(r"\s+", " ", t))
                continue
            if not isinstance(child, Tag):
                continue
            name = child.name
            if name in {"h1", "h2", "h3", "h4", "h5", "h6"}:
                t = _text(child).replace("¶", "").replace("#", "").strip()
                if t:
                    level = int(name[1])
                    lines.append(f"\n{'#' * level} {t}\n")
                    if level <= 3:
                        headings.append(t)
            elif name == "pre":
                code = child.get_text().rstrip()
                if code.strip():
                    lines.append(f"\n```{_code_language(child)}\n{code}\n```\n")
            elif name in {"p", "blockquote", "dd"}:
                t = _inline(child)
                if t:
                    lines.append(("> " if name == "blockquote" else "") + t + "\n")
            elif name in {"ul", "ol"}:
                for i, li in enumerate(child.find_all("li", recursive=False), 1):
                    bullet = f"{i}." if name == "ol" else "-"
                    nested = [c for c in li.children if isinstance(c, Tag) and c.name in {"ul", "ol", "pre"}]
                    for n in nested:
                        n.extract()
                    t = _inline(li)
                    if t:
                        lines.append(f"{'  ' * list_depth}{bullet} {t}")
                    for n in nested:
                        wrapper = BeautifulSoup("<div></div>", "lxml").div
                        wrapper.append(n)
                        walk(wrapper, list_depth + 1)
                lines.append("")
            elif name == "dl":
                for el in child.find_all(["dt", "dd"], recursive=False):
                    t = _inline(el)
                    if t:
                        lines.append(f"**{t}**" if el.name == "dt" else f"  {t}")
                lines.append("")
            elif name == "table":
                rows = []
                for tr in child.find_all("tr"):
                    cells = [_text(c).replace("|", "\\|") for c in tr.find_all(["th", "td"])]
                    if any(cells):
                        rows.append("| " + " | ".join(cells) + " |")
                if rows:
                    cols = rows[0].count("|") - 1
                    rows.insert(1, "|" + " --- |" * max(cols, 1))
                    lines.append("\n" + "\n".join(rows) + "\n")
            elif name in {"img", "video", "picture"}:
                alt = child.get("alt")
                if alt:
                    lines.append(f"[Image: {alt}]")
            else:
                walk(child, list_depth)

    walk(root)
    text = "\n".join(lines)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text, headings


def extract_page(html: str, url: str) -> CrawledPage:
    soup = BeautifulSoup(html, "lxml")
    title = ""
    if soup.title and soup.title.string:
        title = soup.title.string.strip()
    links: list[str] = []
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if href.startswith(("mailto:", "javascript:", "tel:", "#")):
            continue
        n = normalize_url(urljoin(url, href))
        if n:
            links.append(n)
    main = _pick_main(soup)
    h1 = main.find("h1") if isinstance(main, Tag) else None
    if h1 and _text(h1):
        title = _text(h1).replace("¶", "").strip()
    elif title:
        title = re.split(r"\s+[|–—-]\s+", title)[0].strip()
    content, headings = html_to_text(main)
    return CrawledPage(url=url, title=title or url, content=content, headings=headings, links=links)


# ------------------------------------------------------------------ crawler
class Crawler:
    def __init__(
        self,
        start_url: str,
        *,
        max_pages: int = 60,
        same_path_only: bool = True,
        delay: float = 0.25,
        client: httpx.Client | None = None,
        respect_robots: bool = True,
        progress: Callable[[int, int, str], None] | None = None,
    ):
        start = normalize_url(start_url if "://" in start_url else f"https://{start_url}")
        if not start:
            raise CrawlError("Invalid URL")
        self.start = start
        self.max_pages = max(1, max_pages)
        self.host, self.prefix = scope_prefix(start, same_path_only)
        self.delay = delay
        self.client = client or httpx.Client(
            headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"},
            follow_redirects=True,
            timeout=20,
        )
        self.respect_robots = respect_robots
        self.progress = progress or (lambda done, total, url: None)
        self.robots: RobotFileParser | None = None
        self._sitemaps: list[str] = []

    # ---- helpers
    def _get(self, url: str) -> httpx.Response | None:
        try:
            r = self.client.get(url)
        except httpx.HTTPError as exc:
            log.info("fetch failed %s: %s", url, exc)
            return None
        return r

    def _load_robots(self) -> None:
        if not self.respect_robots:
            return
        p = urlparse(self.start)
        r = self._get(f"{p.scheme}://{p.netloc}/robots.txt")
        if r is None or r.status_code >= 400:
            return
        rp = RobotFileParser()
        rp.parse(r.text.splitlines())
        self.robots = rp
        self._sitemaps = [line.split(":", 1)[1].strip() for line in r.text.splitlines()
                          if line.lower().startswith("sitemap:")]

    def _allowed(self, url: str) -> bool:
        return self.robots is None or self.robots.can_fetch(USER_AGENT, url)

    def _sitemap_urls(self) -> list[str]:
        p = urlparse(self.start)
        candidates = self._sitemaps or [f"{p.scheme}://{p.netloc}/sitemap.xml"]
        found: list[str] = []
        seen: set[str] = set()
        queue = list(candidates)
        while queue and len(seen) < 10:
            sm = queue.pop(0)
            if sm in seen:
                continue
            seen.add(sm)
            r = self._get(sm)
            if r is None or r.status_code >= 400 or b"<" not in r.content[:200]:
                continue
            try:
                root = ET.fromstring(r.content)
            except ET.ParseError:
                continue
            for loc in root.iter():
                if not loc.tag.endswith("loc") or not loc.text:
                    continue
                u = loc.text.strip()
                if u.endswith(".xml"):
                    queue.append(u)
                else:
                    n = normalize_url(u)
                    if n and in_scope(n, self.host, self.prefix):
                        found.append(n)
        return found

    # ---- main
    def crawl(self) -> CrawlResult:
        self._load_robots()
        queue: deque[str] = deque([self.start])
        seen: set[str] = {self.start}
        pages: list[CrawledPage] = []
        hashes: set[str] = set()
        visited = skipped = 0
        warnings: list[str] = []
        sitemap_added = False
        thin_pages = 0

        while queue and len(pages) < self.max_pages:
            url = queue.popleft()
            if not self._allowed(url):
                skipped += 1
                continue
            r = self._get(url)
            visited += 1
            if r is None or r.status_code >= 400:
                skipped += 1
                if url == self.start:
                    code = r.status_code if r is not None else "network error"
                    raise CrawlError(f"Could not open the start page ({code})")
                continue
            ctype = r.headers.get("content-type", "")
            if "html" not in ctype and "xml" not in ctype:
                skipped += 1
                continue
            final = normalize_url(str(r.url))
            if final != url and final in seen and url != self.start:
                skipped += 1
                continue
            seen.add(final)
            page = extract_page(r.text, final)

            for link in page.links:
                if link not in seen and in_scope(link, self.host, self.prefix):
                    seen.add(link)
                    queue.append(link)

            digest = hashlib.sha1(page.content.encode()).hexdigest()
            if page.word_count < 25:
                thin_pages += 1
                skipped += 1
            elif digest in hashes:
                skipped += 1
            else:
                hashes.add(digest)
                pages.append(page)
                self.progress(len(pages), self.max_pages, final)

            if not queue and not sitemap_added and len(pages) < self.max_pages:
                sitemap_added = True
                for u in self._sitemap_urls():
                    if u not in seen:
                        seen.add(u)
                        queue.append(u)
            if self.delay:
                time.sleep(self.delay)

        if not pages:
            if thin_pages:
                raise CrawlError(
                    "The pages contain almost no text. The site is probably rendered with JavaScript; "
                    "try a different documentation URL (for example the GitHub README or a static docs mirror)."
                )
            raise CrawlError("No readable documentation pages were found at this URL")
        if thin_pages > len(pages):
            warnings.append(f"{thin_pages} page(s) had almost no text (JavaScript-rendered?) and were skipped.")
        if queue and len(pages) >= self.max_pages:
            warnings.append(f"Stopped at the page limit ({self.max_pages}); {len(queue)} more page(s) were found.")
        return CrawlResult(pages=pages, visited=visited, skipped=skipped, warnings=warnings)
