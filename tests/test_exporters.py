"""Tests for the multi-format exporters."""
import csv
import json
import sqlite3
from datetime import datetime
from pathlib import Path

from tendem_scraper.core.exporters import (
    export_all,
    write_csv,
    write_json,
    write_jsonl,
    write_manifest,
    write_sqlite,
)
from tendem_scraper.models import (
    HeadingRow,
    ImageRow,
    Item,
    LinkRow,
    QAIssue,
    RunMeta,
    TableBlock,
)


def _meta(**overrides) -> RunMeta:
    base = dict(
        url="https://example.com/",
        host="example.com",
        when=datetime(2026, 1, 1, 12, 0, 0),
        method="static",
        secs=1.23,
        pages=1,
    )
    base.update(overrides)
    return RunMeta(**base)


def _fake_result():
    class R:
        pages = []
        items = [
            Item(page=1, index=1, title="Widget", price="$10", link="https://x/1",
                 image="https://x/1.jpg", text="hi", fingerprint="fp1"),
            Item(page=1, index=2, title="Gadget", price="$20", link="https://x/2",
                 image="https://x/2.jpg", text="yo", fingerprint="fp2"),
        ]
        links = [
            LinkRow(page=1, text="Home", href="https://x/", type="internal"),
            LinkRow(page=1, text="About", href="https://x/about", type="internal",
                    status="OK", detail="200"),
        ]
        images = [
            ImageRow(page=1, src="https://x/1.jpg", alt="one", alt_state="ok"),
        ]
        headings = [
            HeadingRow(page=1, level=1, text="Welcome"),
        ]
        issues = [
            QAIssue(page=1, severity="Low", check="Test", detail="x", where="y"),
        ]
        tables = [
            TableBlock(page=1, caption="", header=["a", "b"], rows=[["1", "2"], ["3", "4"]]),
        ]
    return R()


def test_write_csv_creates_utf8_bom_file(tmp_path: Path):
    path = tmp_path / "x.csv"
    write_csv(path, [{"a": 1, "b": 2}, {"a": 3, "b": 4}])
    assert path.exists()
    content = path.read_bytes()
    # UTF-8 BOM so Excel opens it correctly
    assert content.startswith(b"\xef\xbb\xbf")


def test_write_csv_empty_rows(tmp_path: Path):
    path = tmp_path / "empty.csv"
    write_csv(path, [])
    assert path.exists()
    assert path.read_text(encoding="utf-8-sig") == ""


def test_write_json_roundtrip(tmp_path: Path):
    path = tmp_path / "x.json"
    data = [{"a": 1}, {"a": 2}]
    write_json(path, data)
    assert json.loads(path.read_text(encoding="utf-8")) == data


def test_write_jsonl_one_per_line(tmp_path: Path):
    path = tmp_path / "x.jsonl"
    write_jsonl(path, [{"a": 1}, {"a": 2}])
    lines = path.read_text(encoding="utf-8").strip().split("\n")
    assert len(lines) == 2
    assert json.loads(lines[0]) == {"a": 1}
    assert json.loads(lines[1]) == {"a": 2}


def test_write_sqlite_schema_and_rows(tmp_path: Path):
    db = tmp_path / "data.sqlite"
    write_sqlite(db, _fake_result(), _meta())
    assert db.exists()

    con = sqlite3.connect(db)
    try:
        cur = con.cursor()
        assert cur.execute("SELECT COUNT(*) FROM items").fetchone()[0] == 2
        assert cur.execute("SELECT COUNT(*) FROM links").fetchone()[0] == 2
        assert cur.execute("SELECT COUNT(*) FROM images").fetchone()[0] == 1
        assert cur.execute("SELECT COUNT(*) FROM headings").fetchone()[0] == 1
        assert cur.execute("SELECT COUNT(*) FROM qa_issues").fetchone()[0] == 1
        assert cur.execute("SELECT COUNT(*) FROM run_meta").fetchone()[0] == 1
        # spot-check a value
        title = cur.execute("SELECT title FROM items WHERE idx = 1").fetchone()[0]
        assert title == "Widget"
    finally:
        con.close()


def test_export_all_writes_requested_formats(tmp_path: Path):
    result = _fake_result()
    meta = _meta()
    paths = export_all(tmp_path, result, meta, {"csv", "json", "jsonl", "sqlite"})

    assert (tmp_path / "items.csv").exists()
    assert (tmp_path / "items.json").exists()
    assert (tmp_path / "items.jsonl").exists()
    assert (tmp_path / "data.sqlite").exists()
    assert "csv_dir" in paths
    assert "json" in paths
    assert "jsonl" in paths
    assert "sqlite" in paths


def test_export_all_only_csv(tmp_path: Path):
    result = _fake_result()
    meta = _meta()
    export_all(tmp_path, result, meta, {"csv"})
    assert (tmp_path / "items.csv").exists()
    assert not (tmp_path / "items.json").exists()
    assert not (tmp_path / "data.sqlite").exists()


def test_write_manifest_records_files(tmp_path: Path):
    # put a couple of files in the dir first
    (tmp_path / "a.txt").write_text("hi")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "b.txt").write_text("yo")

    path = write_manifest(tmp_path, _meta(), {"items": 2, "pages": 1})
    assert path.exists()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["counts"] == {"items": 2, "pages": 1}
    assert any("a.txt" in f for f in data["files"])
    assert any("sub/b.txt" in f for f in data["files"])