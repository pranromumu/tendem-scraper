"""Tests for the CMS fingerprint detector."""
from tendem_scraper.core.fingerprint import detect_preset


def test_shopify_detected():
    html = (
        '<script src="https://cdn.shopify.com/s/files/1/x.js"></script>'
        '<div class="shopify-section">'
    )
    name, score = detect_preset(html)
    assert name == "shopify"
    assert score > 0


def test_woocommerce_detected():
    html = (
        '<body class="woocommerce woocommerce-page">'
        '<link href="/wp-content/plugins/woocommerce/assets/a.css">'
    )
    name, _ = detect_preset(html)
    # either woocommerce or wordpress is acceptable (both patterns match)
    assert name in ("woocommerce", "wordpress")


def test_wordpress_detected():
    html = '<link rel="stylesheet" href="/wp-content/themes/x/style.css">'
    name, score = detect_preset(html)
    assert name in ("wordpress", "woocommerce")
    assert score > 0


def test_unknown_falls_back_to_generic():
    name, score = detect_preset("<html><body>hello</body></html>")
    assert name == "generic"
    assert score == 0


def test_case_insensitive():
    name, score = detect_preset('<SCRIPT SRC="HTTPS://CDN.SHOPIFY.COM/X.JS"></SCRIPT>')
    assert name == "shopify"
    assert score > 0