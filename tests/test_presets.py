import pytest
from tendem_scraper.core.presets import get_preset, list_presets, PRESETS


def test_all_presets_registered():
    assert "shopify" in PRESETS
    assert "woocommerce" in PRESETS
    assert "wordpress" in PRESETS


def test_get_preset_unknown():
    with pytest.raises(KeyError):
        get_preset("nope")


def test_list_presets_sorted():
    assert list_presets() == sorted(list_presets())


def test_books_preset_extracts(books_html):
    from tendem_scraper.pages.generic_listing import GenericListingPage

    class _F:
        def __init__(self, h): self.h = h
        def get(self, u): return self.h, u, "test"
        def close(self): pass

    p = GenericListingPage(_F(books_html), preset=get_preset("books")).load("https://books.toscrape.com/")
    assert len(p.items) == 3
    assert p.items[0].price.startswith("£")