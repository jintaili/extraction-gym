import json

import pytest
import yaml

from extraction_gym.core.freeze import FreezeError, freeze
from extraction_gym.core.goldset import GoldsetStore
from extraction_gym.core.labelize import colddiff, labelize
from extraction_gym.core.prelabel import values_agree


def make_page(store, url="https://example.com/p1", text="page text", strata=("A",)):
    return store.store_snapshot(
        url=url, final_url=url, fetched_at="2026-07-05T00:00:00+00:00", text=text, strata=list(strata)
    )


def test_snapshot_immutable_and_strata_merge(tmp_path):
    store = GoldsetStore(tmp_path)
    first = make_page(store, strata=("A",))
    assert first.created
    again = make_page(store, text="DIFFERENT TEXT", strata=("E",))
    assert not again.created
    assert again.strata == ["A", "E"]
    assert (tmp_path / "pages" / f"{first.page_id}.txt").read_text() == "page text"


def test_verify_detects_corruption(tmp_path):
    store = GoldsetStore(tmp_path)
    page = make_page(store)
    assert store.verify_checksums() == []
    (tmp_path / "pages" / f"{page.page_id}.txt").write_text("tampered")
    assert store.verify_checksums() == [page.page_id]


def test_canonicalize_label_conventions():
    from extraction_gym.core.prelabel import canonicalize_label

    label = {"coffee.roaster_country": None, "coffee.origin_region": "", "price.bags_count": 1, "f": " x "}
    canon = canonicalize_label(label)
    assert canon["coffee.roaster_country"] == "unknown"
    assert canon["coffee.origin_region"] == "unknown"
    assert canon["price.bags_count"] is None
    assert canon["f"] == "x"


def test_values_agree_normalization():
    assert values_agree("Washed", "washed")
    assert values_agree(["Geisha", "SL-9"], ["sl-9", "geisha"])
    assert values_agree(37.0, 37)
    assert not values_agree("washed", "natural")
    assert not values_agree(None, "washed")


def _write_review(goldset, page_id, status, label, disagreements=None):
    review_dir = goldset / "review"
    review_dir.mkdir(parents=True, exist_ok=True)
    doc = {
        "page_id": page_id,
        "url": f"https://example.com/{page_id}",
        "strata": ["A"],
        "review_status": status,
        "draft_label": label,
        "disagreements": disagreements or {},
    }
    (review_dir / f"{page_id}.review.yaml").write_text(yaml.safe_dump(doc))


def _write_cold(goldset, page_id, label, status="DONE"):
    cold_dir = goldset / "coldlabels"
    cold_dir.mkdir(parents=True, exist_ok=True)
    doc = {"page_id": page_id, "status": status, "label": label}
    (cold_dir / f"{page_id}.cold.yaml").write_text(yaml.safe_dump(doc))


def test_labelize_only_verified_and_warns_on_null_disagreements(tmp_path):
    _write_review(tmp_path, "aaa", "VERIFIED", {"f1": "x", "f2": None}, {"f2": {"a": 1, "b": 2}})
    _write_review(tmp_path, "bbb", "PENDING", {"f1": "y"})
    summary = labelize(tmp_path)
    assert summary["written"] == ["aaa"]
    assert summary["skipped_not_verified"] == ["bbb"]
    assert any("f2" in w for w in summary["warnings"])
    assert json.loads((tmp_path / "labels" / "aaa.json").read_text())["label"]["f1"] == "x"


def test_colddiff_counts_changes(tmp_path):
    _write_review(tmp_path, "aaa", "VERIFIED", {"f1": "x", "f2": "y", "f3": "z"})
    labelize(tmp_path)
    _write_cold(tmp_path, "aaa", {"f1": "x", "f2": "WRONG", "f3": "Z"})
    audit = colddiff(tmp_path)
    assert audit["audit_pages"] == 1
    assert audit["fields_compared"] == 3
    assert audit["fields_changed"] == 1
    assert audit["per_field"] == {"f2": 1}


def test_release_attestation_roundtrip(tmp_path):
    from extraction_gym.core.release import check_attestation, write_attestation

    manifest = {"frozen_at": "t", "page_count": 42}
    att = write_attestation(
        out_path=tmp_path / "att.json", artifact_id="ce68bd4c4e", prompt_text="the prompt",
        gold_version="v1", gold_manifest=manifest, verdict="NOOP_ROOT",
        evidence={"composite": 0.892},
    )
    assert check_attestation(att, "the prompt") == []
    assert check_attestation(att, "tampered prompt") != []
    att_bad = dict(att, verdict="FAIL")
    assert any("not releasable" in p for p in check_attestation(att_bad, "the prompt"))


def test_freeze_requires_labels_and_audit_then_is_immutable(tmp_path):
    store = GoldsetStore(tmp_path)
    page = make_page(store)
    with pytest.raises(FreezeError, match="lack verified labels"):
        freeze(tmp_path, version="v1")

    _write_review(tmp_path, page.page_id, "VERIFIED", {"f1": "x"})
    labelize(tmp_path)
    _write_cold(tmp_path, page.page_id, {"f1": "x"})
    manifest = freeze(tmp_path, version="v1")
    assert manifest["page_count"] == 1
    assert manifest["residual_label_error"]["rate"] == 0.0
    assert store.verify_manifest() == []

    with pytest.raises(FreezeError, match="immutable"):
        freeze(tmp_path, version="v1")

    (tmp_path / "pages" / f"{page.page_id}.txt").write_text("tampered")
    assert any("checksum mismatch" in p for p in store.verify_manifest())
