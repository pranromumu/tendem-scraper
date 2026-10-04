.PHONY: install test lint fmt coverage allure serve clean docker demo crawl

install:
	pip install -e ".[dev,cloud,llm]"
	playwright install chromium

test:
	pytest -q

coverage:
	pytest --cov=tendem_scraper --cov-report=term-missing

allure:
	pytest --alluredir=allure-results
	allure serve allure-results

serve:
	allure serve allure-results

demo:
	tendem-scrape https://books.toscrape.com/ --max-pages 3 --check-links 20 --open

crawl:
	tendem-scrape https://books.toscrape.com/ --crawl --crawl-max 30 --concurrency 6 \
		--format csv,json,sqlite --dedupe --open

docker:
	docker compose up --build

clean:
	rm -rf allure-results allure-report reports .pytest_cache htmlcov .coverage \
	       .mypy_cache .ruff_cache build dist *.egg-info sessions