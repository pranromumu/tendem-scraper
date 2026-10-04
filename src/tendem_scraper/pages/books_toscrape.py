"""Example concrete POM for books.toscrape.com — used in README + tests."""
from __future__ import annotations

from urllib.parse import urljoin

from ..core.extractors import PRICE, clean
from ..models import Item
from .base_page import BasePage


class BooksToScrapePage(BasePage):
    name = "books-toscrape"
    CARD_SEL = "article.product_pod"

    def _parse_items(self) -> None:
        self.selector = self.CARD_SEL
        items: list[Item] = []
        for i, n in enumerate(self.soup.select(self.CARD_SEL), 1):
            a = n.select_one("h3 a")
            title = (a.get("title") or clean(a.get_text(" "))) if a else ""
            price_el = n.select_one("p.price_color")
            m = PRICE.search(clean(price_el.get_text(" ")) if price_el else "")
            img = n.select_one("img")
            items.append(Item(
                page=self.pageno, index=i, title=title,
                price=m.group(0).strip() if m else "",
                link=urljoin(self.final_url, a["href"]) if a and a.get("href") else "",
                image=urljoin(self.final_url, img["src"]) if img and img.get("src") else "",
                text=clean(" ".join(n.stripped_strings))[:400],
            ))
        self.items = items