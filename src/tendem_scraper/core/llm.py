"""Google Gemini LLM fallback for tricky pages.

Used when auto-detection and preset selectors both fail.
Sends the HTML to Gemini and gets back a structured list of items.

Uses Google AI Studio (free tier: 1,500 requests/day).
Model: gemini-3.5-flash (stable, fast, JSON-capable).
"""
from __future__ import annotations

import json

from ..config import settings
from . import logging as log

GEMINI_ENDPOINT = (
    "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
)

SYSTEM_PROMPT = (
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
    """Construct the Gemini request body."""
    trimmed = html[:max_chars]
    prompt = (
        f"{SYSTEM_PROMPT.replace('{max_items}', str(max_items))}\n\n"
        f"URL: {url}\n\nHTML:\n{trimmed}"
    )
    return {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0,
            "maxOutputTokens": 8192,
            "responseMimeType": "application/json",
        },
    }


def _extract_text(data: dict) -> str:
    """Pull text out of a Gemini response."""
    try:
        candidates = data.get("candidates") or []
        if not candidates:
            return ""
        parts = candidates[0].get("content", {}).get("parts") or []
        if not parts:
            return ""
        return parts[0].get("text", "") or ""
    except (KeyError, IndexError, TypeError):
        return ""


def _strip_json_fences(content: str) -> str:
    """Remove ```json ... ``` fences if present."""
    content = content.strip()
    if content.startswith("```"):
        content = content.strip("`")
        if content.lower().startswith("json"):
            content = content[4:].lstrip()
    return content


def extract_items_with_llm(
    html: str,
    url: str,
    max_items: int = 100,
    max_chars: int = 60_000,
) -> list[dict]:
    """Ask Gemini to extract items from raw HTML.

    Returns [] on any failure — the pipeline will fall back gracefully.
    """
    if not settings.openrouter_api_key:
        log.warn("LLM extraction skipped — no API key in .env")
        return []

    model = settings.openrouter_model or "gemini-3.5-flash"

    try:
        import httpx
    except ImportError:
        log.warn("LLM extraction skipped — httpx not installed")
        return []

    endpoint = GEMINI_ENDPOINT.format(model=model)
    payload = _build_payload(html, url, max_items, max_chars)
    log.info(f"LLM extraction: sending {len(html)} chars → Gemini/{model}")

    # Retry up to 3 times on 503 (Google busy) or timeout
    for attempt in range(3):
        try:
            with httpx.Client(timeout=90) as client:
                r = client.post(endpoint, params={"key": settings.openrouter_api_key}, json=payload)
            if r.status_code == 200:
                break
            if r.status_code in (503, 429):
                log.warn(f"Gemini busy ({r.status_code}), retrying...")
                import time
                time.sleep(3)
                continue
            log.warn(f"Gemini error {r.status_code}: {r.text[:200]}")
            return []
        except Exception as e:
            log.warn(f"Gemini request failed ({type(e).__name__}), attempt {attempt + 1}/3")
            import time
            time.sleep(3)
    else:
        log.warn("Gemini failed after 3 attempts")
        return []

    content = _extract_text(r.json())
    if not content:
        log.warn("Gemini returned empty content")
        return []

    content = _strip_json_fences(content)
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as e:
        log.warn(f"Gemini returned invalid JSON: {e}")
        return []

    if isinstance(parsed, dict):
        parsed = parsed.get("items") or parsed.get("data") or []
    if not isinstance(parsed, list):
        log.warn("Gemini returned non-list JSON")
        return []

    log.info(f"LLM extraction: got {len(parsed)} items")
    return parsed