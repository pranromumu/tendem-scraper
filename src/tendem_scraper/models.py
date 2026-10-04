"""Pydantic domain models — single source of truth for every row."""
from __future__ import annotations
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field


class Item(BaseModel):
    page: int
    index: int
    title: str = ""
    price: str = ""
    link: str = ""
    image: str = ""
    text: str = ""
    # NEW: fingerprint used for --dedupe
    fingerprint: str = ""


class LinkRow(BaseModel):
    page: int
    text: str = ""
    href: str
    type: Literal["internal", "external", "mailto", "tel", "anchor", "javascript"]
    status: str = ""
    detail: str = ""


class ImageRow(BaseModel):
    page: int
    src: str
    alt: str = ""
    alt_state: Literal["ok", "empty", "missing"]
    width: str = ""
    height: str = ""


class HeadingRow(BaseModel):
    page: int
    level: int = Field(ge=1, le=6)
    text: str


class TableBlock(BaseModel):
    page: int
    caption: str = ""
    header: list[str]
    rows: list[list[str]]


class QAIssue(BaseModel):
    page: int | str = ""
    severity: Literal["High", "Medium", "Low"]
    check: str
    detail: str
    where: str = ""


class RunMeta(BaseModel):
    url: str
    host: str
    when: datetime
    method: str
    secs: float
    pages: int
    checked: int = 0
    selector: str = ""
    preset: str = ""
    session: str = ""
    mode: str = "single"                 # single | crawl
    crawled_urls: int = 0
    deduped_items: int = 0
    concurrency: int = 1
    strict: bool = False
    resumed_from: str = ""


class RunManifest(BaseModel):
    """Auditable record for the client — lives next to the outputs."""
    meta: RunMeta
    counts: dict[str, int]
    schema_version: str = "2.0"
    files: list[str] = Field(default_factory=list)