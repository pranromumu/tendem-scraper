"""Tests for cross-page deduplication."""
from tendem_scraper.core.dedupe import dedupe_items
from tendem_scraper.models import Item


def _item(page=1, index=1, title="", price="", link="", image="", text=""):
    return Item(page=page, index=index, title=title, price=price,
                link=link, image=image, text=text)


def test_dedupe_removes_same_link():
    items = [
        _item(1, 1, title="A", link="https://x/1"),
        _item(2, 1, title="A", link="https://x/1"),     # dup
        _item(3, 1, title="B", link="https://x/2"),
    ]
    unique, removed = dedupe_items(items)
    assert len(unique) == 2
    assert removed == 1
    assert unique[0].fingerprint
    assert unique[1].fingerprint


def test_dedupe_same_link_different_query():
    # query strings are ignored → same fingerprint
    items = [
        _item(1, 1, link="https://x/p?id=1"),
        _item(2, 1, link="https://x/p?id=2"),
    ]
    unique, removed = dedupe_items(items)
    assert len(unique) == 1
    assert removed == 1


def test_dedupe_image_and_title_fallback():
    # no link → fingerprint based on image + title
    items = [
        _item(1, 1, title="Product", image="https://img/1.jpg"),
        _item(2, 1, title="Product", image="https://img/1.jpg"),  # dup
        _item(3, 1, title="Other",   image="https://img/1.jpg"),
    ]
    unique, removed = dedupe_items(items)
    assert len(unique) == 2
    assert removed == 1


def test_dedupe_all_unique_returns_same_count():
    items = [
        _item(1, 1, link="https://x/1"),
        _item(1, 2, link="https://x/2"),
        _item(1, 3, link="https://x/3"),
    ]
    unique, removed = dedupe_items(items)
    assert len(unique) == 3
    assert removed == 0


def test_dedupe_preserves_first_occurrence():
    items = [
        _item(1, 1, title="first",  link="https://x/1"),
        _item(2, 1, title="second", link="https://x/1"),  # dup, should be dropped
        _item(3, 1, title="third",  link="https://x/3"),
    ]
    unique, _ = dedupe_items(items)
    assert unique[0].title == "first"
    assert unique[1].title == "third"