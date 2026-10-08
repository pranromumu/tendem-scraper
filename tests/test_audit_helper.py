"""Tests for the audit helper — verdicts, pricing, next commands."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from tendem_scraper import audit_helper


# ----------------------------------------------------------------- known hard sites
def test_is_known_hard_amazon():
    hard, why = audit_helper._is_known_hard("https://www.amazon.com/dp/B08N5WRWNW")
    assert hard is True
    assert "amazon" in why


def test_is_known_hard_linkedin():
    hard, why = audit_helper._is_known_hard("https://linkedin.com/in/foo")
    assert hard is True
    assert "linkedin" in why


def test_is_known_hard_facebook():
    hard, _ = audit_helper._is_known_hard("https://facebook.com/page")
    assert hard is True


def test_is_known_hard_normal_site():
    hard, why = audit_helper._is_known_hard("https://example-shop.com/products")
    assert hard is False
    assert why == ""


# ----------------------------------------------------------------- verdicts
def _signals(**overrides) -> dict:
    """Build a default signals dict for verdict testing."""
    base = {
        "auto_items": 0,
        "auto_selector": "",
        "fallback_items": 0,
        "fallback_selector": "",
        "preset": "generic",
        "preset_score": 0,
        "has_next": False,
        "has_login": False,
        "has_captcha": False,
    }
    base.update(overrides)
    return base


def test_verdict_decline_when_robots_disallows():
    _emoji, label, reason = audit_helper._verdict(
        _signals(), robots_allowed=False, url="https://example.com"
    )
    assert label == "DECLINE"
    assert "robots" in reason.lower()


def test_verdict_decline_when_captcha():
    _emoji, label, reason = audit_helper._verdict(
        _signals(has_captcha=True),
        robots_allowed=True,
        url="https://example.com",
    )
    assert label == "DECLINE"
    assert "captcha" in reason.lower()


def test_verdict_hard_for_known_antibot_site():
    _emoji, label, reason = audit_helper._verdict(
        _signals(auto_items=50),
        robots_allowed=True,
        url="https://www.amazon.com/s?k=x",
    )
    assert label == "HARD"
    assert "amazon" in reason.lower()


def test_verdict_easy_when_auto_items_found():
    _emoji, label, _ = audit_helper._verdict(
        _signals(auto_items=20), robots_allowed=True, url="https://example.com"
    )
    assert label == "EASY"


def test_verdict_medium_when_fallback_selector_works():
    _emoji, label, reason = audit_helper._verdict(
        _signals(auto_items=0, fallback_items=30, fallback_selector="tr.athing"),
        robots_allowed=True,
        url="https://news.ycombinator.com",
    )
    assert label == "MEDIUM"
    assert "tr.athing" in reason


def test_verdict_hard_when_login_required():
    _emoji, label, reason = audit_helper._verdict(
        _signals(has_login=True),
        robots_allowed=True,
        url="https://portal.example.com",
    )
    assert label == "HARD"
    assert "login" in reason.lower()


def test_verdict_hard_when_nothing_found():
    _emoji, label, _ = audit_helper._verdict(
        _signals(), robots_allowed=True, url="https://example.com"
    )
    assert label == "HARD"


# ----------------------------------------------------------------- pricing
def test_price_easy():
    assert "$60" in audit_helper._price("EASY")


def test_price_medium():
    assert "$120" in audit_helper._price("MEDIUM")


def test_price_hard():
    price = audit_helper._price("HARD")
    assert "250" in price


def test_price_decline_returns_dash():
    assert audit_helper._price("DECLINE") == "—"


# ----------------------------------------------------------------- next command
def test_next_command_easy():
    cmd = audit_helper._next_command(
        "https://example.com", _signals(auto_items=20), "EASY"
    )
    assert "tendem-scrape" in cmd
    assert "--max-pages" in cmd


def test_next_command_medium_with_selector():
    cmd = audit_helper._next_command(
        "https://example.com",
        _signals(auto_items=0, fallback_items=30, fallback_selector="tr.athing"),
        "MEDIUM",
    )
    assert "--item-selector" in cmd
    assert "tr.athing" in cmd


def test_next_command_medium_without_selector():
    cmd = audit_helper._next_command(
        "https://example.com", _signals(auto_items=0, fallback_items=0), "MEDIUM"
    )
    assert "--render" in cmd


def test_next_command_hard_login():
    cmd = audit_helper._next_command(
        "https://example.com", _signals(has_login=True), "HARD"
    )
    assert "--interactive" in cmd
    assert "--save-session" in cmd


def test_next_command_decline():
    cmd = audit_helper._next_command(
        "https://example.com", _signals(), "DECLINE"
    )
    assert "Decline" in cmd or "decline" in cmd


# ----------------------------------------------------------------- helpers
def test_ask_url_accepts_https(monkeypatch):
    monkeypatch.setattr(audit_helper.Prompt, "ask", staticmethod(lambda _: "https://example.com"))
    assert audit_helper._ask_url() == "https://example.com"


def test_ask_url_rejects_non_url(monkeypatch):
    monkeypatch.setattr(audit_helper.Prompt, "ask", staticmethod(lambda _: "not-a-url"))
    with pytest.raises(SystemExit):
        audit_helper._ask_url()


def test_check_robots_disallows(monkeypatch):
    """robots.txt that disallows everything returns (False, ...)."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = "User-agent: *\nDisallow: /"

    import requests
    monkeypatch.setattr(requests, "get", lambda *a, **k: mock_resp)
    allowed, reason = audit_helper._check_robots("https://example.com/private")
    assert allowed is False
    assert "disallows" in reason.lower()


def test_check_robots_no_file(monkeypatch):
    """Missing robots.txt returns (True, ...)."""
    mock_resp = MagicMock()
    mock_resp.status_code = 404

    import requests
    monkeypatch.setattr(requests, "get", lambda *a, **k: mock_resp)
    allowed, reason = audit_helper._check_robots("https://example.com")
    assert allowed is True
    assert "no robots" in reason.lower()