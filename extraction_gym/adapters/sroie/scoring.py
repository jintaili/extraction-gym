"""SROIE field scoring: normalized exact match (the literature-standard metric for
SROIE Task 3), with a numeric-tolerant comparator for total. Deterministic; no LLM."""

from __future__ import annotations

import re


def _norm(value) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value).strip().casefold())


def score_exact_norm(gold, got) -> float:
    return 1.0 if _norm(gold) == _norm(got) else 0.0


def score_total(gold, got) -> float:
    def parse(v):
        if v is None:
            return None
        m = re.search(r"-?\d[\d,]*\.?\d*", str(v).replace("RM", "").replace("$", ""))
        if not m:
            return None
        try:
            return round(float(m.group().replace(",", "")), 2)
        except ValueError:
            return None

    g, p = parse(gold), parse(got)
    if g is None and p is None:
        return 1.0
    if g is None or p is None:
        return 0.0
    return 1.0 if g == p else 0.0


# field -> (scorer, weight); total and date are the critical fields.
FIELD_SPECS = {
    "company": (score_exact_norm, 1.0),
    "date": (score_exact_norm, 2.0),
    "address": (score_exact_norm, 1.0),
    "total": (score_total, 2.0),
}
CRITICAL_FIELDS = ["date", "total"]


def score_page(gold: dict, got: dict) -> dict[str, float]:
    return {f: scorer(gold.get(f), got.get(f)) for f, (scorer, _w) in FIELD_SPECS.items()}


def composite(scores: dict[str, float]) -> float:
    total_w = sum(w for _, w in FIELD_SPECS.values())
    return sum(s * FIELD_SPECS[f][1] for f, s in scores.items()) / total_w
