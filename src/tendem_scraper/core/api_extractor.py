"""JSON API mode — extract items from JSON endpoints directly.

Some sites expose their data via JSON APIs (better than scraping HTML).
This module handles:
  - Fetching the JSON
  - Navigating the JSON tree (dot notation or [*] arrays)
  - Mapping arbitrary field names to the standard Item model
  - Auto-detecting fields when the mapping isn't given

Example:
    items = extract_items_from_json(
        data,
        json_path="data.products[*]",
        field_map={"title": "name", "price": "cost"},
    )
"""
from __future__ import annotations

import json
from typing import Any

from ..models import Item


def parse_json_path(data: Any, path: str) -> list[Any]:
    """Navigate a JSON structure using dot/bracket notation.

    Examples:
        "products"           → data["products"]
        "data.items"         → data["data"]["items"]
        "data.products[*]"   → each element of data["data"]["products"]

    Returns a list of the leaf values (wrapped in a list if single).
    Empty data or empty path returns [].
    """
    # Empty / falsy data → no items
    if not data:
        return []

    if not path:
        # No path → assume data is already the list
        return data if isinstance(data, list) else [data]

    # Split path on dots, but keep [*] markers
    parts: list[str] = []
    for p in path.split("."):
        # Split "products[*]" into "products" + "*"
        if "[*]" in p:
            head = p.replace("[*]", "")
            if head:
                parts.append(head)
            parts.append("*")
        else:
            parts.append(p)

    current: Any = data
    for part in parts:
        if part == "*":
            if not isinstance(current, list):
                return []
            # Flatten: return each element
            return list(current)
        if isinstance(current, dict):
            current = current.get(part)
            if current is None:
                return []
        elif isinstance(current, list):
            # Apply remaining path to each element
            results = []
            for el in current:
                sub = el.get(part) if isinstance(el, dict) else None
                if sub is not None:
                    results.append(sub)
            return results
        else:
            return []

    return current if isinstance(current, list) else [current]


def auto_detect_field_map(sample: dict) -> dict[str, str]:
    """Guess which JSON keys map to Item fields.

    Looks for common names: title/name, price/cost, url/link, image/img.
    """
    keys = {k.lower(): k for k in sample.keys()}

    def pick(*candidates: str) -> str:
        for c in candidates:
            if c in keys:
                return keys[c]
        return ""

    return {
        "title": pick("title", "name", "product_name", "heading", "headline"),
        "price": pick("price", "cost", "amount", "value"),
        "link": pick("url", "link", "href", "permalink"),
        "image": pick("image", "img", "image_url", "thumbnail", "photo"),
        "text": pick("description", "text", "summary", "body", "content"),
    }


def _get_by_path(obj: dict, dotted_key: str) -> str:
    """Navigate nested dicts using dot notation: 'a.b.c' → obj['a']['b']['c']."""
    if not dotted_key:
        return ""
    current: Any = obj
    for part in dotted_key.split("."):
        if isinstance(current, dict):
            current = current.get(part, "")
        else:
            return ""
    return str(current) if current is not None else ""


def extract_items_from_json(
    data: Any,
    json_path: str = "",
    field_map: dict[str, str] | None = None,
    max_items: int = 1000,
) -> list[Item]:
    """Turn a JSON response into a list of Item objects.

    Args:
        data: The parsed JSON (list or dict).
        json_path: Where in the JSON the list of items lives.
        field_map: Which JSON keys map to Item fields. Auto-detected if None.
        max_items: Cap on items to return.

    Returns:
        List of Item objects. Empty if extraction fails.
    """
    rows = parse_json_path(data, json_path)
    rows = [r for r in rows if isinstance(r, dict)]
    if not rows:
        return []

    if field_map is None:
        field_map = auto_detect_field_map(rows[0])

    items: list[Item] = []
    for i, row in enumerate(rows[:max_items], 1):
        items.append(Item(
            page=1,
            index=i,
            title=_get_by_path(row, field_map.get("title", ""))[:200],
            price=_get_by_path(row, field_map.get("price", ""))[:50],
            link=_get_by_path(row, field_map.get("link", ""))[:500],
            image=_get_by_path(row, field_map.get("image", ""))[:500],
            text=_get_by_path(row, field_map.get("text", ""))[:400],
        ))
    return items


def try_parse_json(text: str) -> Any:
    """Return parsed JSON or None."""
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return None