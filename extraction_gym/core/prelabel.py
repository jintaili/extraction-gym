"""Prelabeling: run two independent extractors over every gold snapshot and produce
one human review file per page.

Review protocol (docs/LABELING_POLICY.md): agreements are auto-filled into the draft
label for spot-checking; disagreements are nulled and flagged for adjudication against
the snapshot text. Candidate values are keyed "a"/"b" so the reviewer can stay blind to
which model produced which; the mapping sits at the bottom of each file.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import yaml

from extraction_gym.adapters.coffee.extractor import CoffeeExtractor, ExtractionResult, production_prompt_id
from extraction_gym.core.cache import ExtractionCache

# Fields the labeling protocol hand-checks on every page regardless of model agreement.
HAND_CHECK_FIELDS = [
    "price.listed_price",
    "price.listed_currency",
    "price.package_grams",
    "price.bags_count",
    "price.price_type",
]

# Extractor self-reports, evidence, and server-side conversion artifacts: never part of the gold label.
EXCLUDED_FROM_LABEL = {
    "quality",
    "coffee.source_snippets",
    "price.assumptions",
    "price.price_100g_usd",
    "price.original_listed_price",
    "price.original_listed_currency",
}


def label_fields(extraction: dict) -> dict:
    flat: dict = {
        "page_type": extraction.get("page_type"),
        "is_specialty_coffee": extraction.get("is_specialty_coffee"),
    }
    for section in ("coffee", "price"):
        for key, value in extraction.get(section, {}).items():
            path = f"{section}.{key}"
            if path not in EXCLUDED_FROM_LABEL:
                flat[path] = value
    return flat


# Schema convention: these string fields use "unknown", never null/empty.
UNKNOWN_STRING_FIELDS = {"coffee.roaster_country", "coffee.origin_country", "coffee.origin_region"}


def canonicalize_label(label: dict) -> dict:
    """Normalize human/model label conventions so comparisons measure content, not style."""
    out = {}
    for field, value in label.items():
        if isinstance(value, str):
            value = value.strip()
        if field in UNKNOWN_STRING_FIELDS and (value is None or value == ""):
            value = "unknown"
        if field == "price.bags_count" and value == 1:
            value = None
        out[field] = value
    return out


def values_agree(a, b) -> bool:
    def norm(v):
        if isinstance(v, str):
            return v.strip().lower()
        if isinstance(v, list):
            return sorted(norm(x) for x in v)
        if isinstance(v, float) and v == int(v):
            return int(v)
        return v

    return norm(a) == norm(b)


async def prelabel_goldset(
    goldset: Path,
    *,
    models: list[str],
    concurrency: int = 4,
    limit: int | None = None,
) -> dict:
    assert len(models) == 2, "prelabel expects exactly two models"
    extractor = CoffeeExtractor()
    cache = ExtractionCache(goldset.parent.parent / ".cache" / "extractions")
    review_dir = goldset / "review"
    review_dir.mkdir(parents=True, exist_ok=True)

    metas = sorted((goldset / "pages").glob("*.meta.json"))
    if limit:
        metas = metas[:limit]
    semaphore = asyncio.Semaphore(concurrency)
    totals = {model: {"input_tokens": 0, "output_tokens": 0, "api_calls": 0} for model in models}

    async def run_one(meta_path: Path) -> str:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        page_id = meta_path.name.removesuffix(".meta.json")
        page_text = (goldset / "pages" / f"{page_id}.txt").read_text(encoding="utf-8")

        results: dict[str, dict] = {}
        for model in models:
            key = ExtractionCache.key(
                page_text=page_text,
                prompt_id=production_prompt_id(),
                model=model,
                params={"decoding": "default"},
            )
            cached = cache.get(key)
            if cached is None:
                async with semaphore:
                    result: ExtractionResult = await extractor.extract(
                        model=model, url=meta["final_url"], page_text=page_text
                    )
                cached = {
                    "extraction": result.extraction,
                    "model": model,
                    "prompt_id": result.prompt_id,
                    "input_tokens": result.input_tokens,
                    "output_tokens": result.output_tokens,
                }
                cache.put(key, cached)
                totals[model]["api_calls"] += 1
                totals[model]["input_tokens"] += result.input_tokens
                totals[model]["output_tokens"] += result.output_tokens
            results[model] = cached

        flat_a = label_fields(results[models[0]]["extraction"])
        flat_b = label_fields(results[models[1]]["extraction"])

        draft: dict = {}
        disagreements: dict = {}
        for field in flat_a:
            if values_agree(flat_a[field], flat_b.get(field)):
                draft[field] = flat_a[field]
            else:
                draft[field] = None
                disagreements[field] = {"a": flat_a[field], "b": flat_b.get(field)}

        review = {
            "page_id": page_id,
            "url": meta["url"],
            "final_url": meta["final_url"],
            "strata": meta["strata"],
            "review_status": "PENDING",
            "instructions": (
                "Fill every null in draft_label by adjudicating disagreements against the snapshot "
                "text (pages/{id}.txt), spot-check agreed values, and always hand-check the "
                "hand_check fields. Set review_status: VERIFIED when done."
            ),
            "draft_label": draft,
            "disagreements": disagreements,
            "hand_check": {f: {"a": flat_a.get(f), "b": flat_b.get(f)} for f in HAND_CHECK_FIELDS},
            "evidence": {
                "a_snippets": results[models[0]]["extraction"]["coffee"].get("source_snippets", []),
                "b_snippets": results[models[1]]["extraction"]["coffee"].get("source_snippets", []),
            },
            "models": {"a": models[0], "b": models[1], "prompt_id": results[models[0]]["prompt_id"]},
        }
        (review_dir / f"{page_id}.review.yaml").write_text(
            yaml.safe_dump(review, allow_unicode=True, sort_keys=False, width=100), encoding="utf-8"
        )
        return f"{page_id}  disagreements={len(disagreements)}"

    lines = await asyncio.gather(*(run_one(m) for m in metas))
    return {"pages": len(lines), "lines": sorted(lines), "totals": totals}
