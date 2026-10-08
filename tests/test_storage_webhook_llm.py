"""Tests for storage, webhook, llm, proxy, and concurrency helpers."""
from unittest.mock import MagicMock

from tendem_scraper.config import settings
from tendem_scraper.core import storage, webhook
from tendem_scraper.core.concurrency import map_concurrent
from tendem_scraper.core.llm import extract_items_with_llm
from tendem_scraper.core.proxy import ProxyPool

# ---------------------------------------------------------------- proxy

def test_proxy_pool_empty_returns_none():
    p = ProxyPool()
    assert p.next() is None
    assert not p


def test_proxy_pool_round_robin():
    p = ProxyPool(["a", "b", "c"])
    assert p.next() == "a"
    assert p.next() == "b"
    assert p.next() == "c"
    assert p.next() == "a"


def test_proxy_pool_ignores_falsy():
    p = ProxyPool(["", None, "x"])  # type: ignore[list-item]
    assert p.next() == "x"
    assert p.next() == "x"


# ---------------------------------------------------------------- concurrency

def test_map_concurrent_sequential():
    results = map_concurrent(lambda x: x * 2, [1, 2, 3], workers=1)
    assert [(it, r) for it, r, e in results] == [(1, 2), (2, 4), (3, 6)]
    assert all(e is None for _, _, e in results)


def test_map_concurrent_parallel():
    results = map_concurrent(lambda x: x + 1, [1, 2, 3, 4], workers=4)
    assert sorted((it, r) for it, r, _ in results) == [(1, 2), (2, 3), (3, 4), (4, 5)]


def test_map_concurrent_captures_exception():
    def boom(x):
        if x == 2:
            raise ValueError("bad")
        return x
    results = map_concurrent(boom, [1, 2, 3], workers=1)
    by_it = {it: (r, e) for it, r, e in results}
    assert by_it[1][0] == 1 and by_it[1][1] is None
    assert by_it[2][0] is None and isinstance(by_it[2][1], ValueError)
    assert by_it[3][0] == 3


# ---------------------------------------------------------------- webhook

def test_webhook_noop_when_not_configured(monkeypatch):
    monkeypatch.setattr(settings, "webhook_url", None, raising=False)
    # Should not raise, should not make a request
    webhook.notify("hello")


def test_webhook_posts_when_configured(monkeypatch):
    monkeypatch.setattr(settings, "webhook_url", "https://hooks.example/123", raising=False)
    mock_post = MagicMock()
    mock_post.return_value.raise_for_status = MagicMock()
    monkeypatch.setattr(webhook.requests, "post", mock_post)

    webhook.notify("ping")
    assert mock_post.called
    # first positional arg is the URL
    assert mock_post.call_args[0][0] == "https://hooks.example/123"


def test_webhook_discord_format(monkeypatch):
    monkeypatch.setattr(settings, "webhook_url",
                        "https://discord.com/api/webhooks/abc/def", raising=False)
    mock_post = MagicMock()
    mock_post.return_value.raise_for_status = MagicMock()
    monkeypatch.setattr(webhook.requests, "post", mock_post)

    webhook.notify("hi")
    body = mock_post.call_args[1]["data"]
    assert "content" in body


def test_webhook_swallows_errors(monkeypatch):
    monkeypatch.setattr(settings, "webhook_url", "https://hooks.example/123", raising=False)

    def boom(*_a, **_kw):
        raise RuntimeError("nope")
    monkeypatch.setattr(webhook.requests, "post", boom)
    # Should not raise
    webhook.notify("hello")


# ---------------------------------------------------------------- storage

def test_storage_noop_when_no_bucket(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "s3_bucket", None, raising=False)
    assert storage.upload_dir(tmp_path) is None


def test_storage_returns_none_if_boto3_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "s3_bucket", "my-bucket", raising=False)

    # Simulate boto3 not installed
    import builtins
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "boto3" or name.startswith("botocore"):
            raise ImportError("simulated missing boto3")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    # Create a dummy file to (potentially) upload
    (tmp_path / "x.txt").write_text("hi")
    assert storage.upload_dir(tmp_path) is None


def test_storage_uploads_when_boto3_available(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "s3_bucket", "my-bucket", raising=False)
    monkeypatch.setattr(settings, "s3_prefix", "scrapes/", raising=False)
    monkeypatch.setattr(settings, "aws_region", "us-east-1", raising=False)

    # Fake boto3 client
    fake_client = MagicMock()
    fake_client.upload_file = MagicMock()
    fake_s3 = MagicMock(return_value=fake_client)

    import sys
    import types

    fake_boto3 = types.ModuleType("boto3")
    fake_boto3.client = fake_s3  # type: ignore[attr-defined]

    fake_botocore = types.ModuleType("botocore")
    fake_config = types.ModuleType("botocore.config")

    class _Cfg:
        def __init__(self, *_, **__):
            pass

    fake_config.Config = _Cfg  # type: ignore[attr-defined]
    fake_botocore.config = fake_config  # type: ignore[attr-defined]

    monkeypatch.setitem(sys.modules, "boto3", fake_boto3)
    monkeypatch.setitem(sys.modules, "botocore", fake_botocore)
    monkeypatch.setitem(sys.modules, "botocore.config", fake_config)

    (tmp_path / "items.csv").write_text("a,b\n1,2")
    uri = storage.upload_dir(tmp_path)
    assert uri == "s3://my-bucket/scrapes/" + tmp_path.name + "/"
    assert fake_client.upload_file.call_count >= 1


# ---------------------------------------------------------------- llm

def test_llm_disabled_without_key(monkeypatch):
    monkeypatch.setattr(settings, "openrouter_api_key", None, raising=False)
    assert extract_items_with_llm("<html></html>", "https://x/") == []


def test_llm_returns_empty_when_httpx_missing(monkeypatch):
    monkeypatch.setattr(settings, "openrouter_api_key", "fake-key", raising=False)

    import builtins
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "httpx":
            raise ImportError("simulated missing httpx")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    assert extract_items_with_llm("<html></html>", "https://x/") == []


def test_llm_happy_path(monkeypatch):
    """LLM extraction works with Google Gemini response format."""
    monkeypatch.setattr(settings, "openrouter_api_key", "fake-key", raising=False)
    monkeypatch.setattr(settings, "openrouter_model", "gemini-3.5-flash", raising=False)

    fake_resp = MagicMock()
    fake_resp.status_code = 200
    fake_resp.raise_for_status = MagicMock()
    fake_resp.json.return_value = {
        "candidates": [{
            "content": {
                "parts": [{
                    "text": '[{"title":"A","price":"$1","link":"","image":"","text":""}]'
                }]
            }
        }]
    }

    class FakeClient:
        def __init__(self, *_, **__):
            pass
        def __enter__(self):
            return self
        def __exit__(self, *_, **__):
            pass
        def post(self, *_, **__):
            return fake_resp

    import sys
    import types
    fake_httpx = types.ModuleType("httpx")
    fake_httpx.Client = FakeClient  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "httpx", fake_httpx)

    out = extract_items_with_llm("<html></html>", "https://x/")
    assert out == [{"title": "A", "price": "$1", "link": "", "image": "", "text": ""}]