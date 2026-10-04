from bs4 import BeautifulSoup
from tendem_scraper.core.extractors import (
    extract_links, extract_images, find_item_groups, clean,
)


def test_clean_collapses_whitespace():
    assert clean("  hello\n\tworld  ") == "hello world"


def test_links_classified(books_html):
    soup = BeautifulSoup(books_html, "lxml")
    links = extract_links(soup, "https://books.toscrape.com/", 1)
    assert any(l.type == "internal" for l in links)


def test_image_alt_state(books_html):
    soup = BeautifulSoup(books_html, "lxml")
    imgs = extract_images(soup, "https://books.toscrape.com/", 1)
    assert imgs and all(i.alt_state == "ok" for i in imgs)


def test_item_group_autodetected(books_html):
    soup = BeautifulSoup(books_html, "lxml")
    groups = find_item_groups(soup, min_items=3)
    assert groups
    assert groups[0]["count"] == 3