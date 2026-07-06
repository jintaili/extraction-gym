from extraction_gym.adapters.coffee.scoring import composite, score_page
from extraction_gym.core.scorers import (
    score_exact,
    score_notes_set,
    score_number,
    score_set_f1,
    score_token_f1,
)


def test_exact_normalizes_case_and_nulls():
    assert score_exact("Washed", "washed") == 1.0
    assert score_exact(None, None) == 1.0
    assert score_exact(None, "washed") == 0.0
    assert score_exact("", None) == 1.0
    assert score_exact(True, True) == 1.0
    assert score_exact(False, True) == 0.0


def test_number_tolerance_and_decimals():
    assert score_number(340.194, 340.1942772, rel_tol=0.02) == 1.0
    assert score_number(340.194, 425.0, rel_tol=0.02) == 0.0
    assert score_number(21.5, 21.504, decimals=2) == 1.0
    assert score_number(21.5, 21.51, decimals=2) == 0.0
    assert score_number(None, None) == 1.0


def test_set_f1_with_aliases_and_unknown():
    aliases = {"geisha": "gesha", "sl-9": "sl9"}
    assert score_set_f1(["Gesha"], ["geisha"], aliases=aliases) == 1.0
    assert score_set_f1(["SL-9"], ["sl9"], aliases=aliases) == 1.0
    assert score_set_f1(["unknown"], ["unknown"]) == 1.0
    assert score_set_f1(["gesha", "caturra"], ["gesha"]) == 2 * (1.0 * 0.5) / 1.5


def test_token_f1_partial_credit():
    assert score_token_f1("Lamastus Family; El Burro", "Lamastus Family") > 0.5
    assert score_token_f1("a b", "a b") == 1.0
    assert score_token_f1("", "") == 1.0
    assert score_token_f1("something", "") == 0.0


def test_notes_set_order_insensitive():
    assert score_notes_set("black cherry, honey", "Honey, Black Cherry") == 1.0
    assert score_notes_set("", "") == 1.0
    assert 0 < score_notes_set("a, b, c", "a, b") < 1


def test_score_page_masks_non_coffee_and_composite():
    gold = {"page_type": "coffee_equipment", "coffee.origin_country": "unknown"}
    got = {"page_type": "coffee_equipment", "coffee.origin_country": "Peru"}
    scores = score_page(gold, got)
    assert scores["page_type"] == 1.0
    assert scores["coffee.origin_country"] is None
    assert composite(scores) == 1.0

    gold2 = {"page_type": "coffee_product", "coffee.origin_country": "Peru", "price.listed_price": 20}
    got2 = {"page_type": "coffee_product", "coffee.origin_country": "Peru", "price.listed_price": 25}
    scores2 = score_page(gold2, got2)
    assert scores2["coffee.origin_country"] == 1.0
    assert scores2["price.listed_price"] == 0.0
    assert 0 < composite(scores2) < 1
