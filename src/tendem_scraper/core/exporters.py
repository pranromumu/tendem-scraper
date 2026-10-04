"""Multi-format exporters: CSV, JSON, JSONL, SQLite + run manifest."""
from __future__ import annotations

import csv
import json
import sqlite3
from collections.abc import Iterable
from pathlib import Path

from pydantic import BaseModel

from ..models import RunManifest, RunMeta


def _rows(models: Iterable[BaseModel]) -> list[dict]:
    return [m.model_dump(mode="json") for m in models]


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("", encoding="utf-8-sig")
        return
    fields = list(rows[0].keys())
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def write_json(path: Path, rows) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def write_sqlite(path: Path, result, meta: RunMeta) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    con = sqlite3.connect(path)
    try:
        cur = con.cursor()
        cur.execute("CREATE TABLE items (page INT, idx INT, title TEXT, price TEXT, link TEXT, "
                    "image TEXT, text TEXT, fingerprint TEXT)")
        cur.executemany("INSERT INTO items VALUES (?,?,?,?,?,?,?,?)",
                        [(i.page, i.index, i.title, i.price, i.link, i.image, i.text, i.fingerprint)
                         for i in result.items])
        cur.execute("CREATE TABLE links (page INT, text TEXT, href TEXT, type TEXT, status TEXT, detail TEXT)")
        cur.executemany("INSERT INTO links VALUES (?,?,?,?,?,?)",
                        [(l.page, l.text, l.href, l.type, l.status, l.detail) for l in result.links])
        cur.execute("CREATE TABLE images (page INT, src TEXT, alt TEXT, alt_state TEXT, width TEXT, height TEXT)")
        cur.executemany("INSERT INTO images VALUES (?,?,?,?,?,?)",
                        [(i.page, i.src, i.alt, i.alt_state, i.width, i.height) for i in result.images])
        cur.execute("CREATE TABLE headings (page INT, level INT, text TEXT)")
        cur.executemany("INSERT INTO headings VALUES (?,?,?)",
                        [(h.page, h.level, h.text) for h in result.headings])
        cur.execute("CREATE TABLE qa_issues (page TEXT, severity TEXT, check_name TEXT, detail TEXT, where_clause TEXT)")
        cur.executemany("INSERT INTO qa_issues VALUES (?,?,?,?,?)",
                        [(str(i.page), i.severity, i.check, i.detail, i.where) for i in result.issues])
        cur.execute("CREATE TABLE run_meta (url TEXT, host TEXT, when_ts TEXT, method TEXT, secs REAL, "
                    "pages INT, checked INT, selector TEXT, preset TEXT, session TEXT, mode TEXT, "
                    "crawled_urls INT, deduped_items INT, concurrency INT, strict INT, resumed_from TEXT)")
        cur.execute("INSERT INTO run_meta VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (meta.url, meta.host, meta.when.isoformat(), meta.method, meta.secs,
                     meta.pages, meta.checked, meta.selector, meta.preset, meta.session,
                     meta.mode, meta.crawled_urls, meta.deduped_items,
                     meta.concurrency, int(meta.strict), meta.resumed_from))
        con.commit()
    finally:
        con.close()


def export_all(out_dir: Path, result, meta: RunMeta, formats: set[str]) -> dict[str, Path]:
    out: dict[str, Path] = {}
    items = _rows(result.items)
    links = _rows(result.links)
    images = _rows(result.images)
    headings = _rows(result.headings)
    issues = _rows(result.issues)

    if "csv" in formats:
        write_csv(out_dir / "items.csv", items)
        write_csv(out_dir / "links.csv", links)
        write_csv(out_dir / "images.csv", images)
        write_csv(out_dir / "headings.csv", headings)
        write_csv(out_dir / "qa_issues.csv", issues)
        for n, t in enumerate(result.tables, 1):
            header = [h or f"col_{i+1}" for i, h in enumerate(t.header)]
            rows = [dict(zip(header, r)) for r in t.rows]
            write_csv(out_dir / "tables" / f"table_{n}.csv", rows)
        out["csv_dir"] = out_dir

    if "json" in formats:
        write_json(out_dir / "items.json", items)
        write_json(out_dir / "links.json", links)
        write_json(out_dir / "images.json", images)
        write_json(out_dir / "qa_issues.json", issues)
        write_json(out_dir / "run.json", {
            "meta": meta.model_dump(mode="json"),
            "items": items, "links": links, "images": images,
            "headings": headings, "issues": issues,
            "tables": [t.model_dump(mode="json") for t in result.tables],
        })
        out["json"] = out_dir / "run.json"

    if "jsonl" in formats:
        write_jsonl(out_dir / "items.jsonl", items)
        write_jsonl(out_dir / "links.jsonl", links)
        out["jsonl"] = out_dir / "items.jsonl"

    if "sqlite" in formats:
        db = out_dir / "data.sqlite"
        write_sqlite(db, result, meta)
        out["sqlite"] = db

    return out


def write_manifest(out_dir: Path, meta: RunMeta, counts: dict[str, int]) -> Path:
    files = sorted(str(p.relative_to(out_dir)).replace("\\", "/")
                   for p in out_dir.rglob("*") if p.is_file())
    manifest = RunManifest(meta=meta, counts=counts, files=files)
    path = out_dir / "run_manifest.json"
    path.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
    return path