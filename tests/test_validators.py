from tendem_scraper.pages.generic_listing import GenericListingPage


class _FakeFetcher:
    def __init__(self, html): self.html = html
    def get(self, url): return self.html, url, "test"
    def close(self): pass


def test_flags_missing_alt(books_html):
    html = books_html.replace('alt="A Light in the Attic"', "")
    page = GenericListingPage(_FakeFetcher(html)).load("https://books.toscrape.com/")
    assert "Image without alt" in {i.check for i in page.issues}


def test_clean_page_has_no_high(books_html):
    page = GenericListingPage(_FakeFetcher(books_html)).load("https://books.toscrape.com/")
    assert not [i for i in page.issues if i.severity == "High"]