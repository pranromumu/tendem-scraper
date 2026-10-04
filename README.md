# Tendem Scraper — Production POM Web-Scraping Framework (v2.0.0)

[![CI](https://github.com/<you>/tendem-scraper/actions/workflows/ci.yml/badge.svg)](../../actions)
![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![Playwright](https://img.shields.io/badge/Playwright-1.44-45ba4b)
![License](https://img.shields.io/badge/license-MIT-green)

**One repo. Every real-world scraping workflow:** single pages, JS SPAs, infinite
scroll, whole-site crawls, sessions, CMS auto-detection, concurrency, resume,
dedupe, strict validation, multi-format delivery, S3 upload, Slack/Discord notify,
Allure artefacts, CI, Docker.

---

## 30-second demo

```bash
pip install -e ".[dev,cloud,llm]"
playwright install chromium

# just paste a URL — auto-detects the CMS and the repeating card
tendem-scrape https://books.toscrape.com/ --max-pages 3 --open

# whole-site crawl with concurrency + dedupe + multi-format
tendem-scrape https://books.toscrape.com/ --crawl --crawl-max 40 --concurrency 8 \
    --dedupe --format csv,json,jsonl,sqlite --open

# log in ONCE and reuse the session
tendem-scrape https://site.com/login --interactive --save-session mysite
tendem-scrape https://site.com/orders --use-session mysite --max-pages 10