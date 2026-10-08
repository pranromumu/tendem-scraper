"""Tests for the fetcher — robots check, block detection, thin page detection."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from tendem_scraper.core import fetcher


# ----------------------------------------------------------------- module helpers
def test_block_hints_is_tuple():
    assert isinstance(fetcher.BLOCK_HINTS, tuple)
    assert "captcha" in fetcher.BLOCK_HINTS


def test_ua_is_string():
    assert isinstance(fetcher.UA, str)
    assert "Mozilla" in fetcher.UA


# ----------------------------------------------------------------- _blocked
def test_blocked_detects_captcha_in_title():
    html = "<html><head><title>Captcha Required</title></head><body>hi</body></html>"
    assert fetcher._blocked(html) is True


def test_blocked_detects_access_denied():
    html = "<html><head><title>Access Denied</title></head><body>x</body></html>"
    assert fetcher._blocked(html) is True


def test_blocked_detects_403_forbidden_in_body():
    html = "<html><head><title>Hi</title></head><body>403 forbidden</body></html>"
    assert fetcher._blocked(html) is True


def test_blocked_returns_false_for_clean_page():
    html = "<html><head><title>Welcome</title></head><body>Products</body></html>"
    assert fetcher._blocked(html) is False


# ----------------------------------------------------------------- _thin
def test_thin_detects_empty_page():
    html = "<html><body>hi</body></html>"
    assert fetcher._thin(html) is True


def test_thin_returns_false_for_real_page():
    html = """
    <html><body>
      <a href="/a">A</a>
      <a href="/b">B</a>
      <a href="/c">C</a>
      <a href="/d">D</a>
      <a href="/e">E</a>
      <p>Some meaningful content here that is long enough to pass the check.</p>
      <p>More content to ensure the text length threshold is exceeded clearly.</p>
    </body></html>
    """
    assert fetcher._thin(html) is False


# ----------------------------------------------------------------- robots_allows
def test_robots_allows_non_http_scheme():
    """A non-http URL is always allowed."""
    assert fetcher.robots_allows("file:///local.html") is True


def test_robots_allows_when_no_file(monkeypatch):
    """If robots.txt returns 404, everything is allowed."""
    mock_resp = MagicMock()
    mock_resp.status_code = 404

    # Clear the robots cache so our mock runs
    fetcher._rp_cache.clear()

    import requests
    monkeypatch.setattr(requests, "get", lambda *a, **k: mock_resp)
    assert fetcher.robots_allows("https://test-no-robots.example/path") is True


def test_robots_disallows_path(monkeypatch):
    """A Disallow: / in robots.txt blocks all paths."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = "User-agent: *\nDisallow: /"

    fetcher._rp_cache.clear()

    import requests
    monkeypatch.setattr(requests, "get", lambda *a, **k: mock_resp)
    assert fetcher.robots_allows("https://test-blocked.example/anything") is False


def test_robots_handles_request_error(monkeypatch):
    """A network error fetching robots.txt should not block scraping."""
    fetcher._rp_cache.clear()

    import requests
    def boom(*a, **k):
        raise requests.RequestException("network down")

    monkeypatch.setattr(requests, "get", boom)
    # Should not raise — returns True
    assert fetcher.robots_allows("https://test-error.example/path") is True


# ----------------------------------------------------------------- Fetcher class
def test_fetcher_local_file(tmp_path: Path):
    """A local HTML file is read directly without HTTP."""
    p = tmp_path / "page.html"
    p.write_text("<html><body>hi</body></html>", encoding="utf-8")

    f = fetcher.Fetcher(mode="static")
    try:
        html, final, method = f.get(str(p))
    finally:
        f.close()

    assert method == "local-file"
    assert "hi" in html
    assert final.startswith("file://")


def test_fetcher_init_defaults():
    """Fetcher can be instantiated with no args."""
    f = fetcher.Fetcher()
    assert f.mode == "auto"
    assert f.scroll is False
    assert f.method == "static"
    f.close()


def test_fetcher_init_with_proxy():
    f = fetcher.Fetcher(proxy="http://user:pass@localhost:8080")
    assert f.proxies is not None
    assert f.proxies.next() == "http://user:pass@localhost:8080"
    f.close()


def test_fetcher_close_is_safe():
    """Calling close() multiple times doesn't raise."""
    f = fetcher.Fetcher()
    f.close()
    f.close()