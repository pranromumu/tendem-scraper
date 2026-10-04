"""GenericListingPage — auto-detects the main repeating block OR uses a preset."""
from __future__ import annotations

from ..core.extractors import extract_item, find_item_groups
from ..core.presets import Preset
from .base_page import BasePage


class GenericListingPage(BasePage):
    name = "generic-listing"

    def __init__(self, fetcher, item_selector: str | None = None, preset: Preset | None = None):
        super().__init__(fetcher, preset=preset)
        self.item_selector = item_selector

    def _parse_items(self) -> None:
        # precedence: CLI --item-selector > preset.item_selector > auto-detect
        selector = self.item_selector or (self.preset.item_selector if self.preset else "")

        if selector:
            try:
                nodes = self.soup.select(selector)
            except Exception as e:
                raise ValueError(f"Invalid item selector '{selector}': {e}") from e
            if not nodes:
                # fall back to auto-detect if preset didn't match
                groups = find_item_groups(self.soup)
                self.candidates = [{"selector": g["selector"], "count": g["count"],
                                    "score": g["score"]} for g in groups[:3]]
                nodes = groups[0]["items"] if groups else []
                self.selector = (groups[0]["selector"] if groups else selector) + "  [auto-fallback]"
            else:
                self.selector = selector + (f"  (preset:{self.preset.name})" if self.preset else "")
                self.candidates = []
        else:
            groups = find_item_groups(self.soup)
            self.candidates = [{"selector": g["selector"], "count": g["count"],
                                "score": g["score"]} for g in groups[:3]]
            nodes = groups[0]["items"] if groups else []
            self.selector = groups[0]["selector"] if groups else ""

        p = self.preset
        self.items = [
            extract_item(
                n, self.final_url, self.pageno, i,
                title_selector=p.title_selector if p else "",
                price_selector=p.price_selector if p else "",
                link_selector=p.link_selector if p else "a",
                image_selector=p.image_selector if p else "img",
                item_link_attr=p.item_link_attr if p else "href",
                item_img_attr=p.item_img_attr if p else "src",
            )
            for i, n in enumerate(nodes, 1)
        ]