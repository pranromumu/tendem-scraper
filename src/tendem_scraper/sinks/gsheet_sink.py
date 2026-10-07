"""Push scraped items to a Google Sheet.

Two ways to authenticate:

1. Service account JSON file  — for backend jobs / scheduled runs
   gspread.service_account(filename="credentials.json")

2. OAuth user consent         — for interactive runs
   (not implemented here, use service accounts for scraping jobs)

What it does:
- Opens a Google Sheet by ID
- Clears or appends a worksheet
- Writes a header row + one row per Item
- Formats the header (bold)
"""
from __future__ import annotations

from typing import Any

from ..core import logging as log
from ..models import Item
from .base_sink import BaseSink

HEADER = ["page", "index", "title", "price", "link", "image", "text", "fingerprint"]


class GSheetSink(BaseSink):
    """Push items to a worksheet in a Google Sheet."""

    name = "gsheet"

    def __init__(
        self,
        sheet_id: str,
        credentials_file: str = "credentials.json",
        worksheet: str = "items",
        mode: str = "replace",  # "replace" | "append"
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.sheet_id = sheet_id
        self.credentials_file = credentials_file
        self.worksheet = worksheet
        self.mode = mode
        self._client = None

    def _connect(self) -> None:
        """Lazy connect — only load gspread when actually used."""
        if self._client is not None:
            return
        try:
            import gspread
        except ImportError as e:
            raise RuntimeError(
                "gspread is not installed. Run: pip install 'gspread>=6.0'"
            ) from e

        try:
            self._client = gspread.service_account(filename=self.credentials_file)
        except FileNotFoundError as e:
            raise RuntimeError(
                f"Google credentials file not found: {self.credentials_file}\n"
                f"See README for instructions on creating a service account."
            ) from e

        log.info(f"Connected to Google Sheets (credentials: {self.credentials_file})")

    def _row_for(self, item: Item) -> list[str]:
        return [
            str(item.page),
            str(item.index),
            item.title,
            item.price,
            item.link,
            item.image,
            item.text,
            item.fingerprint,
        ]

    def push(self, items: list[Item]) -> int:
        if not items:
            log.warn("GSheetSink: no items to push")
            return 0

        self._connect()
        if self._client is None:
            raise RuntimeError("Failed to connect to Google Sheets.")

        sheet = self._client.open_by_key(self.sheet_id)

        # Get or create the worksheet
        try:
            ws = sheet.worksheet(self.worksheet)
        except Exception:
            ws = sheet.add_worksheet(
                title=self.worksheet,
                rows=max(len(items) + 100, 1000),
                cols=len(HEADER),
            )

        if self.mode == "replace":
            ws.clear()
            ws.append_row(HEADER)
            ws.append_rows([self._row_for(i) for i in items])
        else:  # append
            # Check if header exists — if sheet is empty, write it
            existing = ws.get_all_values()
            if not existing:
                ws.append_row(HEADER)
            ws.append_rows([self._row_for(i) for i in items])

        log.info(f"GSheetSink: wrote {len(items)} rows → sheet {self.sheet_id} / {self.worksheet}")
        return len(items)

    def close(self) -> None:
        self._client = None