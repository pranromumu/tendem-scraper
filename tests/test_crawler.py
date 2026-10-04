"""Tests for the whole-site crawler."""
from tendem_scraper.core.crawler import _norm, crawl_urls


def test_norm_strips_fragment():
    assert _norm("https://x/a#frag") == "https://x/a"


def test_norm_strips_trailing_slash():
    assert _norm("https://x/a/") == "https://x/a"
    assert _norm("https://x/a") == "https://x/a"


def test_norm_keeps_query():
    assert _norm("https://x/a?p=1") == "https://x/a?p=1"


class _FakeFetcher:
    """Returns a canned response per URL, and records calls."""
    def __init__(self, mapping):
        self.mapping = mapping
        self.calls = []

    def get(self, url):
        self.calls.append(url)
        if url not in self.mapping:
            from tendem_scraper.core.fetcher import FetchError
            raise FetchError(f"404 {url}")
        return self.mapping[url], url, "test"


SEED = "https://example.com/"
HTML_HOME = """
<html><body>
  <a href="/a">A</a>
  <a href="/b">B</a>
  <a href="https://external.com/x">External</a>
  <a href="#section">Fragment</a>
  <a href="mailto:x@y.com">Mail</a>
</body></html>
"""
HTML_A = "<html><body><a href='/c'>C</a></body></html>"
HTML_B = "<html><body>no links</body></html>"
HTML_C = "<html><body>leaf</body></html>"


def test_crawl_follows_internal_links_only():
    f = _FakeFetcher({
        "https://example.com": HTML_HOME,
        "https://example.com/a": HTML_A,
        "https://example.com/b": HTML_B,
        "https://example.com/c": HTML_C,
    })
    pages = crawl_urls(SEED, f, max_pages=10, same_host_only=True, respect_robots=False)
    urls = [u for u, _ in pages]
    assert "https://example.com" in urls
    assert "https://example.com/a" in urls
    assert "https://example.com/b" in urls
    assert "https://example.com/c" in urls
    # external not followed
    assert not any("external.com" in u for u in urls)


def test_crawl_respects_max_pages():
    f = _FakeFetcher({
        "https://example.com": HTML_HOME,
        "https://example.com/a": HTML_A,
        "https://example.com/b": HTML_B,
        "https://example.com/c": HTML_C,
    })
    pages = crawl_urls(SEED, f, max_pages=2, same_host_only=True, respect_robots=False)
    assert len(pages) == 2


def test_crawl_handles_fetch_error():
    class Broken:
        def get(self, url):
            from tendem_scraper.core.fetcher import FetchError
            raise FetchError("boom")

    pages = crawl_urls(SEED, Broken(), max_pages=5, respect_robots=False)
    assert pages == []