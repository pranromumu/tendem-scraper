"""Persist a browser session (cookies + localStorage) as storage_state.json.

Workflow:
    tendem-scrape URL --interactive --save-session mylogin
        → opens browser, you log in manually, press ENTER, session saved
    tendem-scrape URL --use-session mylogin --render --max-pages 10
        → headless run that reuses the cookies (no login needed)
"""
from __future__ import annotations
from pathlib import Path

from ..config import settings
from . import logging as log


SESSION_DIR = Path(settings.session_dir)


def session_path(name: str) -> Path:
    safe = "".join(c for c in name if c.isalnum() or c in "-_.")
    if not safe:
        raise ValueError("Invalid session name")
    return SESSION_DIR / f"{safe}.json"


def session_exists(name: str) -> bool:
    return session_path(name).exists()


def save_session(page, name: str) -> Path:
    """Given a live Playwright page, dump storage_state to disk."""
    path = session_path(name)
    path.parent.mkdir(parents=True, exist_ok=True)
    page.context.storage_state(path=str(path))
    log.info(f"Session saved → {path}")
    return path


def apply_session(context, name: str) -> None:
    """Load cookies + localStorage into a fresh context."""
    path = session_path(name)
    if not path.exists():
        raise FileNotFoundError(f"Session '{name}' not found at {path}. "
                                f"Create it first with: --interactive --save-session {name}")
    # storage_state is applied via new_context(); we return it from the fetcher
    log.info(f"Reusing session → {path}")


def load_state(name: str) -> dict:
    path = session_path(name)
    if not path.exists():
        raise FileNotFoundError(f"Session '{name}' not found at {path}.")
    import json
    return json.loads(path.read_text(encoding="utf-8"))


def list_sessions() -> list[str]:
    if not SESSION_DIR.exists():
        return []
    return sorted(p.stem for p in SESSION_DIR.glob("*.json"))