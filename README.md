# Tendem Scraper — Production POM Web-Scraping Framework

**One CLI. Every scraping workflow.** Static pages, JavaScript SPAs, infinite
scroll, whole-site crawls, authenticated sessions, CMS auto-detection,
concurrency, resume, dedupe, multi-format delivery, and a self-contained
HTML report — all in one Python package with a 5-job CI pipeline and live
Allure test report.

[![CI Pipeline Quality Gate](https://github.com/pranromumu/tendem-scraper/actions/workflows/ci.yml/badge.svg)](https://github.com/pranromumu/tendem-scraper/actions/workflows/ci.yml)
[![Allure Report](https://img.shields.io/badge/Allure-live%20report-orange)](https://pranromumu.github.io/tendem-scraper/)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/downloads/)
[![Playwright](https://img.shields.io/badge/Playwright-1.44%2B-45ba4b)](https://playwright.dev/python/)
[![Coverage](https://img.shields.io/badge/coverage-74%25-brightgreen)]()
[![Branch coverage](https://img.shields.io/badge/branch%20coverage-59%25-yellowgreen)]()
[![Tests](https://img.shields.io/badge/tests-259%20passed-brightgreen)]()
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)

---

## ⚡ Try it in 60 seconds

```bash
# 1. install
pip install -e ".[dev,cloud,llm]"
playwright install chromium

# 2. scrape + open the report
tendem-scrape https://books.toscrape.com/ --max-pages 3 --open
```

That's it. You get:

- **items.csv** — 60 books, ready for Excel
- **report.html** — sortable, filterable dashboard in your browser
- **items.json** — structured data
- **data.sqlite** — queryable database
- **qa_issues.csv** — data quality audit

No config, no API keys, no signup. Just a URL.

## 📸 Live artifacts

| Artifact | Link |
| --- | --- |
| Live Allure report (auto-published on every push to main) | https://pranromumu.github.io/tendem-scraper/ |
| CI pipeline (5-job quality gate) | https://github.com/pranromumu/tendem-scraper/actions/workflows/ci.yml |
| Scrape report example | See docs/scrape-report-screenshot.png |
| Allure screenshot | See docs/allure-screenshot.png |

## 🎯 Real-world usage examples

```bash
# 1) auto-detect CMS, paginate 50 pages, multi-format
tendem-scrape https://shop.example.com/products --preset auto --max-pages 50 \
  --format csv,json,sqlite --open

# 2) whole-site crawl: concurrency + dedupe
tendem-scrape https://blog.example.com --crawl --crawl-max 200 \
  --concurrency 8 --dedupe --open

# 3) log in ONCE, reuse the session headlessly
tendem-scrape https://site.com/login --interactive --save-session mysite
tendem-scrape https://site.com/orders --use-session mysite --max-pages 10

# 4) JSON API with auth header + proxy
tendem-scrape https://api.example.com/v1/items --api-mode \
  --api-path "data.items[*]" --header "Authorization: Bearer TOKEN" \
  --proxy "http://user:pass@proxy:8080"

# 5) LLM fallback when CSS selectors fail
tendem-scrape https://messy-site.com/ --llm --max-pages 10

# 6) Google Sheets delivery + scheduled weekly
tendem-scrape https://competitor.com/products --sink gsheet --sheet-id "SHEET_ID"
tendem-schedule add acme-weekly --url "https://competitor.com/products" \
  --cron "0 8 * * 1" --preset shopify --email "client@example.com"
```

## 🏗 Architecture

The framework follows a **Page Object Model** design: one class per site,
sharing the same pipeline. Adding a new site means writing ~30 lines in
one file, not rewriting the scraper.

```
┌──────────────────────────────────────────────────────────────┐
│  CLI  (tendem-scrape · tendem-audit · tendem-deliver ·        │
│        tendem-schedule)                                      │
└─────────────────────────────┬────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────┐
│  Pipeline — pagination, concurrency, resume, dedupe, retries │
└─────────────┬────────────────────────────────┬───────────────┘
              │                                │
              ▼                                ▼
┌────────────────────────┐          ┌──────────────────────────┐
│  Fetcher               │          │  Page Object (POM)       │
│  · static HTTP         │          │  · generic listing       │
│  · Playwright headless │  HTML →  │  · product detail        │
│  · visible browser     │          │  · custom per-site       │
│  · proxy pool          │          │  · CMS presets           │
│  · session reuse       │          │  · LLM fallback          │
└────────────┬───────────┘          └──────────┬───────────────┘
             │                                 │
             └───────────────┬─────────────────┘
                             ▼
              ┌──────────────────────────────┐
              │  Extractors                  │
              │  · BeautifulSoup / lxml      │
              │  · JSON path (--api-mode)    │
              │  · Pydantic v2 models        │
              └──────────────┬───────────────┘
                             ▼
              ┌──────────────────────────────┐
              │  Validators (QA)             │
              │  · 15+ accessibility rules   │
              │  · dedupe (SHA-1 fingerprint)│
              │  · broken-link checks        │
              └──────────────┬───────────────┘
                             ▼
              ┌──────────────────────────────┐
              │  Reporters / Sinks           │
              │  · CSV  · JSON  · JSONL      │
              │  · SQLite                    │
              │  · self-contained HTML       │
              │  · Google Sheets             │
              │  · S3                        │
              └──────────────────────────────┘
```

**Design principles:**

- **One fetcher, many page objects** — the transport layer knows nothing about HTML structure, and page objects know nothing about HTTP/Playwright.
- **Extractors are stateless** — same functions work on static HTML, rendered DOM, or JSON API responses.
- **Validators run on every item** — QA is not a separate script, it is a pipeline stage. Bad data never reaches the reporter.
- **Reporters are pluggable** — adding a new output format is one class.
- **The pipeline is the orchestrator** — pagination, resume, dedupe, and retries live in one place, not scattered across page objects.

## 📄 License

This project is licensed under the MIT License — see the LICENSE file for details.