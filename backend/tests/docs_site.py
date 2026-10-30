"""A small fake documentation site used by crawler and learning tests."""

from __future__ import annotations

import httpx

LAYOUT = """<!doctype html><html><head><title>{title} | MiniLib Docs</title></head><body>
<header class="site-header"><a href="/">MiniLib</a> <nav><a href="/blog/">Blog</a></nav></header>
<div class="cookie-banner">We use cookies. <button>OK</button></div>
<aside class="sidebar"><nav>
  <a href="/docs/">Introduction</a>
  <a href="/docs/install.html">Installation</a>
  <a href="/docs/quickstart">Quickstart</a>
  <a href="/docs/concepts/models">Models</a>
  <a href="/docs/concepts/models#fields">Fields (anchor)</a>
  <a href="/docs/logo.png">Logo</a>
  <a href="https://other.example.com/docs/">External</a>
  <a href="/pricing">Pricing</a>
</nav></aside>
<main><article>{body}</article>
<div class="pagination-nav"><a href="/docs/next">Next page</a></div></main>
<footer>Copyright MiniLib</footer></body></html>"""

PAGES = {
    "/docs/": ("Introduction", """
<h1>Introduction to MiniLib</h1>
<p>MiniLib is a tiny library for <strong>validating data</strong> in Python. It turns plain dictionaries into typed
objects and reports clear errors when the data is wrong.</p>
<h2>Why MiniLib?</h2>
<ul><li>Simple: one class to learn.</li><li>Fast: written with performance in mind.</li>
<li>Friendly errors that tell you exactly which field failed.</li></ul>
<p>Continue with the <a href="install.html">installation guide</a>.</p>"""),
    "/docs/install.html": ("Installation", """
<h1>Installation</h1><p>MiniLib requires Python 3.10 or newer. Install it from PyPI with pip.</p>
<div class="highlight-bash"><pre><code class="language-bash">pip install minilib</code></pre></div>
<p>To check that the installation worked, import the package and print its version number.</p>
<pre><code class="language-python">import minilib
print(minilib.__version__)</code></pre>
<table><tr><th>Python</th><th>Supported</th></tr><tr><td>3.10</td><td>yes</td></tr><tr><td>3.9</td><td>no</td></tr></table>"""),
    "/docs/quickstart": ("Quickstart", """
<h1>Quickstart</h1><p>Define a model by subclassing <code>Model</code> and declaring typed fields.
Then create an instance from a dictionary. MiniLib converts and validates every field automatically.</p>
<pre><code class="language-python">from minilib import Model

class User(Model):
    name: str
    age: int

user = User.parse({"name": "Sara", "age": "31"})
print(user.age + 1)  # 32</code></pre>
<p>If a field is missing or has the wrong type, <code>parse</code> raises a <code>ValidationError</code>
listing every problem.</p>"""),
    "/docs/concepts/models": ("Models", """
<h1>Models</h1><p>A model is a class that describes the shape of your data. Each annotated attribute
becomes a field. Fields can have default values and can be optional.</p>
<h2 id="fields">Fields</h2><p>Fields are declared with Python type hints. Supported types include
str, int, float, bool, list and nested models.</p>
<h2>Default values</h2><p>Assign a value in the class body to give a field a default. Fields with defaults
are not required when parsing.</p>"""),
    "/docs/next": ("Validation errors", """
<h1>Validation errors</h1><p>A ValidationError contains a list of errors. Each error has the field path,
the message and the invalid input value. Catch the exception to show friendly messages to your users.</p>
<pre><code>try:
    User.parse({"age": "abc"})
except ValidationError as e:
    print(e.errors())</code></pre>"""),
    "/docs/hidden": ("Hidden page from sitemap", """
<h1>Advanced configuration</h1><p>This page is only listed in the sitemap. It explains configuration
options such as strict mode, which disables automatic type conversion, and extra fields handling.</p>"""),
    "/docs/private/secret": ("Secret", "<h1>Secret</h1><p>Should never be fetched because robots.txt forbids it."
                             " Lorem ipsum dolor sit amet consectetur adipiscing elit sed do eiusmod tempor.</p>"),
}

ROBOTS = "User-agent: *\nDisallow: /docs/private/\nSitemap: https://minilib.dev/sitemap.xml\n"
SITEMAP = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
<url><loc>https://minilib.dev/docs/</loc></url>
<url><loc>https://minilib.dev/docs/hidden</loc></url>
<url><loc>https://minilib.dev/docs/private/secret</loc></url>
<url><loc>https://minilib.dev/blog/post</loc></url>
</urlset>"""


def handler(request: httpx.Request) -> httpx.Response:
    path = request.url.path
    if path == "/robots.txt":
        return httpx.Response(200, text=ROBOTS)
    if path == "/sitemap.xml":
        return httpx.Response(200, text=SITEMAP, headers={"content-type": "application/xml"})
    if path == "/docs/private/secret":
        raise AssertionError("robots.txt was not respected")
    if path == "/docs/index.html":
        path = "/docs/"
    if path in PAGES:
        title, body = PAGES[path]
        return httpx.Response(200, text=LAYOUT.format(title=title, body=body),
                              headers={"content-type": "text/html; charset=utf-8"})
    return httpx.Response(404, text="not found")


def make_client() -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler), base_url="https://minilib.dev",
                        follow_redirects=True)
