"""Concrete POM: single product detail."""
from __future__ import annotations

from urllib.parse import urljoin

from ..core.extractors import PRICE, clean
from ..models import Item
from .base_page import BasePage


class ProductDetailPage(BasePage):
    name = "product-detail"
    TITLE_SEL = "h1"
    PRICE_SEL = '[class*="price" i]'
    DESC_SEL = '[class*="description" i], #description'
    SKU_SEL = '[class*="sku" i], [itemprop="sku"]'
    IMG_SEL = '[class*="gallery" i] img, [itemprop="image"]'

    def _parse_items(self) -> None:
        s = self.soup
        self.selector = f"{self.TITLE_SEL} (hand-written)"
        title_el = s.select_one(self.TITLE_SEL)
        title = clean(title_el.get_text(" ")) if title_el else ""
        price_el = s.select_one(self.PRICE_SEL)
        m = PRICE.search(clean(price_el.get_text(" ")) if price_el else "")
        desc_el = s.select_one(self.DESC_SEL)
        images = [urljoin(self.final_url, i.get("src") or "")
                  for i in s.select(self.IMG_SEL) if i.get("src")]
        self.items = [Item(
            page=self.pageno, index=1, title=title,
            price=m.group(0).strip() if m else "",
            link=self.final_url,
            image=images[0] if images else "",
            text=clean(desc_el.get_text(" "))[:400] if desc_el else "",
        )]