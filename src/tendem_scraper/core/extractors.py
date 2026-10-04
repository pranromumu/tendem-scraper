"""Reusable extractors → pydantic models."""
from __future__ import annotations
import re
from collections import OrderedDict
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from ..models import LinkRow, ImageRow, HeadingRow, TableBlock, Item

PRICE = re.compile(
    r"(?:[$€£¥₹]|\b(?:USD|MYR|RM|Rs\.?|INR|EUR|GBP))\s?\d[\d,]*(?:\.\d+)?"
    r"|\d[\d,]*(?:\.\d+)?\s?(?:USD|MYR|RM|€|£)", re.I)

GENERIC = re.compile(
    r"^(add to (cart|bag|basket)|view( product| details| more)?|buy( now)?|read more|"
    r"learn more|details|more|shop now|quick view|see more|select options|sign ?up|log ?in)$", re.I)

NEXT_TEXT = {"next", "next page", "next »", "next ›", "›", "»", ">", ">>", "older", "older posts"}
SKIP_PARENTS = {"html", "head", "script", "style", "svg", "table", "thead", "tbody",
                "tfoot", "tr", "select", "datalist", "colgroup"}
NAV_TAGS = {"header", "footer", "nav", "aside"}


def clean(t) -> str:
    t = " ".join(str(t).split())
    return "".join(c for c in t if c.isprintable()).strip()


def css_path(el) -> str:
    parts = []
    while el is not None and el.name and el.name != "[document]":
        if el.get("id") and re.match(r"^[A-Za-z][\w-]*$", el["id"]):
            parts.append(f"{el.name}#{el['id']}")
            break
        sibs = el.parent.find_all(el.name, recursive=False) if el.parent else []
        parts.append(f"{el.name}:nth-of-type({sibs.index(el)+1})" if len(sibs) > 1 else el.name)
        el = el.parent
    return " > ".join(reversed(parts))


def link_text(a) -> str:
    t = clean(a.get_text(" "))
    if t and re.search(r"[^\W_]", t):
        return t
    for v in (a.get("aria-label"), a.get("title")):
        if v and clean(v):
            return clean(v)
    img = a.find("img")
    return clean(img["alt"]) if img is not None and img.get("alt") else ""


def extract_links(soup: BeautifulSoup, base: str, pageno: int) -> list[LinkRow]:
    host = urlparse(base).netloc
    out: list[LinkRow] = []
    for a in soup.find_all("a", href=True):
        raw = a["href"].strip()
        if raw.startswith("#"):
            typ, href = "anchor", raw
        elif raw.lower().startswith("javascript:"):
            typ, href = "javascript", raw
        elif raw.lower().startswith("mailto:"):
            typ, href = "mailto", raw
        elif raw.lower().startswith("tel:"):
            typ, href = "tel", raw
        else:
            href = urljoin(base, raw)
            typ = "internal" if urlparse(href).netloc == host else "external"
        out.append(LinkRow(page=pageno, text=link_text(a), href=href, type=typ))
    return out


def extract_images(soup: BeautifulSoup, base: str, pageno: int) -> list[ImageRow]:
    out: list[ImageRow] = []
    for img in soup.find_all("img"):
        src = img.get("src") or img.get("data-src") or img.get("data-lazy-src") or ""
        alt = img.get("alt")
        out.append(ImageRow(
            page=pageno,
            src=urljoin(base, src) if src and not src.startswith("data:") else src[:60],
            alt=alt or "",
            alt_state="missing" if alt is None else "empty" if not alt.strip() else "ok",
            width=img.get("width", ""), height=img.get("height", ""),
        ))
    return out


def extract_headings(soup: BeautifulSoup, pageno: int) -> list[HeadingRow]:
    out: list[HeadingRow] = []
    for h in soup.find_all(re.compile(r"^h[1-6]$")):
        t = clean(h.get_text(" "))
        if t:
            out.append(HeadingRow(page=pageno, level=int(h.name[1]), text=t))
    return out


def extract_tables(soup: BeautifulSoup, pageno: int) -> list[TableBlock]:
    out: list[TableBlock] = []
    for t in soup.find_all("table"):
        trs = [tr for tr in t.find_all("tr") if tr.find_all(["th", "td"])]
        rows = [[clean(c.get_text(" ")) for c in tr.find_all(["th", "td"])] for tr in trs]
        if len(rows) < 2 or max(len(x) for x in rows) < 2:
            continue
        first_is_head = all(c.name == "th" for c in trs[0].find_all(["th", "td"]))
        width = max(len(x) for x in rows)
        head = rows[0] if first_is_head else [f"col_{n}" for n in range(1, width + 1)]
        body = rows[1:] if first_is_head else rows
        cap = t.find("caption")
        out.append(TableBlock(
            page=pageno,
            caption=clean(cap.get_text(" ")) if cap else "",
            header=head + [""] * (width - len(head)),
            rows=[x + [""] * (width - len(x)) for x in body],
        ))
    return out


def find_item_groups(soup: BeautifulSoup, min_items: int = 3) -> list[dict]:
    groups = []
    for parent in soup.find_all(True):
        if parent.name in SKIP_PARENTS:
            continue
        kids = [c for c in parent.find_all(True, recursive=False)
                if c.name not in ("script", "style", "br", "hr")]
        by = {}
        for c in kids:
            by.setdefault((c.name, tuple(c.get("class", []))), []).append(c)
        for sig, items in by.items():
            if len(items) < min_items:
                continue
            texts = [clean(" ".join(i.stripped_strings)) for i in items]
            med = sorted(len(t) for t in texts)[len(texts) // 2]
            if med < 8:
                continue
            link = sum(1 for i in items if i.find("a", href=True)) / len(items)
            img = sum(1 for i in items if i.find("img")) / len(items)
            price = sum(1 for t in texts if PRICE.search(t)) / len(items)
            in_nav = parent.name in NAV_TAGS or any(a.name in NAV_TAGS for a in parent.parents)
            score = len(items) * (min(med, 300) ** 0.5) * (1 + link + img + 2 * price) * (0.15 if in_nav else 1)
            cls = "".join("." + c for c in sig[1] if re.match(r"^[A-Za-z_][\w-]*$", c))
            groups.append({
                "score": round(score, 1), "count": len(items), "items": items,
                "selector": f"{css_path(parent)} > {sig[0]}{cls}",
            })
    groups.sort(key=lambda g: -g["score"])
    return groups


def pick_title(node, title_selector: str = "") -> str:
    cands = []
    if title_selector:
        for el in node.select(title_selector):
            cands.append(clean(el.get_text(" ")))
    cands += [clean(h.get_text(" ")) for h in node.find_all(re.compile(r"^h[1-6]$"))]
    cands += [clean(e.get_text(" ")) for e in node.select('[class*="title" i], [class*="name" i]')]
    cands += [link_text(a) for a in node.find_all("a")]
    cands += [clean(e.get_text(" ")) for e in node.find_all(["p", "strong", "b", "span"])]
    for c in cands:
        if not c or len(c) < 3 or GENERIC.match(c):
            continue
        m = PRICE.search(c)
        if m and len(m.group(0)) >= len(c) - 2:
            continue
        return c[:200]
    return ""


def extract_item(node, base: str, pageno: int, index: int,
                 title_selector: str = "",
                 price_selector: str = "",
                 link_selector: str = "a",
                 image_selector: str = "img",
                 item_link_attr: str = "href",
                 item_img_attr: str = "src") -> Item:
    # price
    price_text = ""
    if price_selector:
        pel = node.select_one(price_selector)
        price_text = clean(pel.get_text(" ")) if pel else ""
    if not price_text:
        pel = node.select_one('[class*="price" i]')
        price_text = clean(pel.get_text(" ")) if pel else ""
    if not price_text:
        price_text = clean(" ".join(node.stripped_strings))
    m = PRICE.search(price_text)

    # link
    link = ""
    a = node.select_one(link_selector) if link_selector else None
    if a is None:
        a = node.find("a", href=True)
    if a is not None:
        raw = a.get(item_link_attr) or a.get("href") or ""
        raw = raw.strip()
        if raw and not raw.startswith(("#", "javascript:")):
            link = urljoin(base, raw)

    # image
    image = ""
    img = node.select_one(image_selector) if image_selector else None
    if img is None:
        img = node.find("img")
    if img is not None:
        src = img.get(item_img_attr) or img.get("src") or img.get("data-src") or img.get("data-lazy-src") or ""
        if not src and img.get("srcset"):
            src = img["srcset"].split(",")[0].split()[0]
        if src and not src.startswith("data:"):
            image = urljoin(base, src)

    text = " | ".join(OrderedDict.fromkeys(s for s in (clean(x) for x in node.stripped_strings) if s))
    return Item(page=pageno, index=index,
                title=pick_title(node, title_selector),
                price=m.group(0).strip() if m else "",
                link=link, image=image, text=text[:400])


def find_next(soup: BeautifulSoup, base: str, next_selector: str = "") -> str | None:
    cand = None
    if next_selector:
        try:
            cand = soup.select_one(next_selector)
        except Exception:
            cand = None
    if cand is None:
        cand = soup.select_one('a[rel~="next"][href], link[rel~="next"][href]')
    if cand is None:
        for a in soup.find_all("a", href=True):
            t = clean(a.get_text(" ")).lower()
            al = (a.get("aria-label") or "").lower()
            classes = [c.lower() for c in a.get("class", [])]
            if t in NEXT_TEXT or "next" in al or "next" in classes:
                cand = a
                break
    if cand is None or not cand.get("href"):
        return None
    holder = " ".join(cand.get("class", []) +
                      (cand.parent.get("class", []) if cand.parent else [])).lower()
    if "disabled" in holder or cand.get("aria-disabled") == "true":
        return None
    u = urljoin(base, cand["href"])
    return u if u.startswith(("http://", "https://")) else None