"""Validate filled cold-label forms: YAML parses, fields complete, enums and types legal."""

from __future__ import annotations

from pathlib import Path

import yaml

ENUMS = {
    "page_type": {"coffee_product", "coffee_equipment", "other_product", "not_a_product_page"},
    "price.bag_size_unit": {"g", "kg", "oz", "lb"},
    "price.price_type": {"one_time", "subscription", "membership", "unknown"},
    "price.availability": {"in_stock", "sold_out", "preorder", "unknown"},
}
BOOLS = {
    "is_specialty_coffee",
    "coffee.is_blend",
    "coffee.is_espresso",
    "coffee.is_decaf",
    "coffee.is_coferment_or_infused",
}
NUMBERS = {"price.listed_price", "price.bag_size_value", "price.package_grams", "price.bags_count"}
LISTS = {"coffee.process_method", "coffee.variety"}
STRINGS = {
    "coffee.coffee_name",
    "coffee.roaster",
    "coffee.roaster_location",
    "coffee.roaster_country",
    "coffee.origin_country",
    "coffee.origin_region",
    "coffee.producer_or_farm",
    "coffee.altitude",
    "coffee.roast_level",
    "coffee.harvest_period",
    "coffee.sensory_text",
    "coffee.display_tasting_notes",
    "coffee.producer_text",
    "price.listed_currency",
}
ALL_FIELDS = set(ENUMS) | BOOLS | NUMBERS | LISTS | STRINGS


def check_form(path: Path) -> list[str]:
    problems: list[str] = []
    try:
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        mark = getattr(exc, "problem_mark", None)
        where = f" (line {mark.line + 1})" if mark else ""
        return [f"YAML parse error{where}: prose with colons/quotes needs |- block style"]

    status = doc.get("status")
    if status not in {"PENDING", "DONE"}:
        problems.append(f"status must be PENDING or DONE, got {status!r}")
    label = doc.get("label") or {}
    missing = ALL_FIELDS - set(label)
    if missing:
        problems.append(f"missing fields: {', '.join(sorted(missing))}")
    if status != "DONE":
        return problems

    for field, allowed in ENUMS.items():
        v = label.get(field)
        if v is not None and v not in allowed:
            problems.append(f"{field}: {v!r} not in {sorted(allowed)}")
    for field in BOOLS:
        v = label.get(field)
        if v is not None and not isinstance(v, bool):
            problems.append(f"{field}: expected true/false/null, got {v!r}")
    for field in NUMBERS:
        v = label.get(field)
        if v is not None and not isinstance(v, (int, float)):
            problems.append(f"{field}: expected number or null, got {v!r}")
    for field in LISTS:
        v = label.get(field)
        if not isinstance(v, list) or not v:
            problems.append(f"{field}: expected non-empty list (use [\"unknown\"] if absent), got {v!r}")
    for field in STRINGS:
        v = label.get(field)
        if isinstance(v, str) and v.strip() == "~":
            problems.append(f"{field}: placeholder ~ not replaced")
        if v is not None and not isinstance(v, str):
            problems.append(f"{field}: expected string or null, got {v!r} (quote numbers, e.g. \"2025\")")
    return problems


def check_all(goldset: Path) -> dict:
    results = {}
    for path in sorted((goldset / "coldlabels").glob("*.cold.yaml")):
        results[path.name] = check_form(path)
    return results
