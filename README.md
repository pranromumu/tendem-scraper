# Tendem Scraper — Production POM Web-Scraping Framework (v2.0.0)

[![CI](https://github.com/pranromumu/tendem-scraper/actions/workflows/ci.yml/badge.svg)](https://github.com/pranromumu/tendem-scraper/actions)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/downloads/)
[![Playwright](https://img.shields.io/badge/Playwright-1.44-45ba4b)](https://playwright.dev/python/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Allure](https://img.shields.io/badge/Allure-report-orange)](https://pranromumu.github.io/tendem-scraper/)

**One repo. Every real-world scraping workflow:** single pages, JS SPAs, infinite
scroll, whole-site crawls, sessions, CMS auto-detection, concurrency, resume,
dedupe, strict validation, multi-format delivery, S3 upload, Slack/Discord notify,
Allure artefacts, CI, Docker.

---

## 📑 Table of contents

- [30-second demo](#-30-second-demo)
- [Why this is production-grade](#-why-this-is-production-grade)
- [Install](#-install)
- [CLI cheat sheet](#-cli-cheat-sheet)
- [Output layout](#-output-layout)
- [Adding a new site (POM pattern)](#-adding-a-new-site-pom-pattern)
- [Architecture](#-architecture)
- [Testing & Allure](#-testing--allure)
- [Docker](#-docker)
- [CI pipeline](#-ci-pipeline)
- [License](#-license)

---

## 🚀 30-second demo

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