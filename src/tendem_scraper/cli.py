#!/usr/bin/env python3
"""
Tendem-scraper v2.0.0 — production CLI.

Real-world examples
-------------------
# just paste a URL — auto-preset + auto-detect
tendem-scrape https://any-shop.com/products --max-pages 5 --open

# unknown platform → fingerprint detection
tendem-scrape URL --preset auto --max-pages 3

# whole-site crawl (BFS, same host, robots-respected)
tendem-scrape URL --crawl --crawl-max 200 --concurrency 8 --format csv,json,sqlite

# log in once, then reuse headlessly
tendem-scrape URL/login --interactive --save-session mysite
tendem-scrape URL/orders --use-session mysite --max-pages 10

# resume an interrupted crawl
tendem-scrape URL --crawl --resume reports/scrape_host_20250115_120000

# dedupe + strict validation + S3 upload + Slack notify
tendem-scrape URL --crawl --dedupe --validate --s3 --webhook https://hooks.slack.com/...

# LLM fallback when no items can be detected
tendem-scrape URL --llm --max-pages 3

# print a POM skeleton
tendem-scrape URL --codegen
"""
from __future__ import annotations

import argparse
import re
import sys
import time
import webbrowser
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import requests
from rich.console import Console
from rich.table import Table

from .config import settings
from .core import logging as log
from .core import session as session_mod
from .core import storage, webhook
from .core.allure_hooks import allure_step, attach_csv, attach_html, attach_json
from .core.concurrency import map_concurrent  # noqa: F401  (kept for future crawl parallelism)
from .core.crawler import crawl_urls
from .core.dedupe import dedupe_items
from .core.exporters import export_all, write_manifest
from .core.fetcher import UA, Fetcher, FetchError
from .core.fingerprint import detect_preset
from .core.pipeline import Pipeline
from .core.presets import get_preset, list_presets
from .core.reporter import write_html_report
from .core.resume import Checkpoint
from .models import QAIssue, RunMeta
from .pages.registry import PAGE_REGISTRY
from .sinks.gsheet_sink import GSheetSink

# Global start-time so _finalise() can compute elapsed seconds even before main() resets it.
_T0 = time.time()


# ------------------------------------------------------------------ link check
def _check_links(urls: list[str], workers: int = 8) -> dict[str, tuple[str, str]]:
    def one(u: str):
        h = {"User-Agent": UA}
        try:
            r = requests.head(u, headers=h, timeout=10, allow_redirects=True)
            if r.status_code >= 400:
                r = requests.get(u, headers=h, timeout=10, stream=True, allow_redirects=True)
                r.close()
            c = r.status_code
        except requests.RequestException as ex:
            return u, "ERROR", type(ex).__name__
        if c < 400:
            return u, "OK", str(c)
        if c in (401, 403, 429, 999):
            return u, "RESTRICTED", str(c)
        return u, "BROKEN", str(c)

    with ThreadPoolExecutor(max_workers=workers) as ex:
        return {u: (s, d) for u, s, d in ex.map(one, urls)}


# ------------------------------------------------------------------ codegen
def _codegen_skeleton(page) -> str:
    sel = page.selector or ".your-card-selector"
    return f"""
# Auto-generated POM skeleton — paste into src/tendem_scraper/pages/mysite.py
# Then register in pages/registry.py:  "mysite": MySiteListing

from __future__ import annotations
from urllib.parse import urljoin
from .base_page import BasePage
from ..core.extractors import clean, PRICE
from ..models import Item


class MySiteListing(BasePage):
    name = "mysite"
    CARD_SEL = "{sel}"

    def _parse_items(self) -> None:
        self.selector = self.CARD_SEL
        for i, n in enumerate(self.soup.select(self.CARD_SEL), 1):
            a = n.select_one("a")
            price_el = n.select_one('[class*="price" i]')
            m = PRICE.search(clean(price_el.get_text(" ")) if price_el else "")
            img = n.select_one("img")
            self.items.append(Item(
                page=self.pageno, index=i,
                title=clean(a.get_text(" ")) if a else "",
                price=m.group(0).strip() if m else "",
                link=urljoin(self.final_url, a["href"]) if a and a.get("href") else "",
                image=urljoin(self.final_url, img["src"]) if img and img.get("src") else "",
                text=clean(" ".join(n.stripped_strings))[:400],
            ))
"""


# ------------------------------------------------------------------ parser
def _build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="tendem-scrape",
        description=(
            "POM scraper v2 — auto-presets, crawl, concurrency, resume, "
            "dedupe, multi-format, Allure, LLM fallback."
        ),
    )
    ap.add_argument("url", help="URL or local .html file")

    m = ap.add_mutually_exclusive_group()
    m.add_argument("--static", action="store_true")
    m.add_argument("--render", action="store_true")
    m.add_argument("--interactive", action="store_true")

    # pagination / crawl
    ap.add_argument("--max-pages", type=int, default=1, help="paginate N pages (single-mode)")
    ap.add_argument("--delay", type=float, default=None)
    ap.add_argument("--crawl", action="store_true", help="BFS-crawl same host from the seed")
    ap.add_argument("--crawl-max", type=int, default=settings.crawl_max_pages)
    ap.add_argument("--concurrency", type=int, default=settings.concurrency)

    # parsing
    ap.add_argument("--item-selector", help="CSS of repeating blocks (overrides preset)")
    ap.add_argument("--preset", default=None,
                    help=f"preset name, or 'auto' for fingerprint detection. one of: auto,{','.join(list_presets())}")
    ap.add_argument("--page-object", choices=sorted(PAGE_REGISTRY.keys()), default=None)

    # behaviour
    ap.add_argument("--scroll", action="store_true")
    ap.add_argument("--infinite", action="store_true")
    ap.add_argument("--infinite-max", type=int, default=30)
    ap.add_argument("--dedupe", action="store_true", help="drop duplicate items across pages")
    ap.add_argument("--llm", action="store_true",
                    help="use OpenRouter LLM fallback when no items are found")
    ap.add_argument("--validate", action="store_true",
                    help="strict mode: exit non-zero if any High-severity QA issue")
    ap.add_argument("--check-links", nargs="?", const=40, type=int, default=0, metavar="N")
    ap.add_argument("--external", action="store_true")
    ap.add_argument("--ignore-robots", action="store_true")
    ap.add_argument("--proxy")

    # sessions
    ap.add_argument("--save-session", metavar="NAME")
    ap.add_argument("--use-session", metavar="NAME")
    ap.add_argument("--list-sessions", action="store_true")

    # output
    ap.add_argument("--format", default="csv",
                    help="comma-separated: csv,json,jsonl,sqlite (default: csv)")
    ap.add_argument("--sink", action="append", default=[],
                    choices=["gsheet", "s3"],
                    help="push results to a sink (repeatable): gsheet, s3")
        # API mode
    ap.add_argument("--api-mode", action="store_true",
                    help="treat the URL as a JSON API endpoint instead of HTML")
    ap.add_argument("--api-path", default="",
                    help="path inside JSON to item list (e.g. 'data.products[*]')")
    ap.add_argument("--field-map", default="",
                    help="comma-separated field mapping: title=name,price=cost")
    ap.add_argument("--header", action="append", default=[],
                    help="custom HTTP header (repeatable): 'Authorization: Bearer X'")
    ap.add_argument("--sheet-id", help="Google Sheet ID (with --sink gsheet)")
    ap.add_argument("--sheet-name", default="items",
                    help="Worksheet name inside the Google Sheet (default: items)")
    ap.add_argument("--sheet-mode", choices=["replace", "append"], default="replace",
                    help="Whether to replace or append to the sheet (default: replace)")
    ap.add_argument("--outdir", default=settings.outdir)
    ap.add_argument("--resume", metavar="RUN_DIR", help="resume from a previous run folder")
    ap.add_argument("--s3", action="store_true", help="upload outputs to S3 (needs TS_S3_BUCKET)")
    ap.add_argument("--webhook", help="Slack/Discord webhook URL")
    ap.add_argument("--open", action="store_true")
    ap.add_argument("--json-logs", action="store_true")
    ap.add_argument("--codegen", action="store_true")
    return ap


# ------------------------------------------------------------------ helpers
def _resolve_page_kwargs(a) -> tuple[str, object | None, dict]:
    """Return (preset_name, preset_obj, page_kwargs)."""
    if a.page_object:
        page_cls = PAGE_REGISTRY[a.page_object]
        preset_name, preset = ("", None)
        if a.preset and a.preset != "auto":
            preset_name = a.preset
            preset = get_preset(a.preset)
        if a.page_object == "listing":
            page_kwargs = {"item_selector": a.item_selector, "preset": preset}
        else:
            page_kwargs = {"preset": preset}
        return preset_name, preset, {"page_cls": page_cls, "page_kwargs": page_kwargs}

    page_cls = PAGE_REGISTRY["listing"]
    preset_name, preset = ("", None)
    if a.preset and a.preset != "auto":
        preset_name = a.preset
        preset = get_preset(a.preset)
    page_kwargs = {"item_selector": a.item_selector, "preset": preset}
    return preset_name, preset, {"page_cls": page_cls, "page_kwargs": page_kwargs}


def _run_single(a, page_cls, page_kwargs, resume_dir) -> int:
    """Single-URL (optionally paginated) run."""
    fetcher = Fetcher(
        mode=("static" if a.static else "render" if a.render
              else "interactive" if a.interactive else "auto"),
        scroll=a.scroll, infinite=a.infinite, infinite_max=a.infinite_max,
        proxy=a.proxy, use_session=a.use_session, save_session=a.save_session,
    )
    try:
        if resume_dir:
            log.info(f"Resuming from {resume_dir}")
            Checkpoint(Path(resume_dir))  # ensures structure exists

        page_kwargs["use_llm"] = getattr(a, "llm", False)
        if getattr(a, "api_mode", False):
            return _run_api_mode(a)

        result = Pipeline(
            fetcher=fetcher, page_cls=page_cls, page_kwargs=page_kwargs,
            max_pages=a.max_pages, delay=a.delay, ignore_robots=a.ignore_robots,
        ).run(a.url)
    finally:
        fetcher.close()

    return _finalise(a, result, resume_dir=resume_dir, crawl_mode=False)

def _run_api_mode(a) -> int:
    """Fetch a JSON API endpoint and convert it to items."""
    import requests

    from .core.api_extractor import extract_items_from_json, try_parse_json

    log.stage("api-mode", a.url)

    # Build headers
    headers = {"User-Agent": UA, "Accept": "application/json"}
    for h in (a.header or []):
        if ":" in h:
            k, v = h.split(":", 1)
            headers[k.strip()] = v.strip()

    # Fetch
    proxies = {"http": a.proxy, "https": a.proxy} if a.proxy else None
    try:
        r = requests.get(a.url, headers=headers, proxies=proxies, timeout=30)
    except requests.RequestException as e:
        log.fail(f"API request failed: {e}")
        return 1

    if r.status_code >= 400:
        log.fail(f"API returned HTTP {r.status_code}")
        return 1

    data = try_parse_json(r.text)
    if data is None:
        log.fail("Response is not valid JSON")
        return 1

    # Build field map
    field_map = None
    if a.field_map:
        field_map = {}
        for pair in a.field_map.split(","):
            if "=" in pair:
                k, v = pair.split("=", 1)
                field_map[k.strip()] = v.strip()

    items = extract_items_from_json(data, json_path=a.api_path, field_map=field_map)
    if not items:
        log.warn("API mode: no items extracted")
        return 1

    log.info(f"API mode: extracted {len(items)} items")
    for it in items:
        log.metric("item", f"{it.title[:60]} | {it.price}")

    # Save as CSV
    host = re.sub(r'[^A-Za-z0-9.-]', '_', urlparse(a.url).netloc)
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    out_dir = Path(a.outdir) / f"api_{host}_{stamp}"
    out_dir.mkdir(parents=True, exist_ok=True)

    from .core.exporters import write_csv
    write_csv(out_dir / "items.csv", [i.model_dump() for i in items])

    log.info(f"Saved to {out_dir / 'items.csv'}")
    return 0


def _run_crawl(a, page_cls, page_kwargs) -> int:
    """Whole-site crawl using the static HTTP fetcher (thread-safe)."""
    if a.render or a.interactive or a.infinite:
        log.warn("--crawl ignores --render/--interactive/--infinite (uses static fetch for stability).")

    fetcher = Fetcher(mode="static", scroll=False, proxy=a.proxy,
                      use_session=a.use_session, save_session=a.save_session)

    log.stage("crawl", f"seed={a.url}  max={a.crawl_max}  workers={a.concurrency}")
    try:
        pages = crawl_urls(a.url, fetcher, max_pages=a.crawl_max,
                           same_host_only=settings.crawl_same_host_only,
                           respect_robots=not a.ignore_robots and settings.crawl_respect_robots)
    finally:
        fetcher.close()

    log.info(f"Crawl collected {len(pages)} page(s)")

    page_kwargs["use_llm"] = getattr(a, "llm", False)

    from bs4 import BeautifulSoup

    from .core.extractors import (  # noqa: F401
        extract_headings,
        extract_images,
        extract_links,
        extract_tables,
        find_next,
    )
    from .core.pipeline import RunResult
    from .core.validators import qa_issues

    rr = RunResult()
    PageCls = page_cls

    for i, (final_url, html) in enumerate(pages, 1):
        class _OneShot(PageCls):  # type: ignore[misc, valid-type]
            """Reuse PageCls parsing logic without hitting the network."""

            def load(self, url: str, pageno: int = 1):  # type: ignore[override]
                self.url = url
                self.pageno = pageno
                self.html = html
                self.final_url = url
                self.method = "crawl-static"
                self.soup = BeautifulSoup(html, "lxml")
                self._parse_header()
                self._parse_common()
                self._parse_items()
                self.next_url = None
                self.issues = qa_issues(self.soup, self)
                return self

        try:
            page = _OneShot(None, **page_kwargs).load(final_url, i)
        except Exception as e:
            log.warn(f"Skip parse {final_url}: {e}")
            continue

        rr.pages.append(page)
        log.metric("parsed", f"{len(rr.pages)}/{len(pages)}  items={len(page.items)}")

    return _finalise(a, rr, resume_dir=None, crawl_mode=True)


def _finalise(a, result, resume_dir: str | None, crawl_mode: bool) -> int:
    """Shared post-processing: link-check, dedupe, validate, write, notify."""
    global _T0

    if not result.pages:
        log.fail("No pages parsed — nothing to write.")
        return 1

    # link check
    checked = 0
    if a.check_links and result.links:
        uniq = list(OrderedDict.fromkeys(
            l.href for l in result.links
            if l.type == "internal" or (a.external and l.type == "external")))
        uniq = [u for u in uniq if u.startswith(("http://", "https://"))][:a.check_links]
        log.stage("check links", f"{len(uniq)} unique URL(s)")
        with allure_step(f"Check {len(uniq)} links"):
            res = _check_links(uniq, settings.link_check_workers)
        checked = len(uniq)
        for l in result.links:
            if l.href in res:
                l.status, l.detail = res[l.href]
        for u, (st, d) in res.items():
            if st in ("BROKEN", "ERROR"):
                result.issues.append(QAIssue(
                    page="",
                    severity="High" if st == "BROKEN" else "Medium",
                    check="Broken link" if st == "BROKEN" else "Link check failed",
                    detail=f"{st} ({d})", where=u,
                ))

    # dedupe
    deduped_count = 0
    if a.dedupe:
        uniq_items, deduped_count = dedupe_items(result.items)
        # keep only the surviving items on their original pages
        keep = {id(x) for x in uniq_items}
        for p in result.pages:
            p.items = [i for i in p.items if id(i) in keep]
        log.info(f"Dedupe: removed {deduped_count} duplicate item(s)")

    # sort issues by severity
    order = {"High": 0, "Medium": 1, "Low": 2}
    result.issues.sort(key=lambda i: order.get(i.severity, 3))

    # output dir
    if resume_dir:
        out_dir = Path(resume_dir)
    else:
        host = urlparse(result.pages[0].final_url).netloc or "local"
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_dir = Path(a.outdir) / f"scrape_{re.sub(r'[^A-Za-z0-9.-]', '_', host)}_{stamp}"
    out_dir.mkdir(parents=True, exist_ok=True)

    if a.json_logs:
        log.set_json_sink(out_dir / "run.jsonl")

    meta = RunMeta(
        url=result.pages[0].final_url,
        host=urlparse(result.pages[0].final_url).netloc or "local",
        when=datetime.now(),
        method=result.pages[0].method,
        secs=time.time() - _T0,
        pages=len(result.pages),
        checked=checked,
        selector=result.pages[0].selector,
        preset=a.preset or "",
        session=a.use_session or a.save_session or "",
        mode="crawl" if crawl_mode else "single",
        crawled_urls=len(result.pages) if crawl_mode else 0,
        deduped_items=deduped_count,
        concurrency=a.concurrency if crawl_mode else 1,
        strict=bool(a.validate),
        resumed_from=resume_dir or "",
    )

    # formats
    formats = {f.strip().lower() for f in a.format.split(",") if f.strip()}
    valid = {"csv", "json", "jsonl", "sqlite"}
    if not formats <= valid:
        log.fail(f"Unknown format(s): {formats - valid}")
        return 2

    log.stage("write report", str(out_dir))
    export_all(out_dir, result, meta, formats)
    write_html_report(out_dir, result, meta)

    counts = {
        "pages": len(result.pages), "items": len(result.items),
        "links": len(result.links), "images": len(result.images),
        "tables": len(result.tables), "qa_issues": len(result.issues),
        "checked_links": checked, "deduped_items": deduped_count,
    }
    manifest_path = write_manifest(out_dir, meta, counts)

    # Allure attachments
    attach_json("run_meta", meta.model_dump(mode="json"))
    try:
        for f in ("items.csv", "qa_issues.csv"):
            if (out_dir / f).exists():
                attach_csv(f, (out_dir / f).read_text(encoding="utf-8-sig"))
        attach_html("report.html", (out_dir / "report.html").read_text(encoding="utf-8"))
    except Exception:
        pass

    # Google Sheets sink (optional)
    if "gsheet" in (a.sink or []):
        if not a.sheet_id:
            log.warn("--sink gsheet requires --sheet-id. Skipping Google Sheets.")
        else:
            try:
                sink = GSheetSink(
                    sheet_id=a.sheet_id,
                    credentials_file="credentials.json",
                    worksheet=a.sheet_name,
                    mode=a.sheet_mode,
                )
                rows = sink.push(result.items)
                log.info(f"Pushed {rows} rows to Google Sheet")
            except Exception as e:
                log.fail(f"Google Sheets sink failed: {e}")

    # S3 (optional)
    s3_uri = None
    if a.s3:
        s3_uri = storage.upload_dir(out_dir)

    # summary table
    table = Table(title=f"Scraped {meta.url}")
    table.add_column("What")
    table.add_column("Count", justify="right")
    for k, v in counts.items():
        table.add_row(k, str(v))
    Console().print(table)

    log.info(f"HTML report : {(out_dir / 'report.html').resolve()}")
    log.info(f"Manifest    : {manifest_path.resolve()}")
    if s3_uri:
        log.info(f"S3 upload   : {s3_uri}")
    log.info(f"Total time  : {log.elapsed()}")

    # webhook
    if a.webhook:
        settings.webhook_url = a.webhook
        webhook.notify_done(meta.url, len(result.items), len(result.pages), meta.secs, str(out_dir))

    # strict validation
    if a.validate:
        highs = [i for i in result.issues if i.severity == "High"]
        if highs:
            log.fail(f"Strict mode: {len(highs)} High-severity QA issue(s) — exiting non-zero")
            return 3

    if a.open:
        webbrowser.open((out_dir / "report.html").resolve().as_uri())
    return 0


# ------------------------------------------------------------------ main
def main(argv: list[str] | None = None) -> int:
    global _T0
    a = _build_parser().parse_args(argv)

    # --list-sessions shortcut
    if a.list_sessions:
        names = session_mod.list_sessions()
        if not names:
            log.warn("No saved sessions.")
        else:
            log.info("Saved sessions:")
            for n in names:
                print(f"   • {n}")
        return 0

    _T0 = time.time()

    preset_name, preset, resolved = _resolve_page_kwargs(a)
    page_cls = resolved["page_cls"]
    page_kwargs = resolved["page_kwargs"]

    # --preset auto → fetch first page to fingerprint
    if a.preset == "auto" and not a.page_object:
        log.stage("fingerprint", "fetching first page to detect CMS…")
        probe = Fetcher(mode=("static" if a.static else "render" if a.render else "auto"),
                        proxy=a.proxy, use_session=a.use_session)
        try:
            html, _, _ = probe.get(a.url)
            det, score = detect_preset(html)
        finally:
            probe.close()
        preset_name = det
        preset = get_preset(det)
        page_kwargs["preset"] = preset
        log.info(f"Using preset: {det} (score={score})")

    mode = ("static" if a.static else "render" if a.render
            else "interactive" if a.interactive else "auto")

    log.stage("start", f"URL = {a.url}")
    log.metric("mode", "crawl" if a.crawl else mode)
    log.metric("max pages", a.crawl_max if a.crawl else a.max_pages)
    log.metric("concurrency", a.concurrency if a.crawl else 1)
    log.metric("check links", a.check_links or "off")
    log.metric("formats", a.format)
    if preset_name:
        log.metric("preset", preset_name)
    if a.page_object:
        log.metric("page object", a.page_object)
    if a.use_session:
        log.metric("use session", a.use_session)
    if a.save_session:
        log.metric("save session", a.save_session)
    if a.validate:
        log.metric("validate", "strict")
    if a.llm:
        log.metric("llm fallback", "on")

    try:
        if a.crawl:
            with allure_step(f"Crawl {a.url}"):
                return _run_crawl(a, page_cls, page_kwargs)
        else:
            with allure_step(f"Scrape {a.url}"):
                return _run_single(a, page_cls, page_kwargs, resume_dir=a.resume)
    except FetchError as e:
        log.fail(f"Scrape failed: {e}")
        log.warn("Try:  --interactive  or  --render  or  --static")
        if a.webhook:
            settings.webhook_url = a.webhook
            webhook.notify_error(a.url, str(e))
        return 1


if __name__ == "__main__":
    sys.exit(main())