"""Tests for concrete Page Objects and the registry."""
from tendem_scraper.pages.books_toscrape import BooksToScrapePage
from tendem_scraper.pages.generic_listing import GenericListingPage
from tendem_scraper.pages.product_page import ProductDetailPage
from tendem_scraper.pages.registry import PAGE_REGISTRY


class _FakeFetcher:
    def __init__(self, html):
        self.html = html

    def get(self, url):
        return self.html, url, "test"

    def close(self):
        pass


BOOKS_HTML = """
<!doctype html><html lang="en"><head><meta charset="utf-8">
<title>Books</title><meta name="description" content="demo">
</head><body>
<h1>All books</h1>
<article class="product_pod">
  <h3><a href="/p1" title="Book One">Book One</a></h3>
  <p class="price_color">£10.00</p>
  <img src="/img/1.jpg" alt="Book One">
</article>
<article class="product_pod">
  <h3><a href="/p2" title="Book Two">Book Two</a></h3>
  <p class="price_color">£20.00</p>
  <img src="/img/2.jpg" alt="Book Two">
</article>
<article class="product_pod">
  <h3><a href="/p3" title="Book Three">Book Three</a></h3>
  <p class="price_color">£30.00</p>
  <img src="/img/3.jpg" alt="Book Three">
</article>
<a rel="next" href="/page-2.html">next</a>
</body></html>
"""

PRODUCT_HTML = """
<!doctype html><html lang="en"><head><meta charset="utf-8">
<title>Fancy Widget</title><meta name="description" content="A widget">
</head><body>
<h1>Fancy Widget</h1>
<p class="price">$49.99</p>
<div class="description">A very fine widget indeed.</div>
<img src="/img/widget.jpg" alt="Fancy Widget">
</body></html>
"""


def test_registry_exposes_all_expected_pages():
    assert "listing" in PAGE_REGISTRY
    assert "product" in PAGE_REGISTRY
    assert "books" in PAGE_REGISTRY


def test_books_toscrape_extracts_all_items():
    page = BooksToScrapePage(_FakeFetcher(BOOKS_HTML)).load("https://books.toscrape.com/")
    assert len(page.items) == 3
    titles = [i.title for i in page.items]
    assert titles == ["Book One", "Book Two", "Book Three"]
    assert page.items[0].price == "£10.00"
    assert page.items[0].link.endswith("/p1")
    assert page.items[0].image.endswith("/img/1.jpg")


def test_books_toscrape_pagination():
    page = BooksToScrapePage(_FakeFetcher(BOOKS_HTML)).load("https://books.toscrape.com/")
    assert page.next_url == "https://books.toscrape.com/page-2.html"


def test_books_toscrape_selector_is_documented():
    page = BooksToScrapePage(_FakeFetcher(BOOKS_HTML)).load("https://books.toscrape.com/")
    assert page.selector == "article.product_pod"


def test_product_detail_extracts_one_item():
    page = ProductDetailPage(_FakeFetcher(PRODUCT_HTML)).load("https://shop.example.com/p/1")
    assert len(page.items) == 1
    item = page.items[0]
    assert item.title == "Fancy Widget"
    assert item.price == "$49.99"
    assert item.link == "https://shop.example.com/p/1"
    assert item.image.endswith("/img/widget.jpg")
    assert "fine widget" in item.text


def test_product_detail_no_pagination():
    page = ProductDetailPage(_FakeFetcher(PRODUCT_HTML)).load("https://shop.example.com/p/1")
    assert page.next_url is None


def test_generic_listing_with_item_selector():
    html = BOOKS_HTML
    page = GenericListingPage(
        _FakeFetcher(html), item_selector="article.product_pod"
    ).load("https://books.toscrape.com/")
    assert len(page.items) == 3
    assert page.selector.startswith("article.product_pod")