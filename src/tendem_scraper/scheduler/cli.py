"""CLI for the scheduler — tendem-schedule command.

Usage:
    tendem-schedule add <name> --url <URL> --cron "0 8 * * 1" [options]
    tendem-schedule list
    tendem-schedule remove <name>
    tendem-schedule run-now <name>
    tendem-schedule daemon
"""
from __future__ import annotations

import argparse
import sys

from rich.console import Console
from rich.table import Table

from .config import ScheduledJob, get_job, load_jobs, remove_job, upsert_job
from .runner import run_daemon, run_job

console = Console()


def cmd_add(args) -> int:
    """Add a new scheduled job."""
    existing = get_job(args.name)
    if existing and not args.force:
        console.print(f"[yellow]Job '{args.name}' already exists.[/yellow]")
        console.print("Use [bold]--force[/bold] to overwrite.")
        return 1

    job = ScheduledJob(
        name=args.name,
        url=args.url,
        cron=args.cron,
        preset=args.preset,
        max_pages=args.max_pages,
        format=args.format,
        email=args.email or "",
        crawl=args.crawl,
        dedupe=not args.no_dedupe,
    )
    upsert_job(job)

    console.print(f"[green]✓[/green] Scheduled job created: [bold]{args.name}[/bold]")
    console.print(f"  URL:   {args.url}")
    console.print(f"  Cron:  {args.cron}")
    console.print(f"  Preset: {args.preset}")
    console.print()
    console.print("[dim]Start the daemon to activate:[/dim] [bold]tendem-schedule daemon[/bold]")
    return 0


def cmd_list(args) -> int:
    """List all scheduled jobs."""
    jobs = load_jobs()
    if not jobs:
        console.print("[yellow]No scheduled jobs yet.[/yellow]")
        console.print('Add one with: [bold]tendem-schedule add myshop --url URL --cron "0 8 * * 1"[/bold]')
        return 0

    table = Table(title=f"Scheduled jobs ({len(jobs)})")
    table.add_column("Name", style="cyan")
    table.add_column("Cron")
    table.add_column("Preset")
    table.add_column("URL")
    table.add_column("Last run")
    table.add_column("Status")

    for j in jobs:
        status_color = "green" if j.last_status == "OK" else ("red" if j.last_status else "dim")
        table.add_row(
            j.name,
            j.cron,
            j.preset,
            j.url[:50] + ("..." if len(j.url) > 50 else ""),
            j.last_run[:19] if j.last_run else "—",
            f"[{status_color}]{j.last_status or 'never run'}[/{status_color}]",
        )
    console.print(table)
    return 0


def cmd_remove(args) -> int:
    """Remove a scheduled job."""
    if remove_job(args.name):
        console.print(f"[green]✓[/green] Removed job '{args.name}'")
        return 0
    console.print(f"[red]No job named '{args.name}'[/red]")
    return 1


def cmd_run_now(args) -> int:
    """Run a scheduled job immediately (for testing)."""
    return run_job(args.name)


def cmd_daemon(args) -> int:
    """Start the scheduler daemon (blocking)."""
    run_daemon()
    return 0


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="tendem-schedule",
        description="Schedule recurring scrape jobs on a cron.",
    )
    sub = ap.add_subparsers(dest="command", required=True)

    # add
    p_add = sub.add_parser("add", help="Create or update a scheduled job")
    p_add.add_argument("name", help="Unique job name (e.g. acme-weekly)")
    p_add.add_argument("--url", required=True, help="Target URL")
    p_add.add_argument("--cron", required=True,
                       help="Cron expression, e.g. '0 8 * * 1' for Monday 8am")
    p_add.add_argument("--preset", default="auto",
                       help="CMS preset (auto, shopify, woocommerce, ...)")
    p_add.add_argument("--max-pages", type=int, default=50)
    p_add.add_argument("--format", default="csv,json,sqlite")
    p_add.add_argument("--email", help="Client email for delivery")
    p_add.add_argument("--crawl", action="store_true", help="Whole-site crawl")
    p_add.add_argument("--no-dedupe", action="store_true")
    p_add.add_argument("--force", action="store_true", help="Overwrite if exists")
    p_add.set_defaults(func=cmd_add)

    # list
    p_list = sub.add_parser("list", help="List scheduled jobs")
    p_list.set_defaults(func=cmd_list)

    # remove
    p_remove = sub.add_parser("remove", help="Delete a scheduled job")
    p_remove.add_argument("name")
    p_remove.set_defaults(func=cmd_remove)

    # run-now
    p_run = sub.add_parser("run-now", help="Run a job immediately")
    p_run.add_argument("name")
    p_run.set_defaults(func=cmd_run_now)

    # daemon
    p_daemon = sub.add_parser("daemon", help="Start the scheduler daemon (blocking)")
    p_daemon.set_defaults(func=cmd_daemon)

    return ap


def main(argv: list[str] | None = None) -> int:
    ap = build_parser()
    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())