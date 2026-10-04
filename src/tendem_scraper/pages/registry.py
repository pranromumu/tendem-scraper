"""Map --page-object name → class."""
from .books_toscrape import BooksToScrapePage
from .generic_listing import GenericListingPage
from .product_page import ProductDetailPage

PAGE_REGISTRY = {
    "listing": GenericListingPage,
    "product": ProductDetailPage,
    "books": BooksToScrapePage,
}