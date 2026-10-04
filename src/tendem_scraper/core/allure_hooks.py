"""Allure integration (safe no-op outside a pytest run)."""
from __future__ import annotations

import contextlib

try:
    import allure
    _HAS = True
except ImportError:
    _HAS = False


@contextlib.contextmanager
def allure_step(title: str):
    if _HAS:
        with allure.step(title):
            yield
    else:
        yield


def attach_json(name: str, payload) -> None:
    if not _HAS:
        return
    import json
    allure.attach(json.dumps(payload, indent=2, ensure_ascii=False),
                  name=name, attachment_type=allure.attachment_type.JSON)


def attach_text(name: str, text: str) -> None:
    if _HAS:
        allure.attach(text, name=name, attachment_type=allure.attachment_type.TEXT)


def attach_csv(name: str, csv_text: str) -> None:
    if _HAS:
        allure.attach(csv_text, name=name, attachment_type=allure.attachment_type.CSV)


def attach_html(name: str, html_text: str) -> None:
    if _HAS:
        allure.attach(html_text, name=name, attachment_type=allure.attachment_type.HTML)