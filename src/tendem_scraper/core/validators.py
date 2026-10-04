"""QA rules."""
from __future__ import annotations
from collections import Counter
from bs4 import BeautifulSoup

from ..models import QAIssue
from .extractors import clean


def qa_issues(soup: BeautifulSoup, page) -> list[QAIssue]:
    out: list[QAIssue] = []

    def add(sev, check, detail, where=""):
        out.append(QAIssue(page=page.pageno, severity=sev, check=check,
                           detail=detail, where=where[:120]))

    def snip(el):
        return clean(str(el))[:120]

    if not page.title:
        add("High", "Missing <title>", "Page has no title.")
    elif len(page.title) > 70:
        add("Low", "Long <title>", f"{len(page.title)} chars.", page.title)
    if not page.description:
        add("Medium", "Missing meta description", "No <meta name=description>.")
    if not page.lang:
        add("Low", "Missing lang attribute", "<html> has no lang.")

    h1 = [h for h in page.headings if h.level == 1]
    if not h1:
        add("Medium", "No <h1>", "Page has no top-level heading.")
    elif len(h1) > 1:
        add("Low", "Multiple <h1>", f"{len(h1)} h1s found.",
            "; ".join(h.text for h in h1))

    bad_alt = [i for i in page.images if i.alt_state == "missing"]
    for i in bad_alt[:15]:
        add("Medium", "Image without alt", "<img> has no alt.", i.src)
    if len(bad_alt) > 15:
        add("Medium", "Image without alt", f"... +{len(bad_alt)-15} more.")

    empty_links = [l for l in page.links if not l.text]
    for l in empty_links[:15]:
        add("Medium", "Link without accessible name", "No text / aria-label / img alt.", l.href)
    if len(empty_links) > 15:
        add("Medium", "Link without accessible name", f"... +{len(empty_links)-15} more.")

    placeholder = [l for l in page.links if l.type in ("anchor", "javascript")
                   and l.href in ("#", "javascript:void(0)", "javascript:;")]
    if placeholder:
        add("Low", "Placeholder links", f"{len(placeholder)} placeholder links.")

    for b in soup.find_all("button"):
        if not (clean(b.get_text(" ")) or b.get("aria-label") or b.get("title")
                or b.get("value") or b.find("img")):
            add("Medium", "Button without accessible name", "No text/aria-label/title.", snip(b))

    ids = Counter(e["id"] for e in soup.find_all(id=True))
    for i, n in ids.items():
        if n > 1:
            add("Medium", "Duplicate id", f'id="{i}" used {n} times.', f"#{i}")

    labels_for = {l.get("for") for l in soup.find_all("label") if l.get("for")}
    for f in soup.find_all(["input", "select", "textarea"]):
        if (f.get("type") or "text").lower() in ("hidden", "submit", "button", "reset", "image"):
            continue
        if (f.get("aria-label") or f.get("aria-labelledby") or f.get("title")
                or f.get("id") in labels_for or f.find_parent("label")):
            continue
        add("Low" if f.get("placeholder") else "Medium", "Form field without label",
            "Only placeholder." if f.get("placeholder") else "No <label>/aria-label.", snip(f))

    dup = Counter(i.link for i in page.items if i.link)
    for link, n in dup.items():
        if n > 1:
            add("Medium", "Duplicate item link", f"{n} items → same URL.", link)
    no_title = sum(1 for i in page.items if not i.title)
    if page.items and no_title:
        add("Medium", "Items without title", f"{no_title}/{len(page.items)} items have no title.")
    no_price = sum(1 for i in page.items if not i.price)
    if page.items and no_price == len(page.items):
        add("Low", "No prices detected", "No price pattern in any item.")

    return out