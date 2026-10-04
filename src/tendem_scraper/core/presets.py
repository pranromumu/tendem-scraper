"""CMS-specific presets. Turn 'paste URL' from ~80% → ~95% accuracy.

Each preset defines:
    name           human label
    item_selector  CSS for the repeating card
    fields         selector map for title/price/link/image
    next_selector  CSS for the "Next" link (optional)
    paginate_param URL param fallback (?page=N)
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Preset:
    name: str
    item_selector: str
    title_selector: str = ""
    price_selector: str = ""
    link_selector: str = "a"
    image_selector: str = "img"
    next_selector: str = 'a[rel~="next"], link[rel~="next"]'
    paginate_param: str | None = None
    item_link_attr: str = "href"
    item_img_attr: str = "src"


PRESETS: dict[str, Preset] = {
    "generic": Preset(
        name="generic",
        item_selector="",
    ),
    "shopify": Preset(
        name="shopify",
        item_selector=".product-card, .product-item, li.grid__item, [data-product-id]",
        title_selector=".product-card__title, .card__heading, h3, h2",
        price_selector=".price, .price__regular, [class*='price']",
        link_selector="a.full-unstyled-link, a.product-card__link, a[href*='/products/']",
        image_selector="img.product-card__image, img.card__media-image, img",
        next_selector='a[rel="next"], .pagination__item--next a, a[aria-label="Next page"]',
        paginate_param="page",
    ),
    "woocommerce": Preset(
        name="woocommerce",
        item_selector="ul.products li.product, .wc-block-grid__product, .product-small",
        title_selector=".woocommerce-loop-product__title, h2, h3",
        price_selector=".price, .woocommerce-Price-amount, bdi",
        link_selector="a.woocommerce-LoopProduct-link, a",
        image_selector="img.attachment-woocommerce_thumbnail, img",
        next_selector='a.next.page-numbers, a[rel="next"]',
        paginate_param="paged",
    ),
    "wordpress": Preset(
        name="wordpress",
        item_selector="article, .post, .hentry, .wp-block-post",
        title_selector=".entry-title, h2.entry-title, h2, h3",
        price_selector="",
        link_selector="a.entry-title-link, h2 a, h3 a, a",
        image_selector="img.wp-post-image, img",
        next_selector='a.next.page-numbers, a[rel="next"]',
        paginate_param="paged",
    ),
    "magento": Preset(
        name="magento",
        item_selector="li.product-item, .product-item-info, .product-card",
        title_selector=".product-item-name, .product-item-link, h3, h2",
        price_selector=".price, .price-wrapper, [data-price-type='finalPrice']",
        link_selector="a.product-item-link, a.product, a",
        image_selector="img.product-image-photo, img",
        next_selector='a.action.next, a[rel="next"]',
        paginate_param="p",
    ),
    "wix": Preset(
        name="wix",
        item_selector="[data-hook='product-item'], .product-item, li[data-hook]",
        title_selector="[data-hook='product-item-name'], h3, h2",
        price_selector="[data-hook='product-item-price'], .price",
        link_selector="a",
        image_selector="img",
    ),
    "squarespace": Preset(
        name="squarespace",
        item_selector=".product-list-item, .sqs-block-product, article",
        title_selector=".product-title, h2, h3",
        price_selector=".product-price, .sqs-money-native, [class*='price']",
        link_selector="a",
        image_selector="img",
        next_selector='a[rel="next"]',
    ),
    "books": Preset(  # demo for books.toscrape.com
        name="books",
        item_selector="article.product_pod",
        title_selector="h3 a",
        price_selector="p.price_color",
        link_selector="h3 a",
        image_selector="img",
        next_selector='li.next a',
    ),
}


def get_preset(name: str) -> Preset:
    if name not in PRESETS:
        raise KeyError(f"Unknown preset '{name}'. Available: {', '.join(sorted(PRESETS))}")
    return PRESETS[name]


def list_presets() -> list[str]:
    return sorted(PRESETS.keys())