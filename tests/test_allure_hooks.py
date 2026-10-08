"""Tests for allure_hooks — step, attach_json, attach_text, attach_csv, attach_html."""
from __future__ import annotations

from tendem_scraper.core import allure_hooks


def test_allure_step_when_allure_unavailable():
    """A step context manager works even without allure installed."""
    with allure_hooks.allure_step("test step"):
        result = 1 + 1
    assert result == 2


def test_attach_json_noop_when_unavailable():
    """attach_json doesn't raise when allure isn't installed."""
    # Should not raise
    allure_hooks.attach_json("data", {"a": 1})


def test_attach_text_noop_when_unavailable():
    allure_hooks.attach_text("name", "some text")


def test_attach_csv_noop_when_unavailable():
    allure_hooks.attach_csv("data.csv", "a,b\n1,2")


def test_attach_html_noop_when_unavailable():
    allure_hooks.attach_html("page.html", "<html></html>")


def test_allure_step_nested():
    """Nested steps work."""
    with allure_hooks.allure_step("outer"):
        with allure_hooks.allure_step("inner"):
            x = 42
    assert x == 42


def test_attach_json_with_various_payloads():
    """attach_json handles dicts, lists, and nested structures."""
    allure_hooks.attach_json("dict", {"key": "value"})
    allure_hooks.attach_json("list", [1, 2, 3])
    allure_hooks.attach_json("nested", {"a": {"b": [1, 2]}})


def test_allure_hooks_has_flag_attribute():
    """The _HAS flag exists to detect whether allure is available."""
    assert hasattr(allure_hooks, "_HAS")
    assert isinstance(allure_hooks._HAS, bool)