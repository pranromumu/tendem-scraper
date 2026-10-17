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