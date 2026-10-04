"""Map --page-object name → class."""
from .generic_listing import GenericListingPage
from .product_page import ProductDetailPage
from .books_toscrape import BooksToScrapePage

PAGE_REGISTRY = {
    "listing": GenericListingPage,
    "product": ProductDetailPage,
    "books": BooksToScrapePage,
}