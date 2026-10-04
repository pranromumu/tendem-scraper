"""Tests for the HTML reporter."""
from datetime import datetime
from pathlib import Path

from tendem_scraper.core.reporter import (
    build_html_report,
    esc,
    write_html_report,
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
        pages = [object()]
        items = [
            Item(page=1, index=1, title="Widget <b>bad</b>", price="$10",
                 link="https://x/1", image="https://x/1.jpg", text="hi"),
        ]
        links = [
            LinkRow(page=1, text="Home", href="https://x/", type="internal"),
        ]
        images = [
            ImageRow(page=1, src="https://x/1.jpg", alt="", alt_state="empty"),
        ]
        headings = [HeadingRow(page=1, level=1, text="Welcome")]
        issues = [
            QAIssue(page=1, severity="Medium", check="Image without alt",
                    detail="no alt", where="x"),
        ]
        tables = [
            TableBlock(page=1, caption="Sales", header=["a", "b"], rows=[["1", "2"]]),
        ]
    return R()


def test_esc_escapes_html():
    assert esc("<script>") == "&lt;script&gt;"
    assert esc('"quoted"') == "&quot;quoted&quot;"


def test_build_html_report_contains_expected_strings():
    html = build_html_report(_meta(), _fake_result())
    assert "<!doctype html>" in html
    assert "Scrape report" in html
    assert "Items (1)" in html
    assert "QA issues (1)" in html
    assert "Links (1)" in html
    assert "Images (1)" in html
    assert "Tables (1)" in html
    assert "Headings (1)" in html


def test_build_html_report_escapes_untrusted_content():
    html = build_html_report(_meta(), _fake_result())
    # The raw <b> from the item title must be escaped
    assert "<b>bad</b>" not in html
    assert "&lt;b&gt;bad&lt;/b&gt;" in html


def test_build_html_report_shows_preset_and_session():
    meta = _meta(preset="shopify", session="mysite")
    html = build_html_report(meta, _fake_result())
    assert "shopify" in html
    assert "mysite" in html


def test_write_html_report_creates_file(tmp_path: Path):
    path = write_html_report(tmp_path, _fake_result(), _meta())
    assert path.exists()
    assert path.read_text(encoding="utf-8").startswith("<!doctype html>")