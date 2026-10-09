"""Extra tests for fetcher — proxies, session state, edge cases."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from tendem_scraper.core import fetcher as fetcher_mod


# ----------------------------------------------------------------- ProxyPool
def test_proxy_pool_empty_returns_none():
    pool = fetcher_mod.ProxyPool()
    assert pool.next() is None
    assert bool(pool) is False


def test_proxy_pool_round_robin_cycles():
    pool = fetcher_mod.ProxyPool(["a", "b", "c"])
    assert pool.next() == "a"
    assert pool.next() == "b"
    assert pool.next() == "c"
    assert pool.next() == "a"


def test_proxy_pool_ignores_empty_strings():
    pool = fetcher_mod.ProxyPool(["", "real", None])  # type: ignore[list-item]
    assert pool.next() == "real"


# ----------------------------------------------------------------- Fetcher init
def test_fetcher_init_default_mode():
    f = fetcher_mod.Fetcher()
    try:
        assert f.mode == "auto"
        assert f.method == "static"
        assert f.scroll is False
        assert f.infinite is False
    finally:
        f.close()


def test_fetcher_init_with_proxy_sets_pool():
    f = fetcher_mod.Fetcher(proxy="http://user:pass@host:1234")
    try:
        assert f.proxies is not None
        assert f.proxies.next() == "http://user:pass@host:1234"
    finally:
        f.close()


def test_fetcher_init_with_proxy_pool():
    f = fetcher_mod.Fetcher(proxy_pool=["http://p1:1", "http://p2:2"])
    try:
        assert f.proxies.next() == "http://p1:1"
        assert f.proxies.next() == "http://p2:2"
    finally:
        f.close()


def test_fetcher_close_is_idempotent():
    f = fetcher_mod.Fetcher()
    f.close()
    f.close()  # should not raise


# ----------------------------------------------------------------- local file
def test_fetcher_reads_local_html(tmp_path: Path):
    p = tmp_path / "page.html"
    p.write_text("<html><body><p>hello</p></body></html>", encoding="utf-8")

    f = fetcher_mod.Fetcher()
    try:
        html, final, method = f.get(str(p))
    finally:
        f.close()

    assert method == "local-file"
    assert "hello" in html
    assert final.startswith("file://")


# ----------------------------------------------------------------- _blocked hints
def test_blocked_detects_verify_you_are_human():
    html = "<html><head><title>Verify you are human</title></head></html>"
    assert fetcher_mod._blocked(html) is True


def test_blocked_detects_pardon_our_interruption():
    html = "<html><body>Pardon our interruption</body></html>"
    assert fetcher_mod._blocked(html) is True


def test_blocked_detects_request_blocked():
    html = "<html><body>Your request blocked</body></html>"
    assert fetcher_mod._blocked(html) is True


# ----------------------------------------------------------------- _thin edge cases
def test_thin_empty_string_is_thin():
    assert fetcher_mod._thin("") is True


def test_thin_short_html_is_thin():
    assert fetcher_mod._thin("<html><body>hi</body></html>") is True


def test_thin_rich_page_not_thin():
    html = "<html><body>" + "".join(
        f'<a href="/{i}">link {i}</a> <p>paragraph with a lot of text here {i}</p>'
        for i in range(10)
    ) + "</body></html>"
    assert fetcher_mod._thin(html) is False


# ----------------------------------------------------------------- robots cache
def test_robots_cache_is_module_level():
    """The robots cache exists as a module-level dict."""
    assert isinstance(fetcher_mod._rp_cache, dict)


def test_robots_for_non_http_scheme_returns_true():
    assert fetcher_mod.robots_allows("ftp://example.com/file") is True
    assert fetcher_mod.robots_allows("file:///local.html") is True