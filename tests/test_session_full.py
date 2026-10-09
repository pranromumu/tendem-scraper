"""Tests for the session module — path sanitization, load, list."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from tendem_scraper.core import session as session_mod


@pytest.fixture
def tmp_session_dir(tmp_path, monkeypatch):
    """Redirect session storage to a temp folder."""
    monkeypatch.setattr(session_mod, "SESSION_DIR", tmp_path)
    return tmp_path


# ----------------------------------------------------------------- session_path
def test_session_path_sanitizes_special_chars(tmp_session_dir):
    """Special characters are stripped from session names."""
    p = session_mod.session_path("my login!!")
    assert p.name == "mylogin.json"
    assert p.parent == tmp_session_dir


def test_session_path_keeps_safe_chars(tmp_session_dir):
    """Dashes, underscores, dots are allowed."""
    p = session_mod.session_path("client-1_test.v2")
    assert p.name == "client-1_test.v2.json"


def test_session_path_rejects_empty_name(tmp_session_dir):
    """An empty result after sanitization raises."""
    with pytest.raises(ValueError):
        session_mod.session_path("!!!")


def test_session_path_keeps_alphanumeric_unicode(tmp_session_dir):
    """Unicode letters that are alphanumeric are preserved (Python's isalnum)."""
    p = session_mod.session_path("cliént")
    # é is considered alphanumeric by Python's str.isalnum(), so it's kept
    assert p.name == "cliént.json"


def test_session_path_strips_symbols(tmp_session_dir):
    """Symbols like !, @, # are stripped."""
    p = session_mod.session_path("hello@world!")
    assert p.name == "helloworld.json"

# ----------------------------------------------------------------- session_exists
def test_session_exists_false_when_missing(tmp_session_dir):
    assert session_mod.session_exists("nothing") is False


def test_session_exists_true_after_creating(tmp_session_dir):
    (tmp_session_dir / "demo.json").write_text("{}", encoding="utf-8")
    assert session_mod.session_exists("demo") is True


# ----------------------------------------------------------------- load_state
def test_load_state_missing_file_raises(tmp_session_dir):
    with pytest.raises(FileNotFoundError):
        session_mod.load_state("missing")


def test_load_state_reads_json(tmp_session_dir):
    payload = {"cookies": [{"name": "session", "value": "abc123"}]}
    (tmp_session_dir / "real.json").write_text(json.dumps(payload), encoding="utf-8")
    state = session_mod.load_state("real")
    assert state == payload


def test_load_state_invalid_json_raises(tmp_session_dir):
    (tmp_session_dir / "corrupt.json").write_text("not json", encoding="utf-8")
    with pytest.raises(json.JSONDecodeError):
        session_mod.load_state("corrupt")


# ----------------------------------------------------------------- list_sessions
def test_list_sessions_empty(tmp_session_dir):
    assert session_mod.list_sessions() == []


def test_list_sessions_returns_sorted_stems(tmp_session_dir):
    (tmp_session_dir / "b.json").write_text("{}", encoding="utf-8")
    (tmp_session_dir / "a.json").write_text("{}", encoding="utf-8")
    (tmp_session_dir / "c.json").write_text("{}", encoding="utf-8")
    assert session_mod.list_sessions() == ["a", "b", "c"]


def test_list_sessions_ignores_non_json(tmp_session_dir):
    (tmp_session_dir / "keep.json").write_text("{}", encoding="utf-8")
    (tmp_session_dir / "ignore.txt").write_text("data", encoding="utf-8")
    assert session_mod.list_sessions() == ["keep"]


# ----------------------------------------------------------------- apply_session
def test_apply_session_missing_raises(tmp_session_dir):
    class FakeCtx:
        def __init__(self):
            self.loaded = False

    with pytest.raises(FileNotFoundError):
        session_mod.apply_session(FakeCtx(), "nothere")


def test_apply_session_logs_when_exists(tmp_session_dir):
    (tmp_session_dir / "demo.json").write_text("{}", encoding="utf-8")

    class FakeCtx:
        pass

    # Should not raise
    session_mod.apply_session(FakeCtx(), "demo")


# ----------------------------------------------------------------- save_session
def test_save_session_writes_file(tmp_session_dir):
    """save_session writes the storage_state to disk."""

    class FakePage:
        class context:
            @staticmethod
            def storage_state(path):
                Path(path).write_text(
                    json.dumps({"cookies": [], "origins": []}), encoding="utf-8"
                )

    saved = session_mod.save_session(FakePage(), "newdemo")
    assert saved.exists()
    assert saved.name == "newdemo.json"
    state = json.loads(saved.read_text(encoding="utf-8"))
    assert state == {"cookies": [], "origins": []}