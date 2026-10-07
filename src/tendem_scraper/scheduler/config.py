"""Job storage and configuration for the scheduler.

A "scheduled job" is a saved tendem-scrape command that runs on a cron.
Jobs are stored in schedules/jobs.json on disk — no database needed.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, Field

SCHEDULES_DIR = Path("schedules")
JOBS_FILE = SCHEDULES_DIR / "jobs.json"


class ScheduledJob(BaseModel):
    """A single scheduled scraping job."""

    name: str = Field(..., description="Unique job name, e.g. 'acme-weekly'")
    url: str = Field(..., description="Target URL to scrape")
    cron: str = Field(..., description="Cron expression, e.g. '0 8 * * 1' for Monday 8am")
    preset: str = Field("auto", description="CMS preset (auto, shopify, woocommerce, ...)")
    max_pages: int = Field(50, description="Maximum pages to fetch")
    format: str = Field("csv,json,sqlite", description="Output formats (comma-separated)")
    email: str = Field("", description="Client email for delivery")
    crawl: bool = Field(False, description="Use whole-site crawl mode")
    dedupe: bool = Field(True, description="Remove duplicate items")
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    last_run: str = Field("", description="ISO timestamp of last run")
    last_status: str = Field("", description="OK / FAILED")


def load_jobs() -> list[ScheduledJob]:
    """Load all scheduled jobs from disk."""
    if not JOBS_FILE.exists():
        return []
    try:
        raw = json.loads(JOBS_FILE.read_text(encoding="utf-8"))
        return [ScheduledJob(**item) for item in raw]
    except Exception:
        return []


def save_jobs(jobs: list[ScheduledJob]) -> None:
    """Persist all scheduled jobs to disk."""
    SCHEDULES_DIR.mkdir(parents=True, exist_ok=True)
    payload = [j.model_dump() for j in jobs]
    JOBS_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def get_job(name: str) -> ScheduledJob | None:
    """Find a job by name."""
    for j in load_jobs():
        if j.name == name:
            return j
    return None


def upsert_job(job: ScheduledJob) -> None:
    """Add a new job or update an existing one (matched by name)."""
    jobs = load_jobs()
    jobs = [j for j in jobs if j.name != job.name]
    jobs.append(job)
    save_jobs(jobs)


def remove_job(name: str) -> bool:
    """Delete a job by name. Returns True if a job was removed."""
    jobs = load_jobs()
    new = [j for j in jobs if j.name != name]
    if len(new) == len(jobs):
        return False
    save_jobs(new)
    return True