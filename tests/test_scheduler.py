"""Tests for the scheduler — config + job lifecycle."""
import json

import pytest

from tendem_scraper.scheduler import config


@pytest.fixture
def tmp_schedules(tmp_path, monkeypatch):
    """Redirect the schedules dir to a temp folder for each test."""
    monkeypatch.setattr(config, "SCHEDULES_DIR", tmp_path)
    monkeypatch.setattr(config, "JOBS_FILE", tmp_path / "jobs.json")
    return tmp_path


def test_load_jobs_empty_when_no_file(tmp_schedules):
    assert config.load_jobs() == []


def test_upsert_and_load_job(tmp_schedules):
    job = config.ScheduledJob(
        name="test-weekly",
        url="https://example.com",
        cron="0 8 * * 1",
    )
    config.upsert_job(job)

    loaded = config.load_jobs()
    assert len(loaded) == 1
    assert loaded[0].name == "test-weekly"
    assert loaded[0].url == "https://example.com"
    assert loaded[0].cron == "0 8 * * 1"


def test_get_job_by_name(tmp_schedules):
    config.upsert_job(config.ScheduledJob(name="a", url="https://a.com", cron="* * * * *"))
    config.upsert_job(config.ScheduledJob(name="b", url="https://b.com", cron="* * * * *"))

    found = config.get_job("b")
    assert found is not None
    assert found.url == "https://b.com"

    missing = config.get_job("nonexistent")
    assert missing is None


def test_upsert_updates_existing(tmp_schedules):
    config.upsert_job(config.ScheduledJob(name="job1", url="https://old.com", cron="0 0 * * *"))
    config.upsert_job(config.ScheduledJob(name="job1", url="https://new.com", cron="0 1 * * *"))

    jobs = config.load_jobs()
    assert len(jobs) == 1
    assert jobs[0].url == "https://new.com"
    assert jobs[0].cron == "0 1 * * *"


def test_remove_job(tmp_schedules):
    config.upsert_job(config.ScheduledJob(name="gone", url="https://x.com", cron="* * * * *"))
    assert config.remove_job("gone") is True
    assert config.load_jobs() == []

    # Removing again returns False
    assert config.remove_job("gone") is False


def test_jobs_persisted_as_json(tmp_schedules):
    config.upsert_job(config.ScheduledJob(name="j", url="https://x.com", cron="* * * * *"))
    raw = json.loads(config.JOBS_FILE.read_text(encoding="utf-8"))
    assert isinstance(raw, list)
    assert raw[0]["name"] == "j"


def test_scheduled_job_defaults(tmp_schedules):
    job = config.ScheduledJob(name="d", url="https://x.com", cron="0 0 * * *")
    assert job.preset == "auto"
    assert job.max_pages == 50
    assert job.format == "csv,json,sqlite"
    assert job.crawl is False
    assert job.dedupe is True
    assert job.last_run == ""
    assert job.last_status == ""


def test_corrupt_file_returns_empty(tmp_schedules):
    config.JOBS_FILE.parent.mkdir(parents=True, exist_ok=True)
    config.JOBS_FILE.write_text("this is not json", encoding="utf-8")
    # Should not raise — returns empty list
    assert config.load_jobs() == []


# ---------------------------------------------------------------- cli tests

def test_cli_add_and_list(tmp_schedules, capsys):
    from tendem_scraper.scheduler import cli

    rc = cli.main([
        "add", "clitest",
        "--url", "https://x.com",
        "--cron", "0 8 * * 1",
    ])
    assert rc == 0

    rc = cli.main(["list"])
    assert rc == 0

    # Both should have written to our temp dir
    jobs = config.load_jobs()
    assert len(jobs) == 1
    assert jobs[0].name == "clitest"


def test_cli_add_duplicate_blocked(tmp_schedules):
    from tendem_scraper.scheduler import cli

    cli.main(["add", "dup", "--url", "https://x.com", "--cron", "* * * * *"])
    rc = cli.main(["add", "dup", "--url", "https://x.com", "--cron", "* * * * *"])
    assert rc == 1  # blocked


def test_cli_add_duplicate_with_force(tmp_schedules):
    from tendem_scraper.scheduler import cli

    cli.main(["add", "dup", "--url", "https://a.com", "--cron", "* * * * *"])
    rc = cli.main(["add", "dup", "--url", "https://b.com", "--cron", "* * * * *", "--force"])
    assert rc == 0

    job = config.get_job("dup")
    assert job.url == "https://b.com"


def test_cli_remove(tmp_schedules):
    from tendem_scraper.scheduler import cli

    cli.main(["add", "rem", "--url", "https://x.com", "--cron", "* * * * *"])
    rc = cli.main(["remove", "rem"])
    assert rc == 0
    assert config.get_job("rem") is None


def test_cli_remove_missing(tmp_schedules):
    from tendem_scraper.scheduler import cli

    rc = cli.main(["remove", "nothere"])
    assert rc == 1


def test_cli_list_empty(tmp_schedules, capsys):
    from tendem_scraper.scheduler import cli

    rc = cli.main(["list"])
    assert rc == 0