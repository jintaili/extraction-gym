"""Evaluate a prompt artifact on the adversarial pressure suite (synthetic ground truth)."""

from __future__ import annotations

from pathlib import Path

from extraction_gym.adapters.coffee.scoring import composite, score_page
from extraction_gym.core.cache import ExtractionCache
from extraction_gym.core.prelabel import canonicalize_label, label_fields
from extraction_gym.core.registry import PromptArtifact


async def evaluate_on_suite(
    suite_root: Path, artifact: PromptArtifact, *, model: str, extract_fn, cache: ExtractionCache,
    budget=None,
) -> dict:
    import json

    composites = {}
    scores_by_page = {}
    for meta_path in sorted(suite_root.glob("*.meta.json")):
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        page_id = meta["page_id"]
        page_text = (suite_root / f"{page_id}.txt").read_text(encoding="utf-8")
        key = ExtractionCache.key(
            page_text=page_text, prompt_id=artifact.artifact_id, model=model,
            params={"decoding": "default"},
        )
        cached = cache.get(key)
        if cached is None:
            result = await extract_fn(
                model=model, url="https://synthetic.invalid/product", page_text=page_text,
                system_prompt=artifact.text,
            )
            cached = {"extraction": result.extraction, "input_tokens": result.input_tokens,
                      "output_tokens": result.output_tokens}
            cache.put(key, cached)
            if budget is not None:
                budget.add(model, result.input_tokens, result.output_tokens)
        scores = score_page(
            canonicalize_label(meta["label"]), canonicalize_label(label_fields(cached["extraction"]))
        )
        composites[page_id] = composite(scores)
        scores_by_page[page_id] = scores
    if not composites:
        raise RuntimeError(f"no pages in suite {suite_root}")
    return {
        "artifact_id": artifact.artifact_id,
        "pages": len(composites),
        "composite_mean": sum(composites.values()) / len(composites),
        "composite_by_page": composites,
        "scores_by_page": scores_by_page,
    }
