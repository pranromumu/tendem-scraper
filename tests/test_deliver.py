# ruff: noqa: E501
"""Tests for the delivery helper — QA checks, ZIP, email templates."""
from __future__ import annotations

import csv
import zipfile
from pathlib import Path

import pytest

from tendem_scraper import deliver


# ----------------------------------------------------------------- helpers
def test_read_csv_rows_missing_file(tmp_path: Path):
    """A missing file returns an empty list."""
    assert deliver._read_csv_rows(tmp_path / "nope.csv") == []


def test_read_csv_rows_returns_dicts(tmp_path: Path):
    p = tmp_path / "x.csv"
    with p.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=["a", "b"])
        w.writeheader()
        w.writerow({"a": "1", "b": "2"})
        w.writerow({"a": "3", "b": "4"})
    rows = deliver._read_csv_rows(p)
    assert len(rows) == 2
    assert rows[0]["a"] == "1"


# ----------------------------------------------------------------- find report
def test_find_latest_report_empty_reports(tmp_path, monkeypatch):
    """No reports/ folder → exits."""
    monkeypatch.chdir(tmp_path)
    with pytest.raises(SystemExit):
        deliver._find_latest_report()


def test_find_latest_report_picks_newest(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    reports = tmp_path / "reports"
    reports.mkdir()
    old = reports / "scrape_old"
    new = reports / "scrape_new"
    old.mkdir()
    new.mkdir()
    # Touch the new one with a slightly later timestamp
    import time
    time.sleep(0.01)
    new.touch()
    latest = deliver._find_latest_report()
    assert latest.name == "scrape_new"


# ----------------------------------------------------------------- QA checks
def _make_report(tmp_path: Path, items: list[dict], qa: list[dict] | None = None) -> Path:
    """Build a fake report folder with items.csv + qa_issues.csv."""
    rep = tmp_path / "reports" / "scrape_test_20260101_120000"
    rep.mkdir(parents=True)
    if items:
        fields = list(items[0].keys())
        with (rep / "items.csv").open("w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            w.writerows(items)
    if qa is not None:
        fields = list(qa[0].keys()) if qa else ["page", "severity", "check", "detail", "where"]
        with (rep / "qa_issues.csv").open("w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            w.writerows(qa)
    return rep


def test_qa_check_clean_report(tmp_path: Path):
    rep = _make_report(
        tmp_path,
        items=[
            {"page": "1", "index": "1", "title": "A", "price": "$1", "link": "u", "image": "i", "text": "t", "fingerprint": "fp1"},
            {"page": "1", "index": "2", "title": "B", "price": "$2", "link": "u", "image": "i", "text": "t", "fingerprint": "fp2"},
        ],
        qa=[],
    )
    qa = deliver._qa_check(rep)
    assert qa["total"] == 2
    assert qa["missing_title"] == 0
    assert qa["missing_price"] == 0
    assert qa["qa_issues_high"] == 0


def test_qa_check_counts_missing_fields(tmp_path: Path):
    rep = _make_report(
        tmp_path,
        items=[
            {"page": "1", "index": "1", "title": "", "price": "", "link": "u", "image": "", "text": "t", "fingerprint": ""},
            {"page": "1", "index": "2", "title": "B", "price": "$2", "link": "u", "image": "i", "text": "t", "fingerprint": "fp2"},
        ],
        qa=[],
    )
    qa = deliver._qa_check(rep)
    assert qa["total"] == 2
    assert qa["missing_title"] == 1
    assert qa["missing_price"] == 1
    assert qa["missing_image"] == 1


def test_qa_check_counts_duplicates(tmp_path: Path):
    rep = _make_report(
        tmp_path,
        items=[
            {"page": "1", "index": "1", "title": "A", "price": "$1", "link": "u", "image": "i", "text": "t", "fingerprint": "same"},
            {"page": "1", "index": "2", "title": "B", "price": "$2", "link": "u", "image": "i", "text": "t", "fingerprint": "same"},
        ],
        qa=[],
    )
    qa = deliver._qa_check(rep)
    assert qa["duplicate_fingerprints"] == 1


def test_qa_check_counts_high_severity(tmp_path: Path):
    rep = _make_report(
        tmp_path,
        items=[{"page": "1", "index": "1", "title": "A", "price": "$1", "link": "u", "image": "i", "text": "t", "fingerprint": "fp"}],
        qa=[
            {"page": "1", "severity": "High", "check": "X", "detail": "bad", "where": "u"},
            {"page": "1", "severity": "Low", "check": "Y", "detail": "minor", "where": "u"},
        ],
    )
    qa = deliver._qa_check(rep)
    assert qa["qa_issues_total"] == 2
    assert qa["qa_issues_high"] == 1


# ----------------------------------------------------------------- packaging
def test_package_creates_zip(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    rep = tmp_path / "reports" / "scrape_test"
    rep.mkdir(parents=True)
    (rep / "items.csv").write_text("a,b\n1,2\n", encoding="utf-8")
    (rep / "report.html").write_text("<html></html>", encoding="utf-8")

    zip_path = deliver._package(rep, client="acme", no_zip=False)
    assert zip_path is not None
    assert zip_path.exists()
    assert zip_path.suffix == ".zip"
    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()
        assert any("items.csv" in n for n in names)
        assert any("report.html" in n for n in names)


def test_package_no_zip_flag(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    rep = tmp_path / "reports" / "scrape_test"
    rep.mkdir(parents=True)
    assert deliver._package(rep, client="acme", no_zip=True) is None


# ----------------------------------------------------------------- templates
def test_qa_summary_clean():
    qa = {
        "missing_title": 0, "missing_price": 0,
        "duplicate_fingerprints": 0, "qa_issues_high": 0,
    }
    text = deliver._qa_summary_text(qa)
    assert "clean" in text.lower()


def test_qa_summary_with_issues():
    qa = {
        "missing_title": 2, "missing_price": 1,
        "duplicate_fingerprints": 3, "qa_issues_high": 1,
    }
    text = deliver._qa_summary_text(qa)
    assert "2" in text
    assert "HIGH" in text


def test_delivery_template_has_placeholders():
    """The template uses format placeholders we can substitute."""
    formatted = deliver.DELIVERY_TEMPLATE.format(
        client="acme", rows=100, zipname="acme.zip",
        date="2026-10-08", qa_summary="clean", signature="Kabir",
    )
    assert "acme" in formatted
    assert "100" in formatted
    assert "acme.zip" in formatted


def test_followup_template_has_placeholders():
    formatted = deliver.FOLLOWUP_TEMPLATE.format(client="acme", signature="Kabir")
    assert "acme" in formatted
    assert "Kabir" in formatted


# ----------------------------------------------------------------- main
def test_main_no_zip_skips_packaging(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _make_report(
        tmp_path,
        items=[{"page": "1", "index": "1", "title": "A", "price": "$1", "link": "u", "image": "i", "text": "t", "fingerprint": "fp"}],
        qa=[],
    )
    rc = deliver.main(["--client", "acme", "--no-zip", "--no-email"])
    assert rc == 0