"""OpenRouter LLM fallback for tricky pages.

Used when auto-detection and preset selectors both fail.
Sends the HTML to an LLM and gets back a structured list of items.

Works with OpenRouter's free router (model = "openrouter/free"),
which auto-selects from the currently-available free models.
"""
from __future__ import annotations

import json

from ..config import settings
from . import logging as log

SYSTEM = (
    "You are a web scraping assistant. You receive HTML from a webpage "
    "and extract a list of repeating records (products, listings, articles). "
    "Return ONLY a JSON array of objects. No prose. No markdown fences. "
    "Each object must have exactly these keys: "
    "title (string), price (string), link (string, absolute URL), "
    "image (string, absolute URL), text (string, short description). "
    "If a field is unknown, use an empty string. "
    "Return at most {max_items} items."
)


def _build_payload(html: str, url: str, max_items: int, max_chars: int) -> dict:
    """Construct the OpenRouter request body."""
    trimmed = html[:max_chars]
    return {
        "model": settings.openrouter_model or "openrouter/free",
        "messages": [
            {"role": "system", "content": SYSTEM.replace("{max_items}", str(max_items))},
            {"role": "user", "content": f"URL: {url}\n\nHTML:\n{trimmed}"},
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0,
        "max_tokens": 4096,
    }


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {settings.openrouter_api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/pranromumu/tendem-scraper",
        "X-Title": "Tendem Scraper",
    }


def extract_items_with_llm(
    html: str,
    url: str,
    max_items: int = 100,
    max_chars: int = 60_000,
) -> list[dict]:
    """Ask the LLM to extract items from raw HTML.

    Returns [] on any failure — the pipeline will fall back gracefully.
    """
    if not settings.openrouter_api_key:
        log.warn("LLM extraction skipped — no OpenRouter API key in .env")
        return []

    try:
        import httpx
    except ImportError:
        log.warn("LLM extraction skipped — httpx not installed")
        return []

    payload = _build_payload(html, url, max_items, max_chars)
    log.info(f"LLM extraction: sending {len(html)} chars → {payload['model']}")

    try:
        with httpx.Client(timeout=90) as client:
            r = client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=_headers(),
                json=payload,
            )
            r.raise_for_status()
            data = r.json()
    except Exception as e:
        log.warn(f"LLM request failed: {type(e).__name__}: {e}")
        return []

    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        log.warn("LLM returned unexpected shape — no choices")
        return []

    if not content:
        log.warn("LLM returned empty content")
        return []

    # Strip common LLM artifacts
    content = content.strip()
    if content.startswith("```"):
        # Remove ```json ... ``` fences
        content = content.strip("`")
        if content.lower().startswith("json"):
            content = content[4:].lstrip()

    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as e:
        log.warn(f"LLM returned invalid JSON: {e}")
        return []

    # Normalize to a list
    if isinstance(parsed, dict):
        parsed = parsed.get("items") or parsed.get("data") or []
    if not isinstance(parsed, list):
        log.warn("LLM returned non-list JSON")
        return []

    log.info(f"LLM extraction: got {len(parsed)} items")
    return parsed