"""Typed settings via pydantic-settings."""
from __future__ import annotations
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="TS_", extra="ignore")

    # HTTP
    user_agent: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    )
    http_timeout: int = 20
    http_retries: int = 3
    delay_seconds: float = 1.0

    # Playwright
    headless: bool = True
    browser_channel: str | None = "chrome"
    page_timeout_ms: int = 45_000
    network_idle_ms: int = 8_000
    stealth: bool = True

    # Proxy
    proxy: str | None = None
    proxy_pool: list[str] = Field(default_factory=list)

    # LLM
    openrouter_api_key: str | None = None
    openrouter_model: str = "openai/gpt-4o-mini"

    # Output
    outdir: str = "reports"
    allure_dir: str = "allure-results"
    session_dir: str = "sessions"

    # Concurrency
    concurrency: int = 4                 # page-level parallelism in crawl mode
    link_check_workers: int = 8

    # Crawl limits (safety)
    crawl_max_pages: int = 200
    crawl_same_host_only: bool = True
    crawl_respect_robots: bool = True

    # Webhook
    webhook_url: str | None = None       # Slack/Discord incoming webhook
    webhook_on: str = "done"             # done | error | always

    # Cloud (optional)
    s3_bucket: str | None = None
    s3_prefix: str = "scrapes/"
    aws_region: str | None = None


settings = Settings()