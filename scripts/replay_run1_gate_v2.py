"""Replay run1's 12 rejected candidates under gate v2 (validation: all must still be
rejected). Mostly cache-served. Writes runs/replay-run1-v2.json."""
import asyncio, json
from pathlib import Path
from dotenv import load_dotenv; load_dotenv(".env")
from coffee_value_app.config import load_settings
from extraction_gym.adapters.coffee.extractor import CoffeeExtractor
from extraction_gym.core.cache import ExtractionCache
from extraction_gym.core.registry import PromptRegistry
from extraction_gym.eval.runner import evaluate_artifact
from extraction_gym.eval.suite_eval import evaluate_on_suite
from extraction_gym.optimizer.loop import gate_candidate_v2

registry = PromptRegistry(Path("registry"))
extractor = CoffeeExtractor()
model = load_settings().extraction_model
cache = ExtractionCache(Path(".cache") / "extractions")
suite = Path("suites/adversarial")

async def main():
    root_id = "ce68bd4c4e"
    inc_suite = await evaluate_on_suite(suite, registry.get(root_id), model=model, extract_fn=extractor.extract, cache=cache)
    inc_gold = await evaluate_artifact(Path("goldset/v1"), registry.get(root_id), model=model, extract_fn=extractor.extract, cache=cache)
    band = json.loads(Path("runs/noise-ce68bd4c4e-gpt-4o-mini.json").read_text())
    state = json.loads(Path("runs/run1/state.json").read_text())
    rows = []
    for h in state["history"]:
        for c in h["candidates"]:
            aid = c["artifact_id"]
            cs = await evaluate_on_suite(suite, registry.get(aid), model=model, extract_fn=extractor.extract, cache=cache)
            cg = await evaluate_artifact(Path("goldset/v1"), registry.get(aid), model=model, extract_fn=extractor.extract, cache=cache)
            ok, reasons, detail = gate_candidate_v2(
                suite_inc_scores=inc_suite["scores_by_page"], suite_cand_scores=cs["scores_by_page"],
                gold_inc=inc_gold, gold_cand=cg, gold_band=band,
                candidate_len=len(registry.get(aid).text), root_len=len(registry.get(root_id).text))
            rows.append({"artifact_id": aid, "accepted": ok, "reasons": reasons, **detail})
            print(aid[:6], "ACCEPT" if ok else "reject", detail)
    accepted = sum(r["accepted"] for r in rows)
    out = {"accepted": accepted, "total": len(rows), "expect": 0, "rows": rows}
    Path("runs/replay-run1-v2.json").write_text(json.dumps(out, indent=2))
    print(f"run1 replay under v2: {accepted}/{len(rows)} accepted (expect 0)")

asyncio.run(main())
