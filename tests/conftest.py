from pathlib import Path

import pytest

FIX = Path(__file__).parent / "fixtures"


@pytest.fixture
def books_html() -> str:
    return (FIX / "books_page.html").read_text(encoding="utf-8")