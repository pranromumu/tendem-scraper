"""Tests for checkpoint / resume."""
from pathlib import Path

from tendem_scraper.core.resume import Checkpoint


def test_checkpoint_roundtrip(tmp_path: Path):
    ck = Checkpoint(tmp_path)
    ck.mark_page(1, "https://a/", "https://a/p2")
    ck.finish()

    ck2 = Checkpoint(tmp_path)
    assert 1 in ck2.state["pages_done"]
    assert "https://a/" in ck2.state["seen_urls"]
    assert ck2.state["next_url"] == "https://a/p2"
    assert ck2.state["finished"] is True


def test_checkpoint_is_done(tmp_path: Path):
    ck = Checkpoint(tmp_path)
    assert not ck.is_done("https://a/")
    ck.mark_page(1, "https://a/", None)
    assert ck.is_done("https://a/")


def test_snapshot_written(tmp_path: Path):
    ck = Checkpoint(tmp_path)
    p = ck.snapshot_html(1, "<html>hi</html>")
    assert p.exists()
    assert p.parent.name == "pages"
    assert "hi" in p.read_text(encoding="utf-8")


def test_checkpoint_survives_reload(tmp_path: Path):
    ck = Checkpoint(tmp_path)
    ck.mark_page(1, "https://a/", "https://a/p2")
    ck.mark_page(2, "https://a/p2", "https://a/p3")

    ck2 = Checkpoint(tmp_path)
    assert ck2.state["pages_done"] == [1, 2]
    assert len(ck2.state["seen_urls"]) == 2
    assert ck2.state["next_url"] == "https://a/p3"