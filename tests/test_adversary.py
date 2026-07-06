from extraction_gym.adversary.generator import deterministic_sanity
from extraction_gym.adversary.round import detect_hit
from extraction_gym.adversary.suite import SuiteStore


def test_deterministic_sanity():
    assert deterministic_sanity("short", "blend") != []
    long_no_price = "word " * 100
    assert "no price/currency marker on page" in deterministic_sanity(long_no_price, "blend")
    assert deterministic_sanity(long_no_price, "missing-price page") == []
    assert deterministic_sanity(("Great coffee $18.00 " * 30), "blend") == []


def test_detect_hit_only_weighted_fields():
    gold = {"page_type": "coffee_product", "coffee.origin_country": "Peru",
            "price.listed_price": 20.0, "coffee.roaster": "X"}
    same = dict(gold)
    assert detect_hit(gold, same) == []
    wrong_price = dict(gold, **{"price.listed_price": 25.0})
    assert detect_hit(gold, wrong_price) == ["price.listed_price"]
    wrong_low_weight = dict(gold, **{"coffee.roaster": "Y"})
    assert detect_hit(gold, wrong_low_weight) == []

    long_text = "a very long tasting description with many words " * 3
    gold_text = dict(gold, **{"coffee.sensory_text": long_text})
    near_miss = dict(gold, **{"coffee.sensory_text": long_text + "extra tail"})
    assert detect_hit(gold_text, near_miss) == [], "trivial span diff must not be a hit"
    real_miss = dict(gold, **{"coffee.sensory_text": "completely different notes"})
    assert detect_hit(gold_text, real_miss) == ["coffee.sensory_text"]


def test_suite_store_roundtrip(tmp_path):
    suite = SuiteStore(tmp_path / "suite")
    page_id = suite.store(
        page_text="Title: Fake\nGreat coffee $18.00",
        label={"page_type": "coffee_product"},
        category="blend presented like a single origin",
        invented_category=False,
        target_artifact_id="ce68bd4c4e",
        generator_model="g",
        judge_model="j",
        judges={"consistency": {"unsupported_fields": []}, "realism": {"score": 5}},
        incumbent={"model": "m", "hit_fields": ["price.listed_price"], "extraction": {}},
    )
    pages = suite.pages()
    assert pages[0]["page_id"] == page_id
    assert pages[0]["incumbent"]["hit_fields"] == ["price.listed_price"]
