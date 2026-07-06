import asyncio
import json
from dataclasses import dataclass

import pytest

from extraction_gym.core.cache import ExtractionCache
from extraction_gym.core.registry import PromptRegistry
from extraction_gym.eval.runner import evaluate_artifact


def test_registry_register_lineage_ledger(tmp_path):
    reg = PromptRegistry(tmp_path / "registry")
    root = reg.register(text="prompt v0", mutation_note="root", source="human")
    child = reg.register(text="prompt v1", parent_id=root.artifact_id, mutation_note="one change", source="optimizer")
    assert reg.register(text="prompt v0", mutation_note="dup", source="human").artifact_id == root.artifact_id

    chain = reg.lineage(child.artifact_id)
    assert [a.artifact_id for a in chain] == [root.artifact_id, child.artifact_id]

    with pytest.raises(ValueError):
        reg.register(text="x", parent_id="nonexistent0", mutation_note="bad", source="optimizer")

    reg.append_ledger({"event": "eval", "artifact_id": root.artifact_id})
    assert reg.ledger_rows()[0]["artifact_id"] == root.artifact_id


@dataclass
class FakeResult:
    extraction: dict
    input_tokens: int = 10
    output_tokens: int = 5


def _setup_goldset(tmp_path):
    (tmp_path / "pages").mkdir()
    (tmp_path / "labels").mkdir()
    for pid, text in [("aaa", "page one"), ("bbb", "page two")]:
        (tmp_path / "pages" / f"{pid}.txt").write_text(text)
        (tmp_path / "pages" / f"{pid}.meta.json").write_text(
            json.dumps({"url": f"https://x/{pid}", "final_url": f"https://x/{pid}", "strata": ["A"],
                        "sha256": "0", "chars": 8, "fetched_at": "t"})
        )
        label = {"page_id": pid, "url": f"https://x/{pid}", "strata": ["A"],
                 "label": {"page_type": "coffee_product", "coffee.origin_country": "Peru",
                           "price.listed_price": 20.0}}
        (tmp_path / "labels" / f"{pid}.json").write_text(json.dumps(label))


def test_evaluate_artifact_scores_and_caches(tmp_path):
    _setup_goldset(tmp_path)
    reg = PromptRegistry(tmp_path / "registry")
    artifact = reg.register(text="the prompt", mutation_note="root", source="human")
    cache = ExtractionCache(tmp_path / "cache")
    calls = {"n": 0}

    async def fake_extract(*, model, url, page_text, system_prompt=None):
        calls["n"] += 1
        assert system_prompt == "the prompt"
        return FakeResult(
            extraction={
                "page_type": "coffee_product",
                "is_specialty_coffee": True,
                "coffee": {"origin_country": "Peru", "source_snippets": []},
                "price": {"listed_price": 20.0, "assumptions": []},
                "quality": {},
            }
        )

    report = asyncio.run(
        evaluate_artifact(tmp_path, artifact, model="m", extract_fn=fake_extract, cache=cache)
    )
    assert report["pages"] == 2
    assert report["field_means"]["coffee.origin_country"] == 1.0
    assert report["field_means"]["price.listed_price"] == 1.0
    assert calls["n"] == 2

    report2 = asyncio.run(
        evaluate_artifact(tmp_path, artifact, model="m", extract_fn=fake_extract, cache=cache)
    )
    assert calls["n"] == 2, "second run must be fully cached"
    assert report2["usage"]["api_calls"] == 0
