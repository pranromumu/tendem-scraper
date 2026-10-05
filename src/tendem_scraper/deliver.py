"""Delivery helper — package a scrape output + generate client email.

Usage:
    tendem-deliver                            # auto: newest report folder
    tendem-deliver <report_dir>               # specific folder
    tendem-deliver <report_dir> --client "Acme Corp"
    tendem-deliver <report_dir> --client "Acme Corp" --no-zip

What it does:
  1. Loads items.csv + qa_issues.csv from the report folder
  2. Runs QA checks (rows, missing fields, duplicates)
  3. Creates deliverable ZIP: deliverables/<client>_<YYYYMMDD>.zip
  4. Prints delivery email (ready to copy-paste)
  5. Prints follow-up email (ready to copy-paste)
"""
from __future__ import annotations

import argparse
import csv
import sys
import zipfile
from collections import Counter
from datetime import datetime
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()


# ------------------------------------------------------------------ helpers

def _find_latest_report() -> Path:
    """Return the newest folder inside ./reports/."""
    reports = Path("reports")
    if not reports.exists():
        console.print("[red]No reports/ folder found. Run a scrape first.[/red]")
        sys.exit(1)
    folders = [p for p in reports.iterdir() if p.is_dir()]
    if not folders:
        console.print("[red]No report folders found inside reports/.[/red]")
        sys.exit(1)
    return max(folders, key=lambda p: p.stat().st_mtime)


def _read_csv_rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _qa_check(report_dir: Path) -> dict:
    """Run QA checks. Returns a dict of results."""
    items_path = report_dir / "items.csv"
    qa_path = report_dir / "qa_issues.csv"

    items = _read_csv_rows(items_path)
    qa_issues = _read_csv_rows(qa_path)

    total = len(items)

    # Missing field counts
    missing_title = sum(1 for i in items if not i.get("title", "").strip())
    missing_price = sum(1 for i in items if not i.get("price", "").strip())
    missing_link = sum(1 for i in items if not i.get("link", "").strip())
    missing_image = sum(1 for i in items if not i.get("image", "").strip())

    # Duplicate fingerprints
    fingerprints = [i.get("fingerprint", "") for i in items if i.get("fingerprint", "")]
    duplicate_fingerprints = sum(
        c - 1 for c in Counter(fingerprints).values() if c > 1
    )

    # High-severity QA
    high_qa = [i for i in qa_issues if (i.get("severity") or "").lower() == "high"]

    return {
        "total": total,
        "missing_title": missing_title,
        "missing_price": missing_price,
        "missing_link": missing_link,
        "missing_image": missing_image,
        "duplicate_fingerprints": duplicate_fingerprints,
        "qa_issues_total": len(qa_issues),
        "qa_issues_high": len(high_qa),
    }


def _package(report_dir: Path, client: str | None, no_zip: bool) -> Path | None:
    """Compress report folder into deliverables/<client>_<date>.zip."""
    if no_zip:
        return None

    deliverables = Path("deliverables")
    deliverables.mkdir(exist_ok=True)

    safe_client = (client or "client").replace(" ", "_").replace("/", "_")
    stamp = datetime.now().strftime("%Y%m%d")
    zip_path = deliverables / f"{safe_client}_{stamp}.zip"

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in report_dir.rglob("*"):
            if f.is_file():
                zf.write(f, arcname=f.relative_to(report_dir))

    return zip_path


# ------------------------------------------------------------------ email builders

DELIVERY_TEMPLATE = """Subject: Your data is ready — {rows} rows

Hi {client},

Your data is ready. Attached: {zipname}

WHAT'S INSIDE:
• items.csv          — main data, open with Excel / Google Sheets
• items.json         — same data in JSON (for developers)
• data.sqlite        — queryable database (for analysts)
• report.html        — double-click to open an interactive dashboard
• qa_issues.csv      — data-quality report
• run_manifest.json  — audit trail (what was scraped, when)

SUMMARY:
• Rows delivered:  {rows}
• Fields:          title, price, link, image
• Date scraped:    {date}
• Data quality:    {qa_summary}

VERIFY IT WORKS:
1. Open report.html — click any column header to sort.
2. Open items.csv in Excel — spot-check 2-3 rows against the live site.

Free revision within 7 days. If anything looks off, just reply.

Best,
{signature}
"""

FOLLOWUP_TEMPLATE = """Subject: Re: Your data — quick check-in

Hi {client},

Just checking in — did you have a chance to look at the data?

If everything looks good, I'll be ready for the next delivery.
If anything needs adjustment, just let me know and I'll fix it.

Also — if you have other sites or data needs in mind, I can often
bundle them at a better rate.

Best,
{signature}
"""


def _qa_summary_text(qa: dict) -> str:
    """Human-readable one-liner for the email."""
    parts = []
    if qa["missing_title"]:
        parts.append(f"{qa['missing_title']} missing titles")
    if qa["missing_price"]:
        parts.append(f"{qa['missing_price']} missing prices")
    if qa["duplicate_fingerprints"]:
        parts.append(f"{qa['duplicate_fingerprints']} duplicates")
    if qa["qa_issues_high"]:
        parts.append(f"{qa['qa_issues_high']} HIGH-severity issues")
    if not parts:
        return "clean — all rows complete, no HIGH-severity issues"
    return "; ".join(parts)


# ------------------------------------------------------------------ main

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="tendem-deliver",
        description="Package a scrape output and generate delivery emails.",
    )
    ap.add_argument("report_dir", nargs="?", help="Report folder (default: newest)")
    ap.add_argument("--client", help="Client name (used in ZIP filename)")
    ap.add_argument("--signature", default="Kabir Hossain",
                    help="Name that signs the emails")
    ap.add_argument("--no-zip", action="store_true",
                    help="Skip ZIP creation (only print emails)")
    ap.add_argument("--no-email", action="store_true",
                    help="Skip email printing (only create ZIP)")
    a = ap.parse_args(argv)

    # 1. Find the report folder
    if a.report_dir:
        report_dir = Path(a.report_dir)
        if not report_dir.is_dir():
            console.print(f"[red]Not a directory: {report_dir}[/red]")
            return 1
    else:
        report_dir = _find_latest_report()

    console.print(Panel.fit(
        f"[bold cyan]Delivery Helper[/bold cyan]\n"
        f"Report folder: [bold]{report_dir}[/bold]",
        border_style="cyan",
    ))

    # 2. QA check
    console.print("\n[cyan]▸ Running QA checks...[/cyan]")
    qa = _qa_check(report_dir)

    qa_table = Table(title="QA Results", show_header=True)
    qa_table.add_column("Check", style="bold")
    qa_table.add_column("Result", justify="right")
    qa_table.add_row("Total rows", str(qa["total"]))
    qa_table.add_row("Missing titles", str(qa["missing_title"]))
    qa_table.add_row("Missing prices", str(qa["missing_price"]))
    qa_table.add_row("Missing links", str(qa["missing_link"]))
    qa_table.add_row("Missing images", str(qa["missing_image"]))
    qa_table.add_row("Duplicate fingerprints", str(qa["duplicate_fingerprints"]))
    qa_table.add_row("QA issues (total)", str(qa["qa_issues_total"]))
    qa_table.add_row("QA issues (HIGH)", str(qa["qa_issues_high"]))
    console.print(qa_table)

    # 3. QA warnings
    if qa["qa_issues_high"]:
        console.print(
            f"\n[red]⚠ {qa['qa_issues_high']} HIGH-severity QA issues found.[/red]\n"
            f"[yellow]Fix before sending, or note them in your email.[/yellow]"
        )
    if qa["missing_title"] > 0 or qa["missing_price"] > 0:
        console.print(
            f"\n[yellow]⚠ Missing fields detected "
            f"(titles: {qa['missing_title']}, prices: {qa['missing_price']}).[/yellow]\n"
            f"[yellow]Consider using --item-selector or a custom POM.[/yellow]"
        )
    if not qa["qa_issues_high"] and not qa["missing_title"] and not qa["missing_price"]:
        console.print("\n[green]✓ QA passed — data looks clean.[/green]")

    # 4. Package
    zip_path = None
    if not a.no_zip:
        console.print("\n[cyan]▸ Packaging ZIP...[/cyan]")
        zip_path = _package(report_dir, a.client, a.no_zip)
        console.print(f"[green]✓ ZIP:[/green] {zip_path}")
    else:
        console.print("\n[dim]▸ ZIP creation skipped (--no-zip)[/dim]")

    # 5. Delivery email
    if not a.no_email:
        zipname = zip_path.name if zip_path else f"{report_dir.name}.zip"
        email = DELIVERY_TEMPLATE.format(
            client=a.client or "there",
            rows=qa["total"],
            zipname=zipname,
            date=datetime.now().strftime("%Y-%m-%d"),
            qa_summary=_qa_summary_text(qa),
            signature=a.signature,
        )
        console.print("\n[bold cyan]═══ Delivery email (copy-paste) ═══[/bold cyan]")
        console.print(Panel(email, border_style="green"))

        followup = FOLLOWUP_TEMPLATE.format(
            client=a.client or "there",
            signature=a.signature,
        )
        console.print("\n[bold cyan]═══ Follow-up email (send in 48h) ═══[/bold cyan]")
        console.print(Panel(followup, border_style="yellow"))

    console.print("\n[green]✓ Done.[/green]")
    return 0


if __name__ == "__main__":
    sys.exit(main())