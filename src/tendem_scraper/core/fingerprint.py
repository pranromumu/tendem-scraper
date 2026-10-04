"""CMS fingerprint detection — powers --preset auto.

Looks at HTML head, script srcs, meta tags, class names and asset hosts to
guess the platform. Cheap (regex only) and offline.
"""
from __future__ import annotations

from bs4 import BeautifulSoup

from .presets import PRESETS

# Each rule: (preset_name, weight, [list of regex tested against lowercased HTML])
RULES: list[tuple[str, int, list[str]]] = [
    ("shopify",      5, [r"cdn\.shopify\.com", r"shopify\.theme", r"/cdn/shop/", r"shopify-payment-button"]),
    ("woocommerce",  5, [r"woocommerce-", r"wc-block-", r"/wp-content/plugins/woocommerce/"]),
    ("wordpress",    3, [r"/wp-content/", r"/wp-includes/", r"wp-json"]),
    ("magento",      5, [r"mage/", r"/static/version\d+/frontend/", r"Magento_"]),
    ("wix",          5, [r"static\.parastorage\.com", r"wix-warmup-data", r"x-wix-"]),
    ("squarespace",  5, [r"static1\.squarespace\.com", r"squarespace-cdn", r"sqs-block-"]),
    ("bigcommerce",  4, [r"cdn\d*\.bigcommerce\.com", r"bigcommerce\.com/s-"]),
    ("prestashop",   4, [r"/themes/[^/]+/assets/", r"prestashop", r"ps_"]),
    ("opencart",     4, [r"catalog/view/theme", r"route=product/"]),
]


def detect_preset(html: str) -> tuple[str, int]:
    """Return (preset_name, score). Falls back to ('generic', 0)."""
    low = html.lower()
    scores: dict[str, int] = {}
    for name, weight, pats in RULES:
        for p in pats:
            import re
            if re.search(p, low):
                scores[name] = scores.get(name, 0) + weight

    if not scores:
        return "generic", 0
    best = max(scores.items(), key=lambda kv: kv[1])
    # sanity: the returned preset must exist
    if best[0] not in PRESETS:
        return "generic", 0
    return best


def detect_from_soup(soup: BeautifulSoup) -> tuple[str, int]:
    return detect_preset(str(soup)[:200_000])