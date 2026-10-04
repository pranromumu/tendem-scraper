from tendem_scraper.core.pipeline import Pipeline
from tendem_scraper.pages.generic_listing import GenericListingPage


class _FakeFetcher:
    def __init__(self, mapping): self.mapping = mapping
    def get(self, url): return self.mapping[url], url, "test"
    def close(self): pass


def test_pipeline_paginates(books_html):
    f = _FakeFetcher({
        "https://books.toscrape.com/": books_html,
        "https://books.toscrape.com/page-2.html": books_html,
    })
    result = Pipeline(f, GenericListingPage, max_pages=2, delay=0).run("https://books.toscrape.com/")
    assert len(result.pages) == 2
    assert len(result.items) == 6