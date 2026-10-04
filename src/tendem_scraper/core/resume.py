"""Checkpoint/resume — survives crashes, rate limits, interrupted runs.

Layout:
    reports/scrape_<host>_<ts>/
        _checkpoint.json          ← what pages have been fetched
        pages/page_0001.html      ← raw HTML snapshots (so we can re-parse offline)
        ... regular outputs
"""
from __future__ import annotations
import json
from datetime import datetime
from pathlib import Path


class Checkpoint:
    def __init__(self, out_dir: Path):
        self.out_dir = out_dir
        self.path = out_dir / "_checkpoint.json"
        self.pages_dir = out_dir / "pages"
        self.pages_dir.mkdir(parents=True, exist_ok=True)
        self.state: dict = self._load()

    def _load(self) -> dict:
        if self.path.exists():
            return json.loads(self.path.read_text(encoding="utf-8"))
        return {"started_at": datetime.utcnow().isoformat(),
                "pages_done": [], "seen_urls": [], "next_url": "", "finished": False}

    def save(self) -> None:
        self.path.write_text(json.dumps(self.state, indent=2, default=str), encoding="utf-8")

    def is_done(self, url: str) -> bool:
        return url in self.state["seen_urls"]

    def mark_page(self, pageno: int, url: str, next_url: str | None) -> None:
        self.state["pages_done"].append(pageno)
        self.state["seen_urls"].append(url)
        self.state["next_url"] = next_url or ""
        self.save()

    def finish(self) -> None:
        self.state["finished"] = True
        self.state["finished_at"] = datetime.utcnow().isoformat()
        self.save()

    def snapshot_html(self, pageno: int, html: str) -> Path:
        f = self.pages_dir / f"page_{pageno:04d}.html"
        f.write_text(html, encoding="utf-8")
        return f