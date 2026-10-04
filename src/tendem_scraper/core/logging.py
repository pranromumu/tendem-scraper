"""Rich console + optional JSON-lines sink."""
from __future__ import annotations
import json, sys, time
from datetime import datetime, timezone
from pathlib import Path
from rich.console import Console

console = Console(highlight=False, soft_wrap=True, file=sys.stdout)
err = Console(highlight=False, soft_wrap=True, file=sys.stderr)

_T0 = time.time()
_JSON_PATH: Path | None = None


def set_json_sink(path: Path) -> None:
    global _JSON_PATH
    _JSON_PATH = path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("", encoding="utf-8")


def _json(level: str, msg: str, **extra) -> None:
    if _JSON_PATH is None:
        return
    rec = {"ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
           "level": level, "msg": msg, **extra}
    with _JSON_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def _ts() -> str:
    return f"[dim]{datetime.now().strftime('%H:%M:%S')}[/dim]"


def stage(name: str, msg: str = "") -> None:
    console.print(f"{_ts()} [bold cyan]▶ {name:<22}[/bold cyan] {msg}")
    _json("info", msg or name, stage=name)


def info(msg: str) -> None:
    console.print(f"{_ts()} [green]✓[/green] {msg}")
    _json("info", msg)


def warn(msg: str) -> None:
    console.print(f"{_ts()} [yellow]![/yellow] {msg}")
    _json("warning", msg)


def fail(msg: str) -> None:
    err.print(f"{_ts()} [red]✗[/red] {msg}")
    _json("error", msg)


def metric(key: str, value) -> None:
    console.print(f"{_ts()}   [magenta]{key:<16}[/magenta] {value}")
    _json("info", f"{key}={value}", metric=key, value=str(value))


def elapsed() -> str:
    return f"{time.time() - _T0:.2f}s"