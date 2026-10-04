"""Whole-site crawler — BFS from a seed URL, respecting host + robots + limits."""
from __future__ import annotations

from collections import deque
from urllib.parse import urldefrag, urlparse

from bs4 import BeautifulSoup

from . import logging as log
from .fetcher import Fetcher, FetchError, robots_allows


def _norm(u: str) -> str:
    u, _ = urldefrag(u)
    return u.rstrip("/")


def crawl_urls(seed: str,
               fetcher: Fetcher,
               max_pages: int = 200,
               same_host_only: bool = True,
               respect_robots: bool = True) -> list[tuple[str, str]]:
    """BFS crawl. Returns [(url, html), ...] in visit order."""
    seed_host = urlparse(seed).netloc
    seen: set[str] = set()
    queue: deque[str] = deque([_norm(seed)])
    out: list[tuple[str, str]] = []

    while queue and len(out) < max_pages:
        url = queue.popleft()
        if url in seen:
            continue
        seen.add(url)

        if respect_robots and not robots_allows(url):
            log.warn(f"robots.txt disallows {url} — skipping")
            continue

        try:
            html, final, _ = fetcher.get(url)
        except FetchError as e:
            log.warn(f"Skip {url}: {e}")
            continue

        out.append((final, html))
        log.metric("crawled", f"{len(out)}/{max_pages}  {url}")

        # enqueue internal links
        try:
            soup = BeautifulSoup(html, "lxml")
        except Exception:
            continue
        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            if href.startswith(("#", "mailto:", "tel:", "javascript:")):
                continue
            from urllib.parse import urljoin
            nxt = _norm(urljoin(final, href))
            if not nxt.startswith(("http://", "https://")):
                continue
            if same_host_only and urlparse(nxt).netloc != seed_host:
                continue
            if nxt not in seen:
                queue.append(nxt)

    return out