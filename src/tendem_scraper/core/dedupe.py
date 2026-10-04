"""Cross-page deduplication using a stable fingerprint."""
from __future__ import annotations
import hashlib
from urllib.parse import urlparse

from ..models import Item


def _fp(it: Item) -> str:
    """Priority: link → image+title → title+price. Fallback: text hash."""
    if it.link:
        p = urlparse(it.link)
        key = f"{p.netloc}{p.path}"
    elif it.image and it.title:
        key = f"{it.image}|{it.title}"
    elif it.title:
        key = f"{it.title}|{it.price}"
    else:
        key = it.text[:200]
    return hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]


def dedupe_items(items: list[Item]) -> tuple[list[Item], int]:
    """Returns (unique_items, removed_count). Preserves first occurrence order."""
    seen: set[str] = set()
    out: list[Item] = []
    for it in items:
        fp = _fp(it)
        if fp in seen:
            continue
        seen.add(fp)
        it.fingerprint = fp
        out.append(it)
    return out, len(items) - len(out)