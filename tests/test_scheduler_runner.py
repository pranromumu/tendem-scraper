"""Tests for the scheduler runner — job execution with mocked pipeline."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from tendem_scraper.scheduler import config, runner


# ----------------------------------------------------------------- fixtures
@pytest.fixture
def tmp_schedules(tmp_path, monkeypatch):
    """Redirect scheduler storage to a temp folder."""
    monkeypatch.setattr(config, "SCHEDULES_DIR", tmp_path)
    monkeypatch.setattr(config, "JOBS_FILE", tmp_path / "jobs.json")
    return tmp_path


@pytest.fixture
def tmp_reports(tmp_path, monkeypatch):
    """Redirect reports output to a temp folder."""
    reports = tmp_path / "reports"
    reports.mkdir()
    from tendem_scraper.config import settings
    monkeypatch.setattr(settings, "outdir", str(reports))
    return reports


def _fake_page():
    """A minimal page object that run_job expects."""
    page = MagicMock()
    page.method = "static"
    page.selector = "article.product_pod"
    page.items = []
    return page


def _fake_result():
    """A fake RunResult with one page."""
    result = MagicMock()
    result.pages = [_fake_page()]
    result.items = []
    result.links = []
    result.images = []
    result.tables = []
    result.issues = []
    return result


# ----------------------------------------------------------------- run_job
def test_run_job_missing_returns_1(tmp_schedules, capsys):
    """A nonexistent job name returns exit code 1."""
    rc = runner.run_job("does-not-exist")
    assert rc == 1


def test_run_job_updates_status_on_success(tmp_schedules, tmp_reports, monkeypatch):
    """A successful run marks the job as OK."""
    # Add a job
    config.upsert_job(config.ScheduledJob(
        name="test-job",
        url="https://example.com",
        cron="0 8 * * 1",
    ))

    # Mock Fetcher + Pipeline
    fake_fetcher = MagicMock()
    fake_fetcher.get = MagicMock(return_value=("<html></html>", "https://example.com", "static"))
    fake_fetcher.close = MagicMock()

    monkeypatch.setattr(runner, "Fetcher", lambda **kw: fake_fetcher)

    # Mock Pipeline
    fake_pipeline = MagicMock()
    fake_pipeline.run = MagicMock(return_value=_fake_result())
    monkeypatch.setattr(
        "tendem_scraper.core.pipeline.Pipeline",
        lambda **kw: fake_pipeline,
    )

    # Mock exporters
    monkeypatch.setattr(
        "tendem_scraper.core.exporters.export_all",
        lambda *a, **k: {},
    )
    monkeypatch.setattr(
        "tendem_scraper.core.exporters.write_manifest",
        lambda *a, **k: Path("manifest.json"),
    )
    monkeypatch.setattr(
        "tendem_scraper.core.reporter.write_html_report",
        lambda *a, **k: Path("report.html"),
    )

    rc = runner.run_job("test-job")
    assert rc == 0

    # Verify job was marked OK
    updated = config.get_job("test-job")
    assert updated.last_status == "OK"
    assert updated.last_run != ""


def test_run_job_marks_failed_on_exception(tmp_schedules, tmp_reports, monkeypatch):
    """An error during scraping marks the job as FAILED."""
    config.upsert_job(config.ScheduledJob(
        name="failing-job",
        url="https://example.com",
        cron="0 8 * * 1",
    ))

    fake_fetcher = MagicMock()
    fake_fetcher.close = MagicMock()
    monkeypatch.setattr(runner, "Fetcher", lambda **kw: fake_fetcher)

    # Make Pipeline raise
    def boom(**kw):
        raise RuntimeError("simulated failure")

    monkeypatch.setattr("tendem_scraper.core.pipeline.Pipeline", boom)

    rc = runner.run_job("failing-job")
    assert rc == 1

    updated = config.get_job("failing-job")
    assert "FAILED" in updated.last_status


# ----------------------------------------------------------------- run_daemon
def test_run_daemon_no_jobs_returns_early(tmp_schedules):
    """No scheduled jobs → daemon exits immediately."""
    runner.run_daemon()  # should not raise


def test_run_daemon_invalid_cron_logs_error(tmp_schedules, monkeypatch):
    """An invalid cron expression is skipped with a warning."""
    config.upsert_job(config.ScheduledJob(
        name="bad-cron",
        url="https://example.com",
        cron="this is not a cron",
    ))

    # Mock BlockingScheduler so .start() doesn't block
    mock_scheduler = MagicMock()
    mock_scheduler.add_job = MagicMock()
    mock_scheduler.start = MagicMock()
    monkeypatch.setattr(runner, "BlockingScheduler", lambda: mock_scheduler)

    # Should not raise — invalid entries are skipped
    runner.run_daemon()

    # The invalid job should NOT have been scheduled
    assert mock_scheduler.add_job.called is False

def test_run_daemon_schedules_valid_job(tmp_schedules, monkeypatch):
    """A valid job is scheduled (we mock BlockingScheduler so it doesn't block)."""
    config.upsert_job(config.ScheduledJob(
        name="good-job",
        url="https://example.com",
        cron="0 8 * * 1",
    ))

    # Mock BlockingScheduler so .start() doesn't actually block
    mock_scheduler = MagicMock()
    mock_scheduler.add_job = MagicMock()
    mock_scheduler.start = MagicMock()

    monkeypatch.setattr(runner, "BlockingScheduler", lambda: mock_scheduler)

    runner.run_daemon()
    assert mock_scheduler.add_job.called
    assert mock_scheduler.start.called