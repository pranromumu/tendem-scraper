"""Tests for the sink module — base class + Google Sheets sink."""
from __future__ import annotations

import sys
import types

import pytest

from tendem_scraper.models import Item
from tendem_scraper.sinks.base_sink import BaseSink
from tendem_scraper.sinks.gsheet_sink import HEADER, GSheetSink


# ----------------------------------------------------------------- base sink
def test_base_sink_cannot_be_instantiated():
    """BaseSink is abstract — cannot be instantiated directly."""
    with pytest.raises(TypeError):
        BaseSink()


def test_base_sink_subclass_must_implement_push():
    """A subclass without push() raises TypeError."""
    class Incomplete(BaseSink):
        pass

    with pytest.raises(TypeError):
        Incomplete()


def test_base_sink_subclass_with_push_works():
    """A minimal subclass works."""
    class Concrete(BaseSink):
        def push(self, items):
            return len(items)

    s = Concrete()
    assert s.push([1, 2, 3]) == 3


def test_base_sink_close_is_noop():
    """close() does nothing by default."""
    class Concrete(BaseSink):
        def push(self, items):
            return 0

    s = Concrete()
    assert s.close() is None


# ----------------------------------------------------------------- GSheetSink init
def test_gsheet_sink_init_defaults():
    sink = GSheetSink(sheet_id="abc123")
    assert sink.sheet_id == "abc123"
    assert sink.worksheet == "items"
    assert sink.mode == "replace"
    assert sink.credentials_file == "credentials.json"
    assert sink._client is None


def test_gsheet_sink_init_custom_worksheet():
    sink = GSheetSink(sheet_id="abc", worksheet="custom", mode="append")
    assert sink.worksheet == "custom"
    assert sink.mode == "append"


# ----------------------------------------------------------------- row formatting
def test_gsheet_sink_row_for_item():
    sink = GSheetSink(sheet_id="abc")
    item = Item(
        page=1, index=1,
        title="Widget", price="$10",
        link="https://x/1", image="https://x/1.jpg",
        text="desc", fingerprint="fp1",
    )
    row = sink._row_for(item)
    assert row == ["1", "1", "Widget", "$10", "https://x/1", "https://x/1.jpg", "desc", "fp1"]


def test_gsheet_sink_header_has_8_columns():
    assert len(HEADER) == 8
    assert HEADER[0] == "page"
    assert HEADER[-1] == "fingerprint"


# ----------------------------------------------------------------- push — empty
def test_gsheet_sink_push_empty_returns_zero():
    sink = GSheetSink(sheet_id="abc")
    assert sink.push([]) == 0


# ----------------------------------------------------------------- push — mocked client
def _fake_gspread_module():
    """Build a fake gspread module for monkeypatching."""
    fake = types.ModuleType("gspread")

    class FakeWorksheet:
        def __init__(self):
            self.appended = []
            self.cleared = False
        def clear(self):
            self.cleared = True
        def append_row(self, row):
            self.appended.append(row)
        def append_rows(self, rows):
            self.appended.extend(rows)
        def get_all_values(self):
            return []

    class FakeSheet:
        def __init__(self):
            self.ws = FakeWorksheet()
        def worksheet(self, name):
            raise Exception("not found")  # forces add_worksheet
        def add_worksheet(self, title, rows, cols):
            return self.ws

    class FakeClient:
        def __init__(self):
            self.sheet = FakeSheet()
        def open_by_key(self, key):
            return self.sheet

    fake.service_account = lambda filename: FakeClient()
    return fake


def test_gsheet_sink_push_writes_header_and_rows(monkeypatch):
    fake_module = _fake_gspread_module()
    monkeypatch.setitem(sys.modules, "gspread", fake_module)

    sink = GSheetSink(sheet_id="abc", mode="replace")
    items = [
        Item(page=1, index=1, title="A", price="$1", link="u", image="i", text="t", fingerprint="fp1"),
        Item(page=1, index=2, title="B", price="$2", link="u", image="i", text="t", fingerprint="fp2"),
    ]
    written = sink.push(items)
    assert written == 2


def test_gsheet_sink_push_append_mode(monkeypatch):
    fake_module = _fake_gspread_module()
    monkeypatch.setitem(sys.modules, "gspread", fake_module)

    sink = GSheetSink(sheet_id="abc", mode="append")
    items = [
        Item(page=1, index=1, title="A", price="$1", link="u", image="i", text="t", fingerprint="fp1"),
    ]
    assert sink.push(items) == 1


def test_gsheet_sink_missing_gspread_raises(monkeypatch):
    """If gspread isn't installed, _connect raises RuntimeError."""
    import builtins
    real_import = builtins.__import__

    def fake_import(name, *a, **k):
        if name == "gspread":
            raise ImportError("simulated")
        return real_import(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    sink = GSheetSink(sheet_id="abc")
    with pytest.raises(RuntimeError, match="gspread"):
        sink._connect()


def test_gsheet_sink_missing_credentials_raises(monkeypatch, tmp_path):
    """If the credentials file doesn't exist, _connect raises RuntimeError."""
    fake = types.ModuleType("gspread")
    def raise_not_found(filename):
        raise FileNotFoundError(f"no {filename}")
    fake.service_account = raise_not_found
    monkeypatch.setitem(sys.modules, "gspread", fake)

    sink = GSheetSink(sheet_id="abc", credentials_file=str(tmp_path / "missing.json"))
    with pytest.raises(RuntimeError, match="credentials"):
        sink._connect()