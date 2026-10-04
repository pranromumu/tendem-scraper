"""Thread-pool fetch helper for crawl mode.

Note: Playwright is NOT thread-safe; when concurrency > 1 we fall back to
static HTTP only (which is correct for crawl mode anyway — crawl uses
the static path, and per-URL Playwright would need one browser per thread).
"""
from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, Iterable, TypeVar

T = TypeVar("T")
R = TypeVar("R")


def map_concurrent(fn: Callable[[T], R], items: Iterable[T], workers: int = 4
                   ) -> list[tuple[T, R | None, Exception | None]]:
    out: list[tuple[T, R | None, Exception | None]] = []
    items = list(items)
    if workers <= 1:
        for it in items:
            try:
                out.append((it, fn(it), None))
            except Exception as e:
                out.append((it, None, e))
        return out

    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(fn, it): it for it in items}
        for fut in as_completed(futs):
            it = futs[fut]
            try:
                out.append((it, fut.result(), None))
            except Exception as e:
                out.append((it, None, e))
    return out