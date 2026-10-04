"""HTML report — sortable, filterable, dark mode."""
from __future__ import annotations

import html as H
import re
from collections import Counter
from pathlib import Path

from ..models import RunMeta

CSS = """
:root{--bg:#f6f7f9;--card:#fff;--tx:#1d2330;--mu:#667085;--bd:#e3e6ec;--ac:#2f6fed;--hd:#eef1f6}
@media(prefers-color-scheme:dark){:root{--bg:#12151c;--card:#1b2029;--tx:#e8ebf2;--mu:#98a2b3;--bd:#2c3340;--ac:#7ba4ff;--hd:#232a36}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--tx);font:15px/1.5 system-ui,Segoe UI,Roboto,sans-serif}
main{max-width:1240px;margin:0 auto;padding:24px 18px 60px}h1{margin:0 0 4px;font-size:24px}h2{margin:0 0 10px;font-size:18px}
.muted{color:var(--mu);font-size:13px}a{color:var(--ac)}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin:18px 0}
.card{background:var(--card);border:1px solid var(--bd);border-radius:10px;padding:12px 14px}
.card b{display:block;font-size:26px;line-height:1.1}.card span{color:var(--mu);font-size:13px}
section{background:var(--card);border:1px solid var(--bd);border-radius:12px;padding:16px;margin:16px 0}
.wrap{overflow-x:auto;max-height:560px;border:1px solid var(--bd);border-radius:8px}
table{border-collapse:collapse;width:100%;font-size:13.5px}th,td{padding:7px 10px;text-align:left;vertical-align:top;border-bottom:1px solid var(--bd)}
th{position:sticky;top:0;background:var(--hd);cursor:pointer;white-space:nowrap;user-select:none}th:hover{color:var(--ac)}
tbody tr:nth-child(even){background:color-mix(in srgb,var(--hd) 45%,transparent)}td{max-width:420px;overflow-wrap:anywhere}
.tools{display:flex;gap:12px;align-items:center;margin:8px 0}.flt{padding:7px 10px;border:1px solid var(--bd);border-radius:8px;background:var(--bg);color:var(--tx);min-width:240px}
.b{display:inline-block;padding:1px 8px;border-radius:99px;font-size:12px;font-weight:600;background:var(--hd)}
.b-high,.b-broken,.b-error{background:#fde2e2;color:#a31515}.b-medium,.b-restricted{background:#fff0d1;color:#8a5a00}
.b-low,.b-missing{background:#e6efff;color:#1f4fbf}.b-ok{background:#ddf5e3;color:#14692c}
.thumb{width:56px;height:56px;object-fit:cover;border-radius:6px;background:var(--hd)}code{background:var(--hd);padding:1px 6px;border-radius:5px;word-break:break-all}
nav.toc{display:flex;flex-wrap:wrap;gap:8px;margin:8px 0}nav.toc a{padding:4px 10px;border:1px solid var(--bd);border-radius:99px;text-decoration:none;font-size:13px;background:var(--card)}
"""

JS = r"""
var NUM=/^\s*[^\d\-\s]{0,4}\s?(-?\d[\d,]*(?:\.\d+)?)\s?[^\d\s]{0,4}\s*$/;
function num(s){var m=NUM.exec(String(s));return m?parseFloat(m[1].replace(/,/g,'')):null}
document.querySelectorAll('table.dt').forEach(function(t){
  Array.prototype.forEach.call(t.tHead.rows[0].cells,function(h,i){var asc=true;h.addEventListener('click',function(){
    var tb=t.tBodies[0],rows=Array.prototype.slice.call(tb.rows);
    rows.sort(function(a,b){var x=a.cells[i].textContent.trim(),y=b.cells[i].textContent.trim(),nx=num(x),ny=num(y);
      var c=(nx!==null&&ny!==null)?nx-ny:x.localeCompare(y,undefined,{numeric:true});return asc?c:-c});
    asc=!asc;rows.forEach(function(r){tb.appendChild(r)});});});
});
document.querySelectorAll('input.flt').forEach(function(inp){inp.addEventListener('input',function(){
  var q=inp.value.toLowerCase(),t=document.getElementById(inp.getAttribute('data-t'));
  Array.prototype.forEach.call(t.tBodies[0].rows,function(r){r.hidden=r.textContent.toLowerCase().indexOf(q)<0});});});
"""

esc = lambda s: H.escape(str(s), quote=True)


def _short(s, n=80):
    s = str(s)
    return s if len(s) <= n else s[:n-3] + "..."


def _fmt(v, kind):
    v = "" if v is None else str(v)
    if kind == "link":
        if v.startswith(("http://", "https://")):
            return f'<a href="{esc(v)}" target="_blank" rel="noopener noreferrer" title="{esc(v)}">{esc(_short(v,70))}</a>'
        return esc(v)
    if kind == "img":
        return (f'<img class="thumb" src="{esc(v)}" loading="lazy" referrerpolicy="no-referrer" alt="">'
                if v.startswith(("http://", "https://", "data:")) else "")
    if kind == "badge":
        return f'<span class="b b-{re.sub("[^a-z]", "", v.lower()) or "x"}">{esc(v)}</span>'
    return esc(v)


def _table(tid, cols, rows, limit=None):
    shown = rows[:limit] if limit else rows
    head = "".join(f"<th>{esc(h)}</th>" for _, h, _ in cols)
    body = "".join("<tr>" + "".join(f"<td>{_fmt(r.get(k, ''), k2)}</td>" for k, _, k2 in cols) + "</tr>" for r in shown)
    more = (f'<p class="muted">Showing the first {limit} of {len(rows)} rows. CSV/JSON/SQLite has everything.</p>'
            if limit and len(rows) > limit else "")
    return (f'<div class="tools"><input class="flt" data-t="{tid}" placeholder="Filter {len(rows)} rows..." aria-label="Filter">'
            f'<span class="muted">click a column header to sort</span></div>'
            f'<div class="wrap"><table class="dt" id="{tid}"><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>{more}')


def build_html_report(meta: RunMeta, result) -> str:
    items, issues, links = result.items, result.issues, result.links
    images, headings, tables = result.images, result.headings, result.tables
    sev = Counter(i.severity for i in issues)
    cards = [("Pages", len(result.pages)), ("Items", len(items)), ("Links", len(links)),
             ("Images", len(images)), ("Tables", len(tables)), ("QA issues", len(issues)),
             ("High", sev["High"]), ("Medium", sev["Medium"])]

    title_line = (f"{esc(meta.url)}<br>{esc(meta.when.isoformat(timespec='seconds'))} &middot; "
                  f"loaded via {esc(meta.method)} &middot; {meta.secs:.2f}s")
    if meta.preset:
        title_line += f" &middot; preset: <code>{esc(meta.preset)}</code>"
    if meta.session:
        title_line += f" &middot; session: <code>{esc(meta.session)}</code>"

    parts = [
        "<h1>Scrape report</h1>",
        f"<div class='muted'>{title_line}</div>",
        "<div class='cards'>" + "".join(
            f"<div class='card'><b>{v}</b><span>{esc(k)}</span></div>" for k, v in cards) + "</div>",
    ]
    toc = [("items", "Items", items), ("qa", "QA issues", issues), ("links", "Links", links),
           ("images", "Images", images), ("tables", "Tables", tables), ("headings", "Headings", headings)]
    parts.append("<nav class='toc'>" + "".join(
        f"<a href='#{i}'>{esc(n)} ({len(d)})</a>" for i, n, d in toc if d) + "</nav>")

    def sec(sid, title, body):
        parts.append(f"<section id='{sid}'><h2>{esc(title)}</h2>{body}</section>")

    if items:
        note = f"<p class='muted'>Item block: <code>{esc(meta.selector)}</code></p>"
        sec("items", f"Items ({len(items)})", note + _table("t-items", [
            ("page", "Page", "text"), ("index", "#", "text"), ("image", "Image", "img"),
            ("title", "Title", "text"), ("price", "Price", "text"),
            ("link", "Link", "link"), ("text", "Text", "text")],
            [i.model_dump() for i in items], 2000))

    if issues:
        sec("qa", f"QA issues ({len(issues)})", _table("t-qa", [
            ("severity", "Severity", "badge"), ("check", "Check", "text"),
            ("detail", "Detail", "text"), ("where", "Where", "text"),
            ("page", "Page", "text")], [i.model_dump() for i in issues]))

    if links:
        sec("links", f"Links ({len(links)})", _table("t-links", [
            ("page", "Page", "text"), ("text", "Text", "text"),
            ("href", "URL", "link"), ("type", "Type", "text"),
            ("status", "Status", "badge"), ("detail", "Code", "text")],
            [l.model_dump() for l in links], 1000))

    if images:
        sec("images", f"Images ({len(images)})", _table("t-images", [
            ("page", "Page", "text"), ("src", "Source", "link"),
            ("alt", "Alt text", "text"), ("alt_state", "Alt", "badge"),
            ("width", "W", "text"), ("height", "H", "text")],
            [i.model_dump() for i in images], 500))

    if tables:
        body = ""
        for n, t in enumerate(tables, 1):
            cols = [(str(i), h or f"col_{i+1}", "text") for i, h in enumerate(t.header)]
            rows = [{str(i): c for i, c in enumerate(r)} for r in t.rows]
            body += f"<h3>Table {n}{' - ' + esc(t.caption) if t.caption else ''}</h3>" + \
                    _table(f"t-tab{n}", cols, rows, 500)
        sec("tables", f"Tables ({len(tables)})", body)

    if headings:
        sec("headings", f"Headings ({len(headings)})", _table("t-head", [
            ("page", "Page", "text"), ("level", "Level", "text"), ("text", "Text", "text")],
            [h.model_dump() for h in headings]))

    csp = "default-src 'none'; img-src http: https: data:; style-src 'unsafe-inline'; script-src 'unsafe-inline'"
    return (f"<!doctype html><html lang='en'><head><meta charset='utf-8'>"
            f"<meta name='viewport' content='width=device-width,initial-scale=1'>"
            f"<meta http-equiv='Content-Security-Policy' content=\"{csp}\">"
            f"<title>Scrape report - {esc(meta.host)}</title>"
            f"<style>{CSS}</style></head><body><main>{''.join(parts)}</main>"
            f"<script>{JS}</script></body></html>")


def write_html_report(out_dir: Path, result, meta: RunMeta) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "report.html"
    path.write_text(build_html_report(meta, result), encoding="utf-8")
    return path