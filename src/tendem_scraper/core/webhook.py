"""Notify Slack / Discord when a run finishes. Silent if not configured."""
from __future__ import annotations

import json

import requests

from ..config import settings
from . import logging as log


def _is_discord(url: str) -> bool:
    return "discord.com/api/webhooks" in url


def notify(text: str) -> None:
    url = settings.webhook_url
    if not url:
        return
    try:
        if _is_discord(url):
            payload = {"content": text[:1900]}
        else:
            # Slack-style
            payload = {"text": text[:1900]}
        r = requests.post(url, data=json.dumps(payload),
                          headers={"Content-Type": "application/json"}, timeout=8)
        r.raise_for_status()
        log.info("Webhook notification sent")
    except Exception as e:
        log.warn(f"Webhook failed: {e}")


def notify_done(url: str, items: int, pages: int, secs: float, out_dir: str) -> None:
    text = (f"✅ Scrape finished\nURL: {url}\nPages: {pages}\nItems: {items}\n"
            f"Time: {secs:.1f}s\nOutput: {out_dir}")
    notify(text)


def notify_error(url: str, err: str) -> None:
    notify(f"❌ Scrape failed\nURL: {url}\nError: {err}")