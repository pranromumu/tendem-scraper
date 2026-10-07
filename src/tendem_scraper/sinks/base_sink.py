"""Base class for all sinks.

A sink takes the list of items from a scrape run and pushes them somewhere
(Google Sheets, a database, an API, ...). Every sink implements `push()`.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from ..models import Item


class BaseSink(ABC):
    """Every sink implements push(items) -> int (rows written)."""

    name: str = "base"

    def __init__(self, **kwargs) -> None:
        self.config = kwargs

    @abstractmethod
    def push(self, items: list[Item]) -> int:
        """Write items to the sink. Return number of rows written."""
        ...

    def close(self) -> None:
        """Optional cleanup."""
        return None