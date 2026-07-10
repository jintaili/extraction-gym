"""Consume the human-arbitrated disputes.yaml and produce:
  1. the audited label set (labels-audited/, corrections traceable to rulings)
  2. the measured label-error lower bound (official vs audited on the sample)
  3. dual scorings of both baselines (official-gold vs audited-gold)

Run AFTER the human fills `resolution:` on every dispute:
  resolution: official            # official label correct
  resolution: gpt-4o-mini         # that model's value is correct
  resolution: claude-haiku-4-5    # that model's value is correct
  resolution: models              # both models agree AND their value is correct
  resolution: "<exact value>"     # none of the above; human supplies the value
"""

from __future__ import annotations

import json
from pathlib import Path

import yaml

GOLD = Path("goldset/sroie-v1")


def main() -> None:
    doc = yaml.safe_load((GOLD / "audit" / "disputes.yaml").read_text())
    unresolved = [d for d in doc["disputes"] if d.get("resolution") in (None, "")]
    if unresolved:
        raise SystemExit(f"{len(unresolved)} disputes unresolved; first: "
                         f"{unresolved[0]['page_id']}/{unresolved[0]['field']}")

    from extraction_gym.adapters.sroie.scoring import score_page

    corrections = []
    for d in doc["disputes"]:
        r = d["resolution"]
        if r == "official":
            continue
        if r == "models":
            f = d["field"]
            a, b = d["candidates"]["gpt-4o-mini"], d["candidates"]["claude-haiku-4-5"]
            if score_page({f: a}, {f: b})[f] != 1.0:
                raise SystemExit(f"{d['page_id']}/{f}: resolution 'models' but the two models "
                                 f"disagree ({a!r} vs {b!r}); name the model or give the value")
            value = a
        elif r in ("gpt-4o-mini", "claude-haiku-4-5"):
            value = d["candidates"][r]
        else:
            value = r
        corrections.append({"page_id": d["page_id"], "field": d["field"],
                            "official": d["candidates"]["official"], "audited": value})

    audited_dir = GOLD / "labels-audited"
    audited_dir.mkdir(exist_ok=True)
    sample_ids = sorted({d["page_id"] for d in doc["disputes"]} |
                        set())  # audited labels exist only for the sampled 40
    # regenerate all sampled labels (start from official, apply corrections)
    import random
    rng = random.Random(doc["seed"])
    all_ids = sorted(p.stem for p in (GOLD / "labels-official").glob("*.json"))
    sample_ids = sorted(rng.sample(all_ids, doc["sample_receipts"]))
    corr_map = {(c["page_id"], c["field"]): c["audited"] for c in corrections}
    for page_id in sample_ids:
        label = json.loads((GOLD / "labels-official" / f"{page_id}.json").read_text())["label"]
        for field in label:
            if (page_id, field) in corr_map:
                label[field] = corr_map[(page_id, field)]
        (audited_dir / f"{page_id}.json").write_text(json.dumps({
            "page_id": page_id, "label": label, "source": "audited",
        }, ensure_ascii=False, indent=2) + "\n")

    fields_total = doc["fields_compared"]
    error_rate = len(corrections) / fields_total
    result = {
        "sample_receipts": doc["sample_receipts"],
        "fields_compared": fields_total,
        "auto_accepted": doc["auto_accepted"],
        "disputes": len(doc["disputes"]),
        "official_label_errors_found": len(corrections),
        "label_error_lower_bound": round(error_rate, 4),
        "note": "LOWER BOUND: triple-agreement auto-accepts were not human-read, and "
                "training-data contamination correlates model votes with official labels.",
        "corrections": corrections,
    }
    (GOLD / "audit" / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(f"label-error lower bound: {error_rate:.3%} "
          f"({len(corrections)}/{fields_total} fields; corrections in audit/result.json)")


if __name__ == "__main__":
    main()
