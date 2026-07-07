"""Post-GEPA analysis: register GEPA's winning instructions as a gym artifact
("transplant"), evaluate it in the production runtime on frozen gold, and run the
gated comparison against the root baseline.

Usage: .venv/bin/python scripts/gepa_transplant.py
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from coffee_value_app.config import load_settings

from extraction_gym.adapters.coffee.extractor import CoffeeExtractor
from extraction_gym.core.cache import ExtractionCache
from extraction_gym.core.registry import PromptRegistry
from extraction_gym.eval.runner import evaluate_artifact
from extraction_gym.eval.stats import compare


def main() -> None:
    results = json.loads(Path("reports/gepa-baseline.json").read_text(encoding="utf-8"))
    instructions = results["optimized_instructions"]
    if not instructions:
        raise SystemExit("no optimized instructions in gepa-baseline.json")

    registry = PromptRegistry(Path("registry"))
    root = registry.get("ce68bd4c4e")
    transplant = registry.register(
        text=instructions,
        parent_id=root.artifact_id,
        mutation_note="GEPA-optimized instructions transplanted into production runtime",
        source="optimizer",
    )
    print(f"transplant artifact: {transplant.artifact_id}")

    extractor = CoffeeExtractor()
    model = load_settings().extraction_model
    report = asyncio.run(
        evaluate_artifact(
            Path("goldset/v1"), transplant, model=model, extract_fn=extractor.extract,
            cache=ExtractionCache(Path(".cache") / "extractions"),
        )
    )
    out_dir = Path("runs") / f"eval-{transplant.artifact_id}-{model}"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "results.json").write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"transplant on gold (production runtime): {report['composite_mean']:.4f}")

    baseline = json.loads(Path(f"runs/eval-ce68bd4c4e-{model}/results.json").read_text())
    band = json.loads(Path(f"runs/noise-ce68bd4c4e-{model}.json").read_text())
    verdict = compare(baseline, report, band)
    (Path("reports") / "gepa-transplant-verdict.json").write_text(
        json.dumps(verdict, ensure_ascii=False, indent=2)
    )
    print(f"gate verdict on transplant: {verdict['verdict']}")
    print(f"  delta {verdict['mean_composite_delta']:+.4f}, CI {verdict['bootstrap_ci95']}")
    for r in verdict["critical_regressions"]:
        print(f"  regression: {r['field']} {r['incumbent']:.3f} -> {r['candidate']:.3f}")
    registry.append_ledger(
        {"event": "gepa_transplant", "artifact_id": transplant.artifact_id,
         "gold_composite": report["composite_mean"], "verdict": verdict["verdict"]}
    )


if __name__ == "__main__":
    main()
