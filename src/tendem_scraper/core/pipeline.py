"""Pipeline: run a Page Object across N pages."""
from __future__ import annotations
import time
from dataclasses import dataclass, field

from . import logging as log
from .fetcher import Fetcher, FetchError, robots_allows
from ..pages.base_page import BasePage
from ..models import Item, LinkRow, ImageRow, HeadingRow, TableBlock, QAIssue
from ..config import settings


@dataclass
class RunResult:
    pages: list[BasePage] = field(default_factory=list)

    @property
    def items(self) -> list[Item]: return [i for p in self.pages for i in p.items]
    @property
    def links(self) -> list[LinkRow]: return [l for p in self.pages for l in p.links]
    @property
    def images(self) -> list[ImageRow]: return [i for p in self.pages for i in p.images]
    @property
    def headings(self) -> list[HeadingRow]: return [h for p in self.pages for h in p.headings]
    @property
    def tables(self) -> list[TableBlock]: return [t for p in self.pages for t in p.tables]
    @property
    def issues(self) -> list[QAIssue]: return [i for p in self.pages for i in p.issues]


class Pipeline:
    def __init__(self, fetcher: Fetcher, page_cls, page_kwargs: dict | None = None,
                 max_pages: int = 1, delay: float | None = None,
                 ignore_robots: bool = False):
        self.fetcher = fetcher
        self.page_cls = page_cls
        self.page_kwargs = page_kwargs or {}
        self.max_pages = max(1, max_pages)
        self.delay = settings.delay_seconds if delay is None else delay
        self.ignore_robots = ignore_robots

    def run(self, start_url: str) -> RunResult:
        result = RunResult()
        url = start_url
        seen: set[str] = set()
        is_local = start_url.endswith((".html", ".htm")) or "://" not in start_url

        for pageno in range(1, self.max_pages + 1):
            if not is_local and not robots_allows(url):
                if pageno == 1:
                    log.warn("robots.txt disallows this path — continuing since you asked explicitly.")
                elif not self.ignore_robots:
                    log.warn(f"robots.txt disallows {url} — stopping.")
                    break

            if pageno > 1:
                log.info(f"waiting {self.delay}s before page {pageno}…")
                time.sleep(self.delay)

            log.stage(f"fetch page {pageno}", url)
            try:
                page = self.page_cls(self.fetcher, **self.page_kwargs).load(url, pageno)
            except FetchError as e:
                log.fail(str(e))
                raise
            result.pages.append(page)
            seen.add(page.final_url)

            log.metric("method", page.method)
            log.metric("items", len(page.items))
            log.metric("links", len(page.links))
            log.metric("images", len(page.images))
            log.metric("tables", len(page.tables))
            log.metric("qa issues", len(page.issues))

            if pageno >= self.max_pages or not page.next_url or page.next_url in seen or is_local:
                break
            url = page.next_url

        return result