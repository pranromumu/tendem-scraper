"""Extra tests for validators — rule edge cases."""
from __future__ import annotations

from bs4 import BeautifulSoup

from tendem_scraper.core.validators import qa_issues


class _FakePage:
    """Minimal page stub for validator tests."""
    def __init__(self, pageno=1):
        self.pageno = pageno
        self.title = ""
        self.description = ""
        self.lang = ""
        self.headings = []
        self.images = []
        self.links = []
        self.items = []


def _soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "lxml")


def test_missing_title_is_high_severity():
    page = _FakePage()
    page.title = ""
    issues = qa_issues(_soup("<html><body></body></html>"), page)
    checks = {i.check for i in issues}
    assert "Missing <title>" in checks


def test_long_title_is_low_severity():
    page = _FakePage()
    page.title = "A" * 100
    issues = qa_issues(_soup("<html><body></body></html>"), page)
    assert any(i.check == "Long <title>" for i in issues)


def test_missing_description_is_medium():
    page = _FakePage()
    page.title = "Valid title"
    issues = qa_issues(_soup("<html><body></body></html>"), page)
    assert any(i.check == "Missing meta description" for i in issues)


def test_missing_lang_is_low():
    page = _FakePage()
    issues = qa_issues(_soup("<html><body></body></html>"), page)
    assert any(i.check == "Missing lang attribute" for i in issues)


def test_no_h1_is_medium():
    page = _FakePage()
    page.headings = []
    issues = qa_issues(_soup("<html><body></body></html>"), page)
    assert any(i.check == "No <h1>" for i in issues)


def test_multiple_h1_is_low():
    from tendem_scraper.models import HeadingRow
    page = _FakePage()
    page.headings = [
        HeadingRow(page=1, level=1, text="First"),
        HeadingRow(page=1, level=1, text="Second"),
    ]
    issues = qa_issues(_soup("<html><body></body></html>"), page)
    assert any(i.check == "Multiple <h1>" for i in issues)


def test_image_without_alt_flagged():
    from tendem_scraper.models import ImageRow
    page = _FakePage()
    page.images = [ImageRow(page=1, src="x.jpg", alt="", alt_state="missing")]
    issues = qa_issues(_soup("<html><body></body></html>"), page)
    assert any(i.check == "Image without alt" for i in issues)


def test_empty_link_text_flagged():
    from tendem_scraper.models import LinkRow
    page = _FakePage()
    page.links = [LinkRow(page=1, text="", href="https://x/", type="internal")]
    issues = qa_issues(_soup("<html><body></body></html>"), page)
    assert any(i.check == "Link without accessible name" for i in issues)


def test_placeholder_links_flagged():
    from tendem_scraper.models import LinkRow
    page = _FakePage()
    page.links = [LinkRow(page=1, text="Click", href="#", type="anchor")]
    issues = qa_issues(_soup("<html><body></body></html>"), page)
    assert any(i.check == "Placeholder links" for i in issues)


def test_empty_button_flagged():
    page = _FakePage()
    html = "<html><body><button></button></body></html>"
    issues = qa_issues(_soup(html), page)
    assert any(i.check == "Button without accessible name" for i in issues)


def test_duplicate_ids_flagged():
    page = _FakePage()
    html = '<html><body><div id="dup"></div><div id="dup"></div></body></html>'
    issues = qa_issues(_soup(html), page)
    assert any(i.check == "Duplicate id" for i in issues)


def test_unlabeled_input_flagged():
    page = _FakePage()
    html = '<html><body><input type="text" name="foo"></body></html>'
    issues = qa_issues(_soup(html), page)
    assert any(i.check == "Form field without label" for i in issues)


def test_input_with_placeholder_is_low_severity():
    page = _FakePage()
    html = '<html><body><input type="text" placeholder="Enter name"></body></html>'
    issues = qa_issues(_soup(html), page)
    field_issues = [i for i in issues if i.check == "Form field without label"]
    assert any(i.severity == "Low" for i in field_issues)


def test_items_without_title_flagged():
    from tendem_scraper.models import Item
    page = _FakePage()
    page.items = [Item(page=1, index=1, title="", price="$1")]
    issues = qa_issues(_soup("<html><body></body></html>"), page)
    assert any("without title" in i.check for i in issues)


def test_no_prices_detected_is_low():
    from tendem_scraper.models import Item
    page = _FakePage()
    page.items = [
        Item(page=1, index=1, title="A", price=""),
        Item(page=1, index=2, title="B", price=""),
    ]
    issues = qa_issues(_soup("<html><body></body></html>"), page)
    assert any(i.check == "No prices detected" for i in issues)


def test_duplicate_item_link_flagged():
    from tendem_scraper.models import Item
    page = _FakePage()
    page.items = [
        Item(page=1, index=1, title="A", link="https://x/same"),
        Item(page=1, index=2, title="B", link="https://x/same"),
    ]
    issues = qa_issues(_soup("<html><body></body></html>"), page)
    assert any(i.check == "Duplicate item link" for i in issues)