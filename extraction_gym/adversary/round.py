"""One adversary round: generate K pressure pages targeting an incumbent artifact.

Per page: sample a failure category (30% chance: instruct the generator to invent a new
one), generate page+labels, deterministic sanity checks, consistency judge, realism
judge, then run the incumbent and diff. Accepted pages (hits and non-hits) are stored;
discards are counted per gate for the report. Spend is budget-capped.
"""

from __future__ import annotations

import random
from pathlib import Path

from extraction_gym.adapters.coffee.scoring import FIELD_SPECS, score_page
from extraction_gym.adversary.generator import AdversaryGenerator, deterministic_sanity
from extraction_gym.adversary.judges import Judges
from extraction_gym.adversary.suite import SuiteStore
from extraction_gym.core.budget import BudgetTracker
from extraction_gym.core.cache import ExtractionCache
from extraction_gym.core.prelabel import canonicalize_label, label_fields
from extraction_gym.core.registry import PromptArtifact

SEED_CATEGORIES = [
    "multi-variant page where the default variant is a small sampler",
    "subscription-only pricing where the shown price is per shipment",
    "non-English page (Japanese, Danish, Italian, or Korean) with structured spec lines",
    "co-ferment or infused coffee described only in marketing prose",
    "blend presented like a single origin",
    "sold-out product with a stale price still displayed",
    "wholesale page with tiered pricing",
    "region-ambiguous origin (place name that exists in two producing countries)",
    "decaf mentioned only in a variant name",
    "embedded variant weight is shipping weight, larger than stated bag content",
    "displayed price rounds differently than the embedded variant price",
    "stale meta description contradicting current page body",
]

HIT_WEIGHT_THRESHOLD = 2.0
# Continuous token-F1 fields never score exactly 1.0 on nontrivial spans; only a
# substantial divergence counts as a hit there. Exact/tolerance fields hit on any miss.
CONTINUOUS_FIELDS = {"coffee.sensory_text", "coffee.producer_text"}
CONTINUOUS_HIT_BELOW = 0.8


def detect_hit(gold_label: dict, incumbent_label: dict) -> list[str]:
    scores = score_page(canonicalize_label(gold_label), canonicalize_label(incumbent_label))
    hits = []
    for field, score in scores.items():
        if score is None or FIELD_SPECS[field][1] < HIT_WEIGHT_THRESHOLD:
            continue
        threshold = CONTINUOUS_HIT_BELOW if field in CONTINUOUS_FIELDS else 0.999
        if score < threshold:
            hits.append(field)
    return hits


async def run_round(
    *,
    count: int,
    target: PromptArtifact,
    generator: AdversaryGenerator,
    judges: Judges,
    incumbent_extract_fn,
    incumbent_model: str,
    suite: SuiteStore,
    cache: ExtractionCache,
    budget: BudgetTracker,
    seed: int = 20260706,
) -> dict:
    rng = random.Random(seed)
    stats = {"generated": 0, "sanity_discard": 0, "consistency_discard": 0, "realism_discard": 0,
             "accepted": 0, "hits": 0}
    by_category: dict[str, dict] = {}
    stored: list[dict] = []

    for _ in range(count):
        category = rng.choice(SEED_CATEGORIES)
        invent = rng.random() < 0.3
        page = await generator.generate(category, invent=invent)
        budget.add(generator.model, page.input_tokens, page.output_tokens)
        stats["generated"] += 1

        if invent and page.page_text.startswith("CATEGORY: "):
            first, _, rest = page.page_text.partition("\n")
            category = first.removeprefix("CATEGORY: ").strip()
            page_text = rest
        else:
            page_text = page.page_text
        flat_label = label_fields(page.extraction)

        problems = deterministic_sanity(page_text, category)
        if problems:
            stats["sanity_discard"] += 1
            continue
        consistency = await judges.consistency(page_text, flat_label)
        budget.add(judges.model, consistency.input_tokens, consistency.output_tokens)
        if not consistency.passed:
            stats["consistency_discard"] += 1
            continue
        realism = await judges.realism(page_text)
        budget.add(judges.model, realism.input_tokens, realism.output_tokens)
        if not realism.passed:
            stats["realism_discard"] += 1
            continue

        key = ExtractionCache.key(
            page_text=page_text, prompt_id=target.artifact_id, model=incumbent_model,
            params={"decoding": "default"},
        )
        cached = cache.get(key)
        if cached is None:
            result = await incumbent_extract_fn(
                model=incumbent_model, url="https://synthetic.invalid/product",
                page_text=page_text, system_prompt=target.text,
            )
            cached = {"extraction": result.extraction, "input_tokens": result.input_tokens,
                      "output_tokens": result.output_tokens}
            cache.put(key, cached)
            budget.add(incumbent_model, result.input_tokens, result.output_tokens)

        hit_fields = detect_hit(flat_label, label_fields(cached["extraction"]))
        stats["accepted"] += 1
        stats["hits"] += bool(hit_fields)
        cat = by_category.setdefault(category, {"accepted": 0, "hits": 0})
        cat["accepted"] += 1
        cat["hits"] += bool(hit_fields)

        page_id = suite.store(
            page_text=page_text,
            label=flat_label,
            category=category,
            invented_category=invent,
            target_artifact_id=target.artifact_id,
            generator_model=generator.model,
            judge_model=judges.model,
            judges={"consistency": consistency.detail, "realism": realism.detail},
            incumbent={"model": incumbent_model, "hit_fields": hit_fields,
                       "extraction": cached["extraction"]},
        )
        stored.append({"page_id": page_id, "category": category, "hit_fields": hit_fields})

    return {"stats": stats, "by_category": by_category, "stored": stored,
            "spend_usd": round(budget.spent_usd, 4), "spend_by_model": {
                m: round(v, 4) for m, v in budget.by_model.items()}}
