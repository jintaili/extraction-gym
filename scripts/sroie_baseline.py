"""Evaluate the naive baseline prompt on SROIE (official labels), both providers.

Usage: .venv/bin/python scripts/sroie_baseline.py [--limit N]
"""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from dotenv import load_dotenv

from coffee_value_app.config import load_settings

from extraction_gym.adapters.sroie.extractor import (
    NAIVE_BASELINE_PROMPT,
    AnthropicSroieExtractor,
    OpenAISroieExtractor,
)
from extraction_gym.adapters.sroie.scoring import FIELD_SPECS, composite, score_page
from extraction_gym.core.cache import ExtractionCache

GOLD = Path("goldset/sroie-v1")


async def run(extractor, provider_tag: str, limit: int | None, concurrency: int = 8) -> dict:
    cache = ExtractionCache(Path(".cache") / "sroie")
    label_files = sorted((GOLD / "labels-official").glob("*.json"))
    if limit:
        label_files = label_files[:limit]
    semaphore = asyncio.Semaphore(concurrency)
    usage = {"input_tokens": 0, "output_tokens": 0, "api_calls": 0}

    async def one(path: Path):
        doc = json.loads(path.read_text())
        page_id = doc["page_id"]
        text = (GOLD / "pages" / f"{page_id}.txt").read_text()
        key = ExtractionCache.key(page_text=text, prompt_id="naive-v1", model=provider_tag, params={})
        cached = cache.get(key)
        if cached is None:
            async with semaphore:
                result = await extractor.extract(page_text=text, system_prompt=NAIVE_BASELINE_PROMPT)
            cached = {"extraction": result.extraction, "input_tokens": result.input_tokens,
                      "output_tokens": result.output_tokens}
            cache.put(key, cached)
            usage["api_calls"] += 1
            usage["input_tokens"] += result.input_tokens
            usage["output_tokens"] += result.output_tokens
        return page_id, score_page(doc["label"], cached["extraction"])

    results = dict(await asyncio.gather(*(one(p) for p in label_files)))
    field_means = {f: sum(r[f] for r in results.values()) / len(results) for f in FIELD_SPECS}
    return {
        "provider": provider_tag,
        "pages": len(results),
        "composite_mean": sum(composite(r) for r in results.values()) / len(results),
        "field_means": field_means,
        "composite_by_page": {k: composite(v) for k, v in results.items()},
        "scores_by_page": results,
        "usage": usage,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()
    load_dotenv(".env")
    settings = load_settings()

    out_dir = Path("reports")
    for extractor, tag in [
        (OpenAISroieExtractor(api_key=settings.openai_api_key), "gpt-4o-mini"),
        (AnthropicSroieExtractor(), "claude-haiku-4-5"),
    ]:
        report = asyncio.run(run(extractor, tag, args.limit))
        (out_dir / f"sroie-naive-{tag}.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n")
        print(f"{tag}: composite {report['composite_mean']:.4f} on {report['pages']} receipts "
              f"| fields: " + ", ".join(f"{f}={m:.3f}" for f, m in report["field_means"].items()))


if __name__ == "__main__":
    main()
