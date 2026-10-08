"""Tests for the main CLI — parser, helpers, and argument routing."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from tendem_scraper import cli


# ----------------------------------------------------------------- parser
def test_parser_has_expected_arguments():
    """The parser exposes all documented flags."""
    ap = cli._build_parser()
    actions = {a.dest for a in ap._actions}
    expected = {
        "url", "max_pages", "crawl", "crawl_max", "concurrency",
        "item_selector", "preset", "page_object", "scroll", "infinite",
        "dedupe", "validate", "check_links", "external", "ignore_robots",
        "proxy", "save_session", "use_session", "list_sessions",
        "format", "sink", "sheet_id", "sheet_name", "sheet_mode",
        "outdir", "resume", "s3", "webhook", "open", "json_logs",
        "codegen", "llm",
    }
    missing = expected - actions
    assert not missing, f"Missing CLI arguments: {missing}"


def test_parser_url_is_positional():
    ap = cli._build_parser()
    args = ap.parse_args(["https://example.com"])
    assert args.url == "https://example.com"


def test_parser_llm_flag_defaults_false():
    ap = cli._build_parser()
    args = ap.parse_args(["https://example.com"])
    assert args.llm is False


def test_parser_llm_flag_enabled():
    ap = cli._build_parser()
    args = ap.parse_args(["https://example.com", "--llm"])
    assert args.llm is True


def test_parser_dedupe_flag():
    ap = cli._build_parser()
    args = ap.parse_args(["https://example.com", "--dedupe"])
    assert args.dedupe is True


def test_parser_multiple_sinks():
    ap = cli._build_parser()
    args = ap.parse_args([
        "https://example.com",
        "--sink", "gsheet",
    ])
    assert "gsheet" in args.sink


def test_parser_mutually_exclusive_modes():
    ap = cli._build_parser()
    with pytest.raises(SystemExit):
        ap.parse_args(["https://example.com", "--static", "--render"])


def test_parser_crawl_defaults():
    ap = cli._build_parser()
    args = ap.parse_args(["https://example.com"])
    assert args.crawl is False
    assert args.crawl_max > 0


# ----------------------------------------------------------------- resolve page kwargs
def test_resolve_page_kwargs_default():
    """Without --preset or --page-object, uses listing page and no preset."""
    ap = cli._build_parser()
    args = ap.parse_args(["https://example.com"])
    preset_name, preset, resolved = cli._resolve_page_kwargs(args)
    assert preset_name == ""
    assert preset is None
    assert "page_cls" in resolved
    assert "page_kwargs" in resolved


def test_resolve_page_kwargs_with_preset():
    """--preset shopify loads the shopify preset."""
    ap = cli._build_parser()
    args = ap.parse_args(["https://example.com", "--preset", "shopify"])
    preset_name, preset, _resolved = cli._resolve_page_kwargs(args)
    assert preset_name == "shopify"
    assert preset is not None


def test_resolve_page_kwargs_with_page_object():
    """--page-object books uses the BooksToScrapePage."""
    ap = cli._build_parser()
    args = ap.parse_args(["https://example.com", "--page-object", "books"])
    _preset_name, _preset, resolved = cli._resolve_page_kwargs(args)
    from tendem_scraper.pages.books_toscrape import BooksToScrapePage
    assert resolved["page_cls"] is BooksToScrapePage


def test_resolve_page_kwargs_with_item_selector():
    ap = cli._build_parser()
    args = ap.parse_args([
        "https://example.com",
        "--item-selector", ".product-card",
    ])
    _, _, resolved = cli._resolve_page_kwargs(args)
    assert resolved["page_kwargs"]["item_selector"] == ".product-card"


# ----------------------------------------------------------------- check links
def test_check_links_ok(monkeypatch):
    """A 200 response is reported as OK."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = "ok"

    def fake_head(url, **kwargs):
        return mock_resp

    monkeypatch.setattr(cli.requests, "head", fake_head)
    result = cli._check_links(["https://example.com"])
    assert result["https://example.com"][0] == "OK"


def test_check_links_broken(monkeypatch):
    """A 404 response is reported as BROKEN."""
    mock_head = MagicMock()
    mock_head.status_code = 404
    mock_get = MagicMock()
    mock_get.status_code = 404
    mock_get.close = MagicMock()

    monkeypatch.setattr(cli.requests, "head", lambda *a, **k: mock_head)
    monkeypatch.setattr(cli.requests, "get", lambda *a, **k: mock_get)
    result = cli._check_links(["https://example.com/404"])
    assert result["https://example.com/404"][0] == "BROKEN"


def test_check_links_restricted(monkeypatch):
    """A 403 response is reported as RESTRICTED."""
    mock_head = MagicMock()
    mock_head.status_code = 403
    mock_get = MagicMock()
    mock_get.status_code = 403
    mock_get.close = MagicMock()

    monkeypatch.setattr(cli.requests, "head", lambda *a, **k: mock_head)
    monkeypatch.setattr(cli.requests, "get", lambda *a, **k: mock_get)
    result = cli._check_links(["https://example.com/private"])
    assert result["https://example.com/private"][0] == "RESTRICTED"


def test_check_links_error(monkeypatch):
    """A network error is reported as ERROR."""
    def boom(*a, **k):
        raise cli.requests.RequestException("timeout")

    monkeypatch.setattr(cli.requests, "head", boom)
    result = cli._check_links(["https://broken.test"])
    assert result["https://broken.test"][0] == "ERROR"


# ----------------------------------------------------------------- codegen
def test_codegen_skeleton_uses_page_selector():
    """Codegen uses the page's selector if available."""
    page = MagicMock()
    page.selector = ".product-card"
    skeleton = cli._codegen_skeleton(page)
    assert ".product-card" in skeleton
    assert "class MySiteListing" in skeleton


def test_codegen_skeleton_defaults_when_no_selector():
    page = MagicMock()
    page.selector = ""
    skeleton = cli._codegen_skeleton(page)
    assert "your-card-selector" in skeleton


# ----------------------------------------------------------------- main (basic routing)
def test_main_list_sessions_empty(monkeypatch, capsys):
    """--list-sessions with no sessions prints a warning."""
    monkeypatch.setattr(cli.session_mod, "list_sessions", lambda: [])
    rc = cli.main(["URL", "--list-sessions"])
    assert rc == 0


def test_main_list_sessions_with_data(monkeypatch):
    monkeypatch.setattr(cli.session_mod, "list_sessions", lambda: ["a", "b"])
    rc = cli.main(["URL", "--list-sessions"])
    assert rc == 0