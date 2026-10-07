"""Run scheduled jobs on cron using APScheduler.

Two ways to use this:
  1. Short run  — `run_job(name)` to trigger a single job now.
  2. Daemon     — `run_daemon()` blocks and executes jobs on their schedule.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from ..config import settings
from ..core import logging as log
from ..core.fetcher import Fetcher
from ..pages.registry import PAGE_REGISTRY
from .config import ScheduledJob, get_job, load_jobs, upsert_job


def _job_kwargs_for(job: ScheduledJob) -> dict:
    """Build the argparse-like namespace that the pipeline expects."""
    class Args:
        url = job.url
        crawl = job.crawl
        crawl_max = 200
        max_pages = job.max_pages
        delay = None
        concurrency = 4
        static = False
        render = False
        interactive = False
        scroll = False
        infinite = False
        infinite_max = 30
        item_selector = None
        preset = job.preset
        page_object = None
        check_links = 0
        external = False
        ignore_robots = False
        proxy = None
        save_session = None
        use_session = None
        format = job.format
        outdir = settings.outdir
        resume = None
        s3 = False
        webhook = None
        open = False
        json_logs = False
        codegen = False
        dedupe = job.dedupe
        validate = False

    return {"a": Args()}


def run_job(name: str) -> int:
    """Execute a single scheduled job by name. Returns exit code."""
    job = get_job(name)
    if not job:
        log.fail(f"No scheduled job named '{name}'")
        return 1

    log.stage(f"scheduled job: {name}", job.url)
    log.metric("cron", job.cron)
    log.metric("preset", job.preset)


    # Page class defaults to GenericListingPage unless a preset overrides
    page_cls = PAGE_REGISTRY["listing"]
    preset_name = job.preset
    from ..core.presets import get_preset
    preset = get_preset(preset_name) if preset_name and preset_name != "auto" else None
    page_kwargs = {"item_selector": None, "preset": preset}

    # Fetch using the same Fetcher as the CLI
    fetcher = Fetcher(mode="auto", scroll=False)

    try:
        from ..core.pipeline import Pipeline
        result = Pipeline(
            fetcher=fetcher,
            page_cls=page_cls,
            page_kwargs=page_kwargs,
            max_pages=job.max_pages,
            delay=None,
            ignore_robots=False,
        ).run(job.url)
    except Exception as e:
        log.fail(f"Job '{name}' failed: {e}")
        job.last_run = datetime.utcnow().isoformat()
        job.last_status = f"FAILED: {type(e).__name__}"
        upsert_job(job)
        return 1
    finally:
        fetcher.close()

    # Write output using the same exporter as the CLI
    from ..core.exporters import export_all, write_manifest
    from ..core.reporter import write_html_report
    from ..models import RunMeta

    host = job.url.split("//")[-1].split("/")[0]
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = Path(settings.outdir) / f"scrape_{host}_{stamp}"
    out_dir.mkdir(parents=True, exist_ok=True)

    meta = RunMeta(
        url=job.url,
        host=host,
        when=datetime.now(),
        method=result.pages[0].method if result.pages else "scheduled",
        secs=0.0,
        pages=len(result.pages),
        selector=result.pages[0].selector if result.pages else "",
        preset=job.preset,
        mode="crawl" if job.crawl else "single",
    )

    formats = {f.strip() for f in job.format.split(",") if f.strip()}
    export_all(out_dir, result, meta, formats)
    write_html_report(out_dir, result, meta)

    counts = {
        "pages": len(result.pages),
        "items": len(result.items),
        "links": len(result.links),
        "images": len(result.images),
        "tables": len(result.tables),
        "qa_issues": len(result.issues),
    }
    write_manifest(out_dir, meta, counts)

    log.info(f"Job '{name}' finished — {len(result.items)} items → {out_dir}")

    # Update job record
    job.last_run = datetime.utcnow().isoformat()
    job.last_status = "OK"
    upsert_job(job)

    return 0


def run_daemon() -> None:
    """Block and run jobs on their cron schedule until Ctrl+C."""
    jobs = load_jobs()
    if not jobs:
        log.warn("No scheduled jobs found. Add one with: tendem-schedule add ...")
        return

    scheduler = BlockingScheduler()

    for job in jobs:
        try:
            trigger = CronTrigger.from_crontab(job.cron)
        except ValueError as e:
            log.fail(f"Invalid cron for job '{job.name}': {e}")
            continue

        scheduler.add_job(
            run_job,
            trigger=trigger,
            args=[job.name],
            id=job.name,
            name=job.name,
            replace_existing=True,
            misfire_grace_time=3600,  # 1 hour
        )
        log.info(f"Scheduled '{job.name}' → {job.cron}")

    log.stage("daemon", f"Running {len(jobs)} job(s). Ctrl+C to stop.")
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        log.info("Scheduler stopped.")


if __name__ == "__main__":
    run_daemon()