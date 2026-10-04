"""OpenRouter fallback for tricky pages (optional)."""
from __future__ import annotations

import json

from ..config import settings

SYSTEM = (
    "You extract structured records from raw HTML. "
    "Return ONLY a JSON array of objects with keys: title, price, link, image, text. "
    "If a field is unknown, use an empty string."
)


def extract_items_with_llm(html: str, url: str, max_chars: int = 60_000) -> list[dict]:
    if not settings.openrouter_api_key:
        return []
    try:
        import httpx
    except ImportError:
        return []

    payload = {
        "model": settings.openrouter_model,
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": f"URL: {url}\n\nHTML:\n{html[:max_chars]}"},
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0,
    }
    headers = {
        "Authorization": f"Bearer {settings.openrouter_api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/your-handle/tendem-scraper",
        "X-Title": "Tendem Scraper",
    }
    try:
        with httpx.Client(timeout=60) as c:
            r = c.post("https://openrouter.ai/api/v1/chat/completions",
                       headers=headers, json=payload)
            r.raise_for_status()
            data = r.json()
        content = data["choices"][0]["message"]["content"]
        parsed = json.loads(content)
        return parsed if isinstance(parsed, list) else parsed.get("items", [])
    except Exception:
        return []