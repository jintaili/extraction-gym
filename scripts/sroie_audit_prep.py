"""SROIE label audit prep (HITL arbitration forms).

Protocol (plan step 3): two blind prelabel models from different provider families
(gpt-4o-mini, claude-haiku-4-5) labeled every receipt with the naive prompt. On a seeded
40-receipt sample, diff both against the official label per field:
  - triple agreement (both models == official)  -> auto-accept, no human look
  - any disagreement                            -> dispute form for human arbitration

Lower-bound honesty: models are trained on SROIE, so agreement with the official label is
partially recitation, not independent confirmation - triple agreement can hide errors.
The audited error rate is therefore a LOWER BOUND on SROIE label error.

Each dispute form carries the three candidates, a receipt excerpt, deterministic
page-evidence checks (is each candidate a verbatim substring of the OCR text), and a
drafted recommendation the human can accept or override.
"""

from __future__ import annotations

import json
import random
import re
from pathlib import Path

import yaml

from extraction_gym.adapters.sroie.scoring import score_page
from extraction_gym.core.cache import ExtractionCache

GOLD = Path("goldset/sroie-v1")
SEED = 20260709
SAMPLE = 40


def load_prelabel(page_text: str, provider: str) -> dict:
    cache = ExtractionCache(Path(".cache") / "sroie")
    key = ExtractionCache.key(page_text=page_text, prompt_id="naive-v1", model=provider, params={})
    cached = cache.get(key)
    return cached["extraction"] if cached else {}


def on_page(value, text_norm: str) -> bool:
    if value is None:
        return False
    v = re.sub(r"\s+", " ", str(value).strip().casefold())
    return v in text_norm


def main() -> None:
    ids = sorted(p.stem for p in (GOLD / "labels-official").glob("*.json"))
    rng = random.Random(SEED)
    sample = sorted(rng.sample(ids, SAMPLE))

    disputes = []
    auto_accepted = 0
    fields_total = 0
    for page_id in sample:
        official = json.loads((GOLD / "labels-official" / f"{page_id}.json").read_text())["label"]
        text = (GOLD / "pages" / f"{page_id}.txt").read_text()
        text_norm = re.sub(r"\s+", " ", text.casefold())
        a = load_prelabel(text, "gpt-4o-mini")
        b = load_prelabel(text, "claude-haiku-4-5")
        score_a = score_page(official, a)
        score_b = score_page(official, b)
        for field in ("company", "date", "address", "total"):
            fields_total += 1
            if score_a[field] == 1.0 and score_b[field] == 1.0:
                auto_accepted += 1
                continue
            candidates = {
                "official": official.get(field),
                "gpt-4o-mini": a.get(field),
                "claude-haiku-4-5": b.get(field),
            }
            evidence = {k: on_page(v, text_norm) for k, v in candidates.items()}
            models_agree = score_page(a, b)[field] == 1.0
            if models_agree and evidence["gpt-4o-mini"] and not evidence["official"]:
                rec = "models (both agree, page-supported; official not found verbatim on page)"
            elif evidence["official"]:
                rec = "official (page-supported)"
            else:
                rec = "UNCLEAR - read the excerpt"
            excerpt_lines = [
                line for line in text.splitlines()
                if any(str(v) and str(v).casefold()[:12] in line.casefold() for v in candidates.values() if v)
            ]
            disputes.append({
                "page_id": page_id,
                "field": field,
                "candidates": candidates,
                "verbatim_on_page": evidence,
                "drafted_recommendation": rec,
                "resolution": None,  # HUMAN: set to "official" | "models" | exact correct value
                "receipt_excerpt": "\n".join(excerpt_lines[:8]) or text[:400],
            })

    out = GOLD / "audit"
    out.mkdir(exist_ok=True)
    (out / "disputes.yaml").write_text(yaml.safe_dump({
        "protocol": "triple-agreement auto-accept; human arbitrates disputes; result is a LOWER BOUND (training-data contamination correlates the votes)",
        "seed": SEED, "sample_receipts": SAMPLE,
        "fields_compared": fields_total, "auto_accepted": auto_accepted,
        "disputes": disputes,
    }, allow_unicode=True, sort_keys=False, width=110), encoding="utf-8")
    print(f"sample {SAMPLE} receipts, {fields_total} fields: {auto_accepted} auto-accepted, "
          f"{len(disputes)} disputes -> {out}/disputes.yaml")


if __name__ == "__main__":
    main()
