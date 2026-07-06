"""Evaluate a prompt artifact over a labeled gold set.

Extractions are cached by hash(page_text, prompt_id, model, params); re-running an eval
on unchanged inputs costs zero API calls. Scoring is fully deterministic (core.scorers).
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from extraction_gym.adapters.coffee.scoring import FIELD_SPECS, composite, score_page
from extraction_gym.core.cache import ExtractionCache
from extraction_gym.core.prelabel import canonicalize_label, label_fields
from extraction_gym.core.registry import PromptArtifact


def load_gold_labels(goldset: Path) -> dict[str, dict]:
    labels = {}
    for path in sorted((goldset / "labels").glob("*.json")):
        doc = json.loads(path.read_text(encoding="utf-8"))
        labels[doc["page_id"]] = canonicalize_label(doc["label"])
    return labels


async def evaluate_artifact(
    goldset: Path,
    artifact: PromptArtifact,
    *,
    model: str,
    extract_fn,
    cache: ExtractionCache,
    concurrency: int = 4,
    cache_disabled: bool = False,
    run_tag: str = "",
) -> dict:
    """extract_fn(model, url, page_text, system_prompt) -> ExtractionResult-like."""
    gold = load_gold_labels(goldset)
    if not gold:
        raise RuntimeError(f"no gold labels in {goldset}/labels; run gym labelize first")

    semaphore = asyncio.Semaphore(concurrency)
    totals = {"input_tokens": 0, "output_tokens": 0, "api_calls": 0}

    async def run_one(page_id: str) -> tuple[str, dict]:
        meta = json.loads((goldset / "pages" / f"{page_id}.meta.json").read_text(encoding="utf-8"))
        page_text = (goldset / "pages" / f"{page_id}.txt").read_text(encoding="utf-8")
        params = {"decoding": "default"}
        if cache_disabled:
            params["noise_run"] = run_tag
        key = ExtractionCache.key(
            page_text=page_text, prompt_id=artifact.artifact_id, model=model, params=params
        )
        cached = None if cache_disabled else cache.get(key)
        if cached is None:
            async with semaphore:
                result = await extract_fn(
                    model=model, url=meta["final_url"], page_text=page_text, system_prompt=artifact.text
                )
            cached = {
                "extraction": result.extraction,
                "input_tokens": result.input_tokens,
                "output_tokens": result.output_tokens,
            }
            cache.put(key, cached)
            totals["api_calls"] += 1
            totals["input_tokens"] += result.input_tokens
            totals["output_tokens"] += result.output_tokens
        got = canonicalize_label(label_fields(cached["extraction"]))
        return page_id, score_page(gold[page_id], got)

    results = dict(await asyncio.gather(*(run_one(pid) for pid in sorted(gold))))

    per_field: dict[str, list[float]] = {f: [] for f in FIELD_SPECS}
    composites = {}
    for page_id, scores in results.items():
        composites[page_id] = composite(scores)
        for field, score in scores.items():
            if score is not None:
                per_field[field].append(score)

    return {
        "artifact_id": artifact.artifact_id,
        "model": model,
        "pages": len(results),
        "composite_mean": sum(composites.values()) / len(composites),
        "composite_by_page": composites,
        "scores_by_page": results,
        "field_means": {
            f: (sum(v) / len(v) if v else None) for f, v in per_field.items()
        },
        "field_coverage": {f: len(v) for f, v in per_field.items()},
        "usage": totals,
    }


def report_markdown(report: dict) -> str:
    lines = [
        f"# Eval report: artifact {report['artifact_id']} on {report['pages']} pages",
        "",
        f"- model: {report['model']}",
        f"- composite (weighted mean over pages): **{report['composite_mean']:.4f}**",
        f"- api calls: {report['usage']['api_calls']}, tokens: "
        f"{report['usage']['input_tokens']} in / {report['usage']['output_tokens']} out",
        "",
        "| field | mean score | pages graded |",
        "|---|---|---|",
    ]
    for field, mean in sorted(report["field_means"].items(), key=lambda kv: (kv[1] is None, kv[1])):
        shown = "n/a" if mean is None else f"{mean:.3f}"
        lines.append(f"| {field} | {shown} | {report['field_coverage'][field]} |")
    return "\n".join(lines) + "\n"
