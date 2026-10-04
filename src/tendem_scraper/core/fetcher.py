"""Unified fetcher: local file → static HTTP → Playwright headless → visible."""
from __future__ import annotations
import os, re
from pathlib import Path
from urllib import robotparser
from urllib.parse import urlparse

import requests
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from ..config import settings
from . import logging as log
from .proxy import ProxyPool
from . import session as session_mod
# Backwards-compatible alias — some modules (cli.py, webhook.py) import UA.
UA = settings.user_agent

BLOCK_HINTS = ("just a moment", "access denied", "attention required", "verify you are human",
               "are you a robot", "captcha", "request blocked", "pardon our interruption",
               "403 forbidden")

_STEALTH_JS = """
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
Object.defineProperty(navigator, 'languages', { get: () => ['en-US','en'] });
Object.defineProperty(navigator, 'plugins', { get: () => [1,2,3,4,5] });
window.chrome = { runtime: {} };
"""

_rp_cache: dict[str, robotparser.RobotFileParser] = {}

# Backwards-compatible alias — some modules (cli.py, webhook.py) import UA.


class FetchError(RuntimeError):
    pass


def robots_allows(url: str) -> bool:
    p = urlparse(url)
    if p.scheme not in ("http", "https"):
        return True
    base = f"{p.scheme}://{p.netloc}"
    if base not in _rp_cache:
        rp = robotparser.RobotFileParser()
        try:
            r = requests.get(base + "/robots.txt", headers={"User-Agent": settings.user_agent}, timeout=10)
            rp.parse(r.text.splitlines() if r.status_code == 200 else [])
        except requests.RequestException:
            rp.parse([])
        _rp_cache[base] = rp
    return _rp_cache[base].can_fetch("*", url)


def _blocked(html: str) -> bool:
    head = html[:4000].lower()
    m = re.search(r"<title[^>]*>(.*?)</title>", html, re.I | re.S)
    return any(h in (m.group(1).lower() if m else "") + head for h in BLOCK_HINTS)


def _thin(html: str) -> bool:
    from bs4 import BeautifulSoup
    interactive = len(re.findall(r"<(?:a|input|button|select|textarea)\b", html, re.I))
    text = " ".join(BeautifulSoup(html, "lxml").get_text(" ").split())
    return interactive < 5 and len(text) < 200


class Fetcher:
    """One instance per run. Optionally saves / loads a storage_state."""

    def __init__(self,
                 mode: str = "auto",
                 scroll: bool = False,
                 infinite: bool = False,
                 infinite_max: int = 30,
                 proxy: str | None = None,
                 proxy_pool: list[str] | None = None,
                 use_session: str | None = None,
                 save_session: str | None = None):
        self.mode = mode
        self.scroll = scroll
        self.infinite = infinite
        self.infinite_max = infinite_max
        self.use_session = use_session
        self.save_session = save_session
        self.proxies = ProxyPool(proxy_pool or [])
        if proxy:
            self.proxies = ProxyPool([proxy])

        self.http = requests.Session()
        self.http.headers.update({"User-Agent": settings.user_agent,
                                  "Accept-Language": "en-US,en;q=0.9"})
        self._pw = self._browser = self._ctx = self._page = None
        self.method = "static"
        self._session_saved = False

    # ------------------------------------------------------------ browser
    def _start_browser(self, headless: bool) -> None:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as e:
            raise FetchError(
                "Playwright missing. Run: pip install playwright && playwright install chromium"
            ) from e

        self._pw = sync_playwright().start()
        launch_kwargs: dict = {"headless": headless}
        if settings.browser_channel:
            launch_kwargs["channel"] = settings.browser_channel
        proxy = self.proxies.next()
        if proxy:
            launch_kwargs["proxy"] = {"server": proxy}

        try:
            self._browser = self._pw.chromium.launch(**launch_kwargs)
        except Exception:
            launch_kwargs.pop("channel", None)
            self._browser = self._pw.chromium.launch(**launch_kwargs)

        ctx_kwargs: dict = {
            "user_agent": settings.user_agent,
            "viewport": {"width": 1366, "height": 900},
            "locale": "en-US",
            "java_script_enabled": True,
        }

        # reuse saved session (cookies + localStorage)
        if self.use_session:
            state = session_mod.load_state(self.use_session)
            ctx_kwargs["storage_state"] = state
            log.info(f"Loaded session '{self.use_session}'")

        self._ctx = self._browser.new_context(**ctx_kwargs)
        if settings.stealth:
            self._ctx.add_init_script(_STEALTH_JS)

        self._page = self._ctx.new_page()
        self._page.set_default_timeout(settings.page_timeout_ms)
        self.method = "playwright-headless" if headless else "playwright-visible"
        log.stage("browser", self.method)

    def _goto(self, url: str) -> int | None:
        try:
            resp = self._page.goto(url, wait_until="domcontentloaded", timeout=settings.page_timeout_ms)
        except Exception as e:
            raise FetchError(f"Playwright could not load {url} ({type(e).__name__})") from e
        try:
            self._page.wait_for_load_state("networkidle", timeout=settings.network_idle_ms)
        except Exception:
            pass
        if self.scroll:
            try:
                self._page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                self._page.wait_for_timeout(800)
                self._page.evaluate("window.scrollTo(0, 0)")
            except Exception:
                pass
        if self.infinite:
            self._auto_infinite_scroll()
        return resp.status if resp else None

    def _auto_infinite_scroll(self) -> None:
        """Scroll until the page height stops growing (or --infinite-max reached)."""
        log.info(f"Auto-scrolling for lazy content (max {self.infinite_max} steps)…")
        last_h = 0
        stable = 0
        for i in range(self.infinite_max):
            try:
                h = self._page.evaluate("document.body.scrollHeight")
                self._page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                self._page.wait_for_timeout(900)
                new_h = self._page.evaluate("document.body.scrollHeight")
            except Exception:
                break
            if new_h == last_h and new_h == h:
                stable += 1
                if stable >= 2:
                    break
            else:
                stable = 0
            last_h = new_h
        log.info(f"Infinite scroll finished (height={last_h}px)")

    def _enter(self) -> None:
        log.warn("Browser is open. Solve any check / log in, then press ENTER here.")
        try:
            input()
        except EOFError:
            pass

    def _maybe_save_session(self) -> None:
        if self.save_session and not self._session_saved and self._page is not None:
            try:
                session_mod.save_session(self._page, self.save_session)
                self._session_saved = True
            except Exception as e:
                log.warn(f"Could not save session: {e}")

    # ------------------------------------------------------------ HTTP
    @retry(stop=stop_after_attempt(settings.http_retries),
           wait=wait_exponential(multiplier=0.8, min=1, max=8),
           retry=retry_if_exception_type(requests.RequestException),
           reraise=True)
    def _http_get(self, url: str):
        proxy = self.proxies.next()
        proxies = {"http": proxy, "https": proxy} if proxy else None
        return self.http.get(url, timeout=settings.http_timeout, proxies=proxies)

    # ------------------------------------------------------------ public
    def get(self, url: str) -> tuple[str, str, str]:
        if os.path.isfile(url):
            p = Path(url).resolve()
            return p.read_text(encoding="utf-8"), p.as_uri(), "local-file"

        # If we need a session, skip static and go straight to browser
        force_browser = bool(self.use_session or self.save_session or self.infinite)

        if not force_browser and self._page is None and self.mode in ("auto", "static"):
            try:
                r = self._http_get(url)
                if r.status_code < 400 and not _blocked(r.text) and (
                        self.mode == "static" or not _thin(r.text)):
                    return r.text, r.url, "static"
                if self.mode == "static":
                    raise FetchError(f"Static request not usable (HTTP {r.status_code})")
                log.warn(f"Static returned HTTP {r.status_code} / JS shell → Playwright")
            except requests.RequestException as e:
                if self.mode == "static":
                    raise FetchError(f"Request failed: {e}") from e
                log.warn(f"Static failed ({type(e).__name__}) → Playwright")

        if self._page is None:
            self._start_browser(headless=self.mode != "interactive" and settings.headless)

        status = self._goto(url)

        if self.mode == "interactive":
            self._enter()

        html = self._page.content()
        final = self._page.url

        # save session right after interactive log-in (or after first goto in use-session mode)
        if self.save_session:
            self._maybe_save_session()

        if self.method.startswith("playwright-headless") and (
                _blocked(html) or status in (401, 403, 429, 503)):
            log.warn(f"Blocked in headless (HTTP {status}) → visible browser")
            self.close()
            self._start_browser(headless=False)
            self._goto(url)
            self._enter()
            html = self._page.content()
            final = self._page.url
            self._maybe_save_session()

        if _thin(html):
            log.warn("Page looks nearly empty — try --interactive or --scroll")

        return html, final, self.method

    def close(self) -> None:
        for fn in (self._ctx and self._ctx.close,
                   self._browser and self._browser.close,
                   self._pw and self._pw.stop):
            try:
                fn and fn()
            except Exception:
                pass
        self._pw = self._browser = self._ctx = self._page = None