import pytest

from extraction_gym.eval.stats import binom_one_sided_p
from extraction_gym.optimizer.loop import gate_candidate_v2, suite_repairs

BAND = {"composite_std": 0.005, "field_stds": {f: 0.01 for f in [
    "page_type", "coffee.origin_country", "coffee.process_method",
    "coffee.variety", "price.listed_price", "price.package_grams"]}}


def _gold(composite, price=0.9, n=40):
    means = {f: 0.9 for f in BAND["field_stds"]}
    means["price.listed_price"] = price
    return {"composite_mean": composite, "field_means": means,
            "field_coverage": {f: n for f in means}}


def _suite(pairs):
    """pairs: {page: {field: score}}"""
    return pairs


def test_binom_one_sided():
    assert binom_one_sided_p(5, 0) == pytest.approx(1 / 32)
    assert binom_one_sided_p(0, 0) == 1.0
    assert binom_one_sided_p(4, 4) > 0.5


def test_suite_repairs_counts_weighted_fields_only():
    inc = {"p1": {"price.listed_price": 0.0, "coffee.roaster": 0.0, "coffee.variety": 1.0}}
    cand = {"p1": {"price.listed_price": 1.0, "coffee.roaster": 1.0, "coffee.variety": 0.0}}
    repairs, breakages = suite_repairs(inc, cand)
    assert (repairs, breakages) == (1, 1)  # roaster (weight 0.5) ignored


def test_gate_v2_accepts_significant_repair():
    inc = {f"p{i}": {"price.listed_price": 0.0} for i in range(5)}
    cand = {f"p{i}": {"price.listed_price": 1.0} for i in range(5)}
    ok, reasons, detail = gate_candidate_v2(
        suite_inc_scores=inc, suite_cand_scores=cand,
        gold_inc=_gold(0.85), gold_cand=_gold(0.85), gold_band=BAND)
    assert ok, reasons
    assert detail == {"repairs": 5, "breakages": 0, "p": pytest.approx(0.0312, abs=1e-3)}


def test_gate_v2_rejects_insignificant_or_balanced():
    inc = {f"p{i}": {"price.listed_price": 0.0} for i in range(3)}
    cand = {f"p{i}": {"price.listed_price": 1.0} for i in range(3)}
    ok, reasons, _ = gate_candidate_v2(
        suite_inc_scores=inc, suite_cand_scores=cand,
        gold_inc=_gold(0.85), gold_cand=_gold(0.85), gold_band=BAND)
    assert not ok and "repair test" in reasons[0]  # 3:0 -> p=0.125


def test_gate_v2_one_page_wobble_allowed_two_blocked():
    inc = {f"p{i}": {"price.listed_price": 0.0} for i in range(6)}
    cand = {f"p{i}": {"price.listed_price": 1.0} for i in range(6)}
    # one-page dip on a critical gold field (n=40): 0.900 -> 0.875 = 1 page -> allowed
    ok, reasons, _ = gate_candidate_v2(
        suite_inc_scores=inc, suite_cand_scores=cand,
        gold_inc=_gold(0.85, price=0.900), gold_cand=_gold(0.85, price=0.875), gold_band=BAND)
    assert ok, reasons
    # two-page dip: 0.900 -> 0.850 -> blocked
    ok, reasons, _ = gate_candidate_v2(
        suite_inc_scores=inc, suite_cand_scores=cand,
        gold_inc=_gold(0.85, price=0.900), gold_cand=_gold(0.85, price=0.850), gold_band=BAND)
    assert not ok and "critical gold field regression" in " ".join(reasons)


def test_gate_v2_gold_composite_and_length_still_block():
    inc = {f"p{i}": {"price.listed_price": 0.0} for i in range(6)}
    cand = {f"p{i}": {"price.listed_price": 1.0} for i in range(6)}
    ok, reasons, _ = gate_candidate_v2(
        suite_inc_scores=inc, suite_cand_scores=cand,
        gold_inc=_gold(0.85), gold_cand=_gold(0.80), gold_band=BAND)
    assert not ok and "gold composite regression" in " ".join(reasons)
    ok, reasons, _ = gate_candidate_v2(
        suite_inc_scores=inc, suite_cand_scores=cand,
        gold_inc=_gold(0.85), gold_cand=_gold(0.85), gold_band=BAND,
        candidate_len=1600, root_len=1000)
    assert not ok and "prompt length" in reasons[0]
