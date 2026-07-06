import pytest

from extraction_gym.core.budget import BudgetExceeded, BudgetTracker
from extraction_gym.eval.stats import compare, mcnemar_p, noise_band, paired_bootstrap_ci


def _report(composites: dict[str, float], field_means: dict, scores_by_page=None):
    return {
        "composite_mean": sum(composites.values()) / len(composites),
        "composite_by_page": composites,
        "field_means": field_means,
        "scores_by_page": scores_by_page or {},
    }


BASE_FIELDS = {"page_type": 1.0, "coffee.origin_country": 0.9, "coffee.process_method": 0.9,
               "coffee.variety": 0.9, "price.listed_price": 0.9, "price.package_grams": 0.9}


def test_noise_band_and_budget():
    r1 = _report({"a": 0.90, "b": 0.92}, BASE_FIELDS)
    r2 = _report({"a": 0.91, "b": 0.93}, BASE_FIELDS)
    band = noise_band([r1, r2])
    assert band["composite_std"] == pytest.approx(0.005)

    tracker = BudgetTracker(max_usd=0.01)
    cost = tracker.add("gpt-4o-mini", 10_000, 1_000)
    assert cost == pytest.approx(10_000 / 1e6 * 0.15 + 1_000 / 1e6 * 0.60)
    with pytest.raises(BudgetExceeded):
        tracker.add("gpt-5.5", 1_000_000, 0)
    with pytest.raises(KeyError):
        tracker.cost_of("mystery-model", 1, 1)


def test_bootstrap_and_mcnemar():
    deltas = {f"p{i}": 0.05 for i in range(10)}
    mean, low, high = paired_bootstrap_ci(deltas, iterations=200)
    assert mean == pytest.approx(0.05)
    assert low == pytest.approx(0.05) and high == pytest.approx(0.05)
    assert mcnemar_p(0, 0) == 1.0
    assert mcnemar_p(10, 0) < 0.01
    assert mcnemar_p(5, 5) == 1.0


def _band(std=0.005):
    return {"composite_std": std, "field_stds": {f: 0.01 for f in BASE_FIELDS}}


def test_compare_verdicts():
    incumbent = _report({"a": 0.80, "b": 0.80}, BASE_FIELDS)

    better = _report({"a": 0.90, "b": 0.90}, BASE_FIELDS)
    assert compare(incumbent, better, _band())["verdict"] == "PASS"

    within_noise = _report({"a": 0.805, "b": 0.805}, BASE_FIELDS)
    assert compare(incumbent, within_noise, _band())["verdict"] == "NOOP"

    regressed_fields = dict(BASE_FIELDS, **{"price.listed_price": 0.5})
    regression = _report({"a": 0.90, "b": 0.90}, regressed_fields)
    result = compare(incumbent, regression, _band())
    assert result["verdict"] == "FAIL"
    assert result["critical_regressions"][0]["field"] == "price.listed_price"
