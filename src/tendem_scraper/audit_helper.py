"""Interactive audit helper — guides you from client URL → verdict → next command.

Usage:
    tendem-audit
    # or
    python -m tendem_scraper.audit_helper
"""
from __future__ import annotations

import sys

from bs4 import BeautifulSoup
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt

from .core.extractors import find_item_groups
from .core.fetcher import Fetcher, FetchError
from .core.fingerprint import detect_preset

console = Console()


# Known anti-bot domains — always flag as HARD so you don't quote $60 for a 4-hour fight
BLOCKED_HINTS = (
    "amazon.",
    "linkedin.com",
    "facebook.com",
    "instagram.com",
    "twitter.com",
    "x.com",
    "tiktok.com",
    "zillow.com",
    "booking.com",
    "airbnb.com",
    "tripadvisor.com",
    "yelp.com",
    "glassdoor.com",
    "indeed.com",
    "craigslist.org",
    "walmart.com",
    "target.com",
    "ebay.com",
)


def _banner() -> None:
    console.print(Panel.fit(
        "[bold cyan]Tendem Audit Helper[/bold cyan]\n"
        "Follow the prompts. I'll tell you: [green]accept[/green] / "
        "[yellow]caution[/yellow] / [red]decline[/red], plus the price.",
        border_style="cyan",
    ))


def _ask_url() -> str:
    url = Prompt.ask("[bold]Client URL[/bold]").strip()
    if not url.startswith(("http://", "https://")):
        console.print("[red]URL must start with http:// or https://[/red]")
        sys.exit(1)
    return url


def _fetch_probe(url: str) -> tuple[str, str, str]:
    """Fetch the URL with the tool's own adaptive fetcher (static → playwright)."""
    fetcher = Fetcher(mode="auto", scroll=False)
    try:
        html, final, method = fetcher.get(url)
    except FetchError as e:
        console.print(f"[red]Fetch failed:[/red] {e}")
        sys.exit(1)
    finally:
        fetcher.close()
    return html, final, method


def _check_robots(url: str) -> tuple[bool, str]:
    """Return (allowed, reason)."""
    from urllib import robotparser
    from urllib.parse import urlparse

    import requests

    p = urlparse(url)
    base = f"{p.scheme}://{p.netloc}"
    rp = robotparser.RobotFileParser()
    try:
        r = requests.get(
            base + "/robots.txt",
            timeout=10,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        if r.status_code == 200:
            rp.parse(r.text.splitlines())
            allowed = rp.can_fetch("*", url)
            return (
                allowed,
                "robots.txt allows this path"
                if allowed
                else "robots.txt DISALLOWS this path",
            )
        return True, f"no robots.txt (HTTP {r.status_code}) — assume allowed"
    except requests.RequestException as e:
        return True, f"robots.txt fetch failed ({type(e).__name__}) — assume allowed"


def _is_known_hard(url: str) -> tuple[bool, str]:
    """Return (is_hard, reason). Detects famous anti-bot domains."""
    low = url.lower()
    for hint in BLOCKED_HINTS:
        if hint in low:
            clean = hint.rstrip(".")
            return True, f"known anti-bot site ({clean})"
    return False, ""


def _analyze(html: str, url: str, method: str) -> dict:
    """Extract signals used for verdict."""
    soup = BeautifulSoup(html, "lxml")

    # Auto-detection of repeating blocks
    try:
        groups = find_item_groups(soup, min_items=3)
    except Exception:
        groups = []

    auto_items = len(groups[0]["items"]) if groups else 0
    auto_selector = groups[0]["selector"] if groups else ""

    # Fallback selectors — SPECIFIC, tested ones only (no generic `tr` / `div`)
    common_selectors = [
        # Site-specific (safe)
        "tr.athing",              # Hacker News
        "li.product",             # WooCommerce
        ".product-card",          # Shopify
        "article.product_pod",    # books.toscrape.com
        ".product-item",          # Magento
        "article.card",           # generic card
        "div.card",               # generic card
        "li.card",                # generic card list
        "div[class*='product']",  # anything with "product" in class
        "div[class*='item']",     # anything with "item" in class
    ]

    fallback_selector = ""
    fallback_count = 0
    for sel in common_selectors:
        try:
            n = len(soup.select(sel))
            if n > fallback_count:
                fallback_count = n
                fallback_selector = sel
        except Exception:
            pass

    # Fingerprint the CMS
    preset, score = detect_preset(html)

    # Pagination hints
    has_next = bool(
        soup.select_one('a[rel~="next"]')
        or soup.find(
            "a",
            string=lambda t: t and t.strip().lower() in ("next", "next page", "more"),
        )
    )

    # Login walls
    has_login = bool(
        soup.find("input", attrs={"type": "password"})
        or soup.find("form", action=lambda a: a and "login" in a.lower())
    )

    # Captcha
    has_captcha = bool(
        soup.find("iframe", src=lambda s: s and "recaptcha" in s.lower())
        or soup.find(
            attrs={"class": lambda c: c and "captcha" in c.lower() if c else False}
        )
    )

    return {
        "auto_items": auto_items,
        "auto_selector": auto_selector,
        "fallback_items": fallback_count,
        "fallback_selector": fallback_selector,
        "preset": preset,
        "preset_score": score,
        "has_next": has_next,
        "has_login": has_login,
        "has_captcha": has_captcha,
    }


def _verdict(signals: dict, robots_allowed: bool, url: str) -> tuple[str, str, str]:
    """Return (verdict_emoji, verdict_label, reason)."""
    if not robots_allowed:
        return "🔴", "DECLINE", "robots.txt disallows this path"

    # Known anti-bot domains — always HARD, never trust auto-detect
    hard, why = _is_known_hard(url)
    if hard:
        return (
            "🟠",
            "HARD",
            f"{why} — expected to block scraping after a few pages",
        )

    if signals["has_captcha"]:
        return "🔴", "DECLINE", "site uses CAPTCHA — unreliable to scrape"

    if signals["auto_items"] >= 10:
        return (
            "🟢",
            "EASY",
            f"auto-detected {signals['auto_items']} items in the card block",
        )

    if signals["fallback_items"] >= 10:
        return (
            "🟡",
            "MEDIUM",
            f"auto-detect failed but `{signals['fallback_selector']}` "
            f"returns {signals['fallback_items']} items",
        )

    if signals["has_login"]:
        return "🟠", "HARD", "login-walled — needs --interactive --save-session"

    return "🟠", "HARD", "could not find repeating items with common selectors"


def _next_command(url: str, signals: dict, verdict_label: str) -> str:
    """The exact command the user should run next."""
    if verdict_label == "EASY":
        return (
            f'tendem-scrape "{url}" --max-pages 50 '
            f"--format csv,json,sqlite --open"
        )
    if verdict_label == "MEDIUM":
        sel = signals["fallback_selector"] or signals["auto_selector"]
        if sel:
            return (
                f'tendem-scrape "{url}" --item-selector "{sel}" '
                f"--max-pages 50 --format csv,json,sqlite --open"
            )
        return (
            f'tendem-scrape "{url}" --render --scroll '
            f"--max-pages 50 --format csv,json,sqlite --open"
        )
    if verdict_label == "HARD":
        if signals["has_login"]:
            return (
                f'tendem-scrape "{url}" --interactive --save-session clientname\n'
                f'tendem-scrape "{url}" --use-session clientname --max-pages 50'
            )
        return f'tendem-scrape "{url}" --render --scroll --crawl --crawl-max 20'
    return "# Decline politely. See intake_reply.txt for the template."


def _price(verdict_label: str) -> str:
    if verdict_label == "EASY":
        return "$60/month (Starter)"
    if verdict_label == "MEDIUM":
        return "$120/month (Standard)"
    if verdict_label == "HARD":
        return "$250+/month — accept only if budget allows"
    return "—"


def main() -> int:
    _banner()
    url = _ask_url()

    console.print(f"\n[cyan]▸ Auditing[/cyan] {url}")
    console.print("[dim]  (fetching page + checking robots.txt...)[/dim]")

    html, final_url, method = _fetch_probe(url)
    robots_allowed, robots_reason = _check_robots(final_url)

    console.print(f"  method:      [bold]{method}[/bold]")
    console.print(f"  robots.txt:  {robots_reason}")

    signals = _analyze(html, final_url, method)

    if signals["auto_items"] < 10 and signals["fallback_items"] >= 10:
        console.print(
            f"\n[yellow]Auto-detect found nothing, but selector "
            f"`{signals['fallback_selector']}` gives "
            f"{signals['fallback_items']} items.[/yellow]"
        )

    emoji, label, reason = _verdict(signals, robots_allowed, final_url)

    console.print()
    console.print(
        Panel(
            f"{emoji}  [bold]{label}[/bold]\n\n"
            f"[dim]Reason:[/dim]  {reason}\n"
            f"[dim]Preset:[/dim]  {signals['preset']} (score {signals['preset_score']})\n"
            f"[dim]Next step:[/dim] [bold]{label}[/bold]",
            title="Verdict",
            border_style=(
                "green" if label == "EASY" else ("yellow" if label == "MEDIUM" else "red")
            ),
        )
    )

    if label == "HARD":
        console.print(
            "\n[yellow]⚠ Reminder:[/yellow] run a small test scrape "
            "(--max-pages 2) before quoting. Some sites look fine but block on page 3+."
        )

    console.print("\n[bold cyan]Suggested price[/bold cyan]")
    console.print(f"  {_price(label)}")

    console.print("\n[bold cyan]Next command[/bold cyan]")
    console.print(f"  [bold]{_next_command(url, signals, label)}[/bold]")

    console.print()

    if label in ("EASY", "MEDIUM"):
        if Confirm.ask(
            "[green]Accept this job and run the scrape now?[/green]", default=False
        ):
            cmd = _next_command(url, signals, label)
            console.print(f"\n[cyan]Run this:[/cyan]\n  {cmd}\n")
    else:
        console.print(
            "[red]Recommendation:[/red] Decline politely. "
            "See intake_reply.txt for the template."
        )

    console.print()
    return 0


if __name__ == "__main__":
    sys.exit(main())