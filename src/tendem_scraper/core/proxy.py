"""Round-robin proxy rotation."""
from __future__ import annotations
import itertools
from typing import Iterable


class ProxyPool:
    def __init__(self, proxies: Iterable[str] = ()):
        self._proxies = [p for p in proxies if p]
        self._cycle = itertools.cycle(self._proxies) if self._proxies else None

    def next(self) -> str | None:
        return next(self._cycle) if self._cycle else None

    def __bool__(self) -> bool:
        return bool(self._proxies)