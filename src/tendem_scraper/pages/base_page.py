"""BasePage — POM root."""
from __future__ import annotations

from abc import ABC, abstractmethod

from bs4 import BeautifulSoup

from ..core.extractors import extract_headings, extract_images, extract_links, extract_tables, find_next
from ..core.presets import Preset
from ..core.validators import qa_issues
from ..models import HeadingRow, ImageRow, Item, LinkRow, QAIssue, TableBlock


class BasePage(ABC):
    name: str = "page"

    def __init__(self, fetcher, preset: Preset | None = None):
        self.fetcher = fetcher
        self.preset = preset
        self.url = ""
        self.final_url = ""
        self.method = "static"
        self.soup: BeautifulSoup | None = None
        self.html = ""
        self.pageno = 1

        self.items: list[Item] = []
        self.links: list[LinkRow] = []
        self.images: list[ImageRow] = []
        self.headings: list[HeadingRow] = []
        self.tables: list[TableBlock] = []
        self.issues: list[QAIssue] = []
        self.next_url: str | None = None
        self.title = ""
        self.description = ""
        self.lang = ""
        self.selector = ""
        self.candidates: list[dict] = []

    def load(self, url: str, pageno: int = 1) -> BasePage:
        self.url = url
        self.pageno = pageno
        self.html, self.final_url, self.method = self.fetcher.get(url)
        self.soup = BeautifulSoup(self.html, "lxml")
        self._parse_header()
        self._parse_common()
        self._parse_items()
        self.next_url = find_next(
            self.soup, self.final_url,
            next_selector=self.preset.next_selector if self.preset else "",
        )
        self.issues = qa_issues(self.soup, self)
        return self

    @abstractmethod
    def _parse_items(self) -> None: ...

    def _parse_header(self) -> None:
        s = self.soup
        self.title = " ".join(s.title.get_text(" ").split()) if s.title else ""
        meta = s.find("meta", attrs={"name": lambda v: v and v.lower() == "description"})
        self.description = (meta.get("content") or "").strip() if meta else ""
        self.lang = (s.html.get("lang") or "") if s.html else ""

    def _parse_common(self) -> None:
        self.links = extract_links(self.soup, self.final_url, self.pageno)
        self.images = extract_images(self.soup, self.final_url, self.pageno)
        self.headings = extract_headings(self.soup, self.pageno)
        self.tables = extract_tables(self.soup, self.pageno)