"""Extra tests for llm — error paths and edge cases."""
from __future__ import annotations

import sys
import types
from unittest.mock import MagicMock

from tendem_scraper.config import settings
from tendem_scraper.core import llm


def test_llm_skips_when_no_api_key(monkeypatch):
    """No API key → returns []."""
    monkeypatch.setattr(settings, "openrouter_api_key", None, raising=False)
    assert llm.extract_items_with_llm("<html></html>", "https://x/") == []


def test_llm_skips_when_httpx_missing(monkeypatch):
    """httpx not installed → returns []."""
    monkeypatch.setattr(settings, "openrouter_api_key", "fake", raising=False)

    import builtins
    real_import = builtins.__import__

    def fake_import(name, *a, **k):
        if name == "httpx":
            raise ImportError("simulated")
        return real_import(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    assert llm.extract_items_with_llm("<html></html>", "https://x/") == []


def test_llm_returns_empty_on_http_error(monkeypatch):
    """HTTP error → returns []."""
    monkeypatch.setattr(settings, "openrouter_api_key", "fake", raising=False)
    monkeypatch.setattr(settings, "openrouter_model", "test", raising=False)

    class FailingClient:
        def __init__(self, *_, **__): pass
        def __enter__(self): return self
        def __exit__(self, *_, **__): pass
        def post(self, *_, **__):
            raise RuntimeError("connection failed")

    fake_httpx = types.ModuleType("httpx")
    fake_httpx.Client = FailingClient
    monkeypatch.setitem(sys.modules, "httpx", fake_httpx)

    assert llm.extract_items_with_llm("<html></html>", "https://x/") == []


def test_llm_returns_empty_on_4xx(monkeypatch):
    """4xx response → returns []."""
    monkeypatch.setattr(settings, "openrouter_api_key", "fake", raising=False)
    monkeypatch.setattr(settings, "openrouter_model", "test", raising=False)

    resp = MagicMock()
    resp.status_code = 400
    resp.text = "bad request"

    class Client:
        def __init__(self, *_, **__): pass
        def __enter__(self): return self
        def __exit__(self, *_, **__): pass
        def post(self, *_, **__): return resp

    fake_httpx = types.ModuleType("httpx")
    fake_httpx.Client = Client
    monkeypatch.setitem(sys.modules, "httpx", fake_httpx)

    assert llm.extract_items_with_llm("<html></html>", "https://x/") == []


def test_llm_returns_empty_on_invalid_json(monkeypatch):
    """Response with invalid JSON → returns []."""
    monkeypatch.setattr(settings, "openrouter_api_key", "fake", raising=False)
    monkeypatch.setattr(settings, "openrouter_model", "test", raising=False)

    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {
        "candidates": [{"content": {"parts": [{"text": "not json at all"}]}}]
    }

    class Client:
        def __init__(self, *_, **__): pass
        def __enter__(self): return self
        def __exit__(self, *_, **__): pass
        def post(self, *_, **__): return resp

    fake_httpx = types.ModuleType("httpx")
    fake_httpx.Client = Client
    monkeypatch.setitem(sys.modules, "httpx", fake_httpx)

    assert llm.extract_items_with_llm("<html></html>", "https://x/") == []


def test_llm_returns_empty_on_empty_content(monkeypatch):
    """Empty content in response → returns []."""
    monkeypatch.setattr(settings, "openrouter_api_key", "fake", raising=False)
    monkeypatch.setattr(settings, "openrouter_model", "test", raising=False)

    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {
        "candidates": [{"content": {"parts": [{"text": ""}]}}]
    }

    class Client:
        def __init__(self, *_, **__): pass
        def __enter__(self): return self
        def __exit__(self, *_, **__): pass
        def post(self, *_, **__): return resp

    fake_httpx = types.ModuleType("httpx")
    fake_httpx.Client = Client
    monkeypatch.setitem(sys.modules, "httpx", fake_httpx)

    assert llm.extract_items_with_llm("<html></html>", "https://x/") == []


def test_llm_extracts_from_json_fences(monkeypatch):
    """Response with ```json fences → parsed."""
    monkeypatch.setattr(settings, "openrouter_api_key", "fake", raising=False)
    monkeypatch.setattr(settings, "openrouter_model", "test", raising=False)

    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {
        "candidates": [{"content": {"parts": [{
            "text": '```json\n[{"title":"A"}]\n```'
        }]}}]
    }

    class Client:
        def __init__(self, *_, **__): pass
        def __enter__(self): return self
        def __exit__(self, *_, **__): pass
        def post(self, *_, **__): return resp

    fake_httpx = types.ModuleType("httpx")
    fake_httpx.Client = Client
    monkeypatch.setitem(sys.modules, "httpx", fake_httpx)

    out = llm.extract_items_with_llm("<html></html>", "https://x/")
    assert out == [{"title": "A"}]


def test_llm_handles_dict_with_items_key(monkeypatch):
    """If Gemini returns {"items": [...]}, we extract the items."""
    monkeypatch.setattr(settings, "openrouter_api_key", "fake", raising=False)
    monkeypatch.setattr(settings, "openrouter_model", "test", raising=False)

    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {
        "candidates": [{"content": {"parts": [{
            "text": '{"items": [{"title": "A"}]}'
        }]}}]
    }

    class Client:
        def __init__(self, *_, **__): pass
        def __enter__(self): return self
        def __exit__(self, *_, **__): pass
        def post(self, *_, **__): return resp

    fake_httpx = types.ModuleType("httpx")
    fake_httpx.Client = Client
    monkeypatch.setitem(sys.modules, "httpx", fake_httpx)

    out = llm.extract_items_with_llm("<html></html>", "https://x/")
    assert out == [{"title": "A"}]


def test_llm_handles_non_list_non_dict(monkeypatch):
    """If Gemini returns a string or number, we return []."""
    monkeypatch.setattr(settings, "openrouter_api_key", "fake", raising=False)
    monkeypatch.setattr(settings, "openrouter_model", "test", raising=False)

    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {
        "candidates": [{"content": {"parts": [{"text": '"just a string"'}]}}]
    }

    class Client:
        def __init__(self, *_, **__): pass
        def __enter__(self): return self
        def __exit__(self, *_, **__): pass
        def post(self, *_, **__): return resp

    fake_httpx = types.ModuleType("httpx")
    fake_httpx.Client = Client
    monkeypatch.setitem(sys.modules, "httpx", fake_httpx)

    assert llm.extract_items_with_llm("<html></html>", "https://x/") == []