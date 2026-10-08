"""Tests for the JSON API extractor."""
from __future__ import annotations

from tendem_scraper.core.api_extractor import (
    auto_detect_field_map,
    extract_items_from_json,
    parse_json_path,
    try_parse_json,
)


# ----------------------------------------------------------------- parse_json_path
def test_parse_json_path_empty_returns_whole_list():
    data = [{"a": 1}, {"a": 2}]
    assert parse_json_path(data, "") == data


def test_parse_json_path_simple_key():
    data = {"products": [{"a": 1}]}
    assert parse_json_path(data, "products") == [{"a": 1}]


def test_parse_json_path_nested_dot():
    data = {"data": {"items": [{"x": 1}]}}
    assert parse_json_path(data, "data.items") == [{"x": 1}]


def test_parse_json_path_array_flatten():
    data = {"products": [{"x": 1}, {"x": 2}, {"x": 3}]}
    assert parse_json_path(data, "products[*]") == [{"x": 1}, {"x": 2}, {"x": 3}]


def test_parse_json_path_missing_returns_empty():
    assert parse_json_path({"a": 1}, "nonexistent") == []


# ----------------------------------------------------------------- auto_detect_field_map
def test_auto_detect_finds_common_fields():
    sample = {"name": "Widget", "cost": 10, "url": "u", "img": "i", "description": "d"}
    fm = auto_detect_field_map(sample)
    assert fm["title"] == "name"
    assert fm["price"] == "cost"
    assert fm["link"] == "url"
    assert fm["image"] == "img"
    assert fm["text"] == "description"


def test_auto_detect_returns_empty_strings_when_no_match():
    fm = auto_detect_field_map({"xx": 1, "yy": 2})
    assert fm["title"] == ""
    assert fm["price"] == ""


# ----------------------------------------------------------------- extract_items_from_json
def test_extract_items_auto_detect():
    data = [
        {"name": "A", "cost": "$1", "url": "u1", "img": "i1", "description": "d1"},
        {"name": "B", "cost": "$2", "url": "u2", "img": "i2", "description": "d2"},
    ]
    items = extract_items_from_json(data)
    assert len(items) == 2
    assert items[0].title == "A"
    assert items[0].price == "$1"
    assert items[1].title == "B"


def test_extract_items_with_field_map():
    data = [
        {"title": "X", "price_str": "$9"},
    ]
    fm = {"title": "title", "price": "price_str"}
    items = extract_items_from_json(data, field_map=fm)
    assert len(items) == 1
    assert items[0].title == "X"
    assert items[0].price == "$9"


def test_extract_items_with_json_path():
    data = {"data": {"products": [{"name": "A"}, {"name": "B"}]}}
    items = extract_items_from_json(data, json_path="data.products[*]")
    assert len(items) == 2
    assert items[0].title == "A"


def test_extract_items_skips_non_dicts():
    data = [{"name": "A"}, "not a dict", 42, {"name": "B"}]
    items = extract_items_from_json(data)
    assert len(items) == 2


def test_extract_items_caps_at_max_items():
    data = [{"name": f"Item {i}"} for i in range(100)]
    items = extract_items_from_json(data, max_items=10)
    assert len(items) == 10


def test_extract_items_empty_data_returns_empty():
    assert extract_items_from_json([]) == []
    assert extract_items_from_json({}) == []
    assert extract_items_from_json("not a list or dict") == []


# ----------------------------------------------------------------- try_parse_json
def test_try_parse_json_valid():
    assert try_parse_json('{"a": 1}') == {"a": 1}


def test_try_parse_json_invalid_returns_none():
    assert try_parse_json("not json") is None


def test_try_parse_json_empty_returns_none():
    assert try_parse_json("") is None