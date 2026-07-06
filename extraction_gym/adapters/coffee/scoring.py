"""Field scoring config for the coffee adapter: scorer kind and composite weight per field.

Weights are higher for value-critical fields (price, package size, origin, process,
variety, page classification). Weight 0 = report-only, excluded from the composite
(is_specialty_coffee stays report-only until R11 survives a labeling pass).
"""

from __future__ import annotations

from functools import partial

from extraction_gym.core.scorers import (
    score_exact,
    score_notes_set,
    score_number,
    score_set_f1,
    score_token_f1,
)

VARIETY_ALIASES = {
    "geisha": "gesha",
    "sl-9": "sl9",
    "sl 9": "sl9",
    "sl-09": "sl9",
    "sl-28": "sl28",
    "sl 28": "sl28",
    "sl-34": "sl34",
    "sl 34": "sl34",
    "ruiru 11": "ruiru11",
}

# field -> (scorer, weight)
FIELD_SPECS = {
    "page_type": (score_exact, 3.0),
    "is_specialty_coffee": (score_exact, 0.0),
    "coffee.coffee_name": (score_token_f1, 1.0),
    "coffee.roaster": (score_token_f1, 0.5),
    "coffee.roaster_location": (score_token_f1, 0.5),
    "coffee.roaster_country": (score_exact, 1.0),
    "coffee.origin_country": (score_exact, 3.0),
    "coffee.origin_region": (score_token_f1, 1.0),
    "coffee.process_method": (partial(score_set_f1, aliases=VARIETY_ALIASES), 3.0),
    "coffee.variety": (partial(score_set_f1, aliases=VARIETY_ALIASES), 3.0),
    "coffee.producer_or_farm": (score_token_f1, 1.0),
    "coffee.altitude": (score_token_f1, 0.5),
    "coffee.roast_level": (score_token_f1, 0.5),
    "coffee.harvest_period": (score_token_f1, 0.5),
    "coffee.is_blend": (score_exact, 2.0),
    "coffee.is_espresso": (score_exact, 1.0),
    "coffee.is_decaf": (score_exact, 2.0),
    "coffee.is_coferment_or_infused": (score_exact, 1.0),
    "coffee.sensory_text": (score_token_f1, 2.0),
    "coffee.display_tasting_notes": (score_notes_set, 1.0),
    "coffee.producer_text": (score_token_f1, 2.0),
    "price.listed_price": (partial(score_number, decimals=2), 3.0),
    "price.listed_currency": (score_exact, 2.0),
    "price.bag_size_value": (partial(score_number, rel_tol=0.001), 1.0),
    "price.bag_size_unit": (score_exact, 1.0),
    "price.package_grams": (partial(score_number, rel_tol=0.02), 3.0),
    "price.bags_count": (score_exact, 1.0),
    "price.price_type": (score_exact, 2.0),
    "price.availability": (score_exact, 1.0),
}

# Fields whose regression blocks a candidate regardless of composite improvement.
CRITICAL_FIELDS = [
    "page_type",
    "coffee.origin_country",
    "coffee.process_method",
    "coffee.variety",
    "price.listed_price",
    "price.package_grams",
]


def score_page(gold: dict, got: dict) -> dict[str, float | None]:
    """Per-field scores for one page. On non-coffee gold pages only page_type is graded;
    all other fields return None (excluded from aggregation)."""
    scores: dict[str, float | None] = {}
    coffee_page = gold.get("page_type", "coffee_product") == "coffee_product"
    for field, (scorer, _weight) in FIELD_SPECS.items():
        if not coffee_page and field != "page_type":
            scores[field] = None
            continue
        scores[field] = scorer(gold.get(field), got.get(field))
    return scores


def composite(scores: dict[str, float | None]) -> float:
    total, weight_sum = 0.0, 0.0
    for field, score in scores.items():
        if score is None:
            continue
        weight = FIELD_SPECS[field][1]
        total += score * weight
        weight_sum += weight
    return total / weight_sum if weight_sum else 0.0
