"""Convert VERIFIED review files into gold labels, and audit cold labels against them.

gym labelize: review/<id>.review.yaml with review_status VERIFIED -> labels/<id>.json.
Nulls remaining on former disagreement fields are accepted (VERIFIED asserts they are
deliberate) but reported, so accidental skips are visible.

gym colddiff: for every DONE cold form with a final label, report field-level changes.
The change rate over the audit subset is the referee's stated residual label error.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import yaml

from extraction_gym.core.prelabel import canonicalize_label, values_agree


def labelize(goldset: Path) -> dict:
    labels_dir = goldset / "labels"
    labels_dir.mkdir(parents=True, exist_ok=True)
    written, skipped, warnings = [], [], []
    for review_path in sorted((goldset / "review").glob("*.review.yaml")):
        review = yaml.safe_load(review_path.read_text(encoding="utf-8"))
        page_id = review["page_id"]
        if review.get("review_status") != "VERIFIED":
            skipped.append(page_id)
            continue
        draft = canonicalize_label(review["draft_label"])
        unresolved = [f for f in review.get("disagreements", {}) if draft.get(f) is None]
        if unresolved:
            warnings.append(f"{page_id}: null on former disagreements: {', '.join(sorted(unresolved))}")
        label_doc = {
            "page_id": page_id,
            "url": review["url"],
            "strata": review["strata"],
            "label": draft,
            "source": "assisted_review",
            "verified_at": datetime.now(UTC).isoformat(timespec="seconds"),
        }
        (labels_dir / f"{page_id}.json").write_text(
            json.dumps(label_doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        written.append(page_id)
    return {"written": written, "skipped_not_verified": skipped, "warnings": warnings}


def colddiff(goldset: Path) -> dict:
    per_page: dict[str, list[str]] = {}
    pending: list[str] = []
    fields_compared = 0
    changed_fields: list[str] = []
    for cold_path in sorted((goldset / "coldlabels").glob("*.cold.yaml")):
        cold = yaml.safe_load(cold_path.read_text(encoding="utf-8"))
        page_id = cold["page_id"]
        if cold.get("status") != "DONE":
            pending.append(page_id)
            continue
        label_path = goldset / "labels" / f"{page_id}.json"
        if not label_path.exists():
            pending.append(page_id)
            continue
        final = canonicalize_label(json.loads(label_path.read_text(encoding="utf-8"))["label"])
        cold_label = canonicalize_label(cold["label"])
        diffs = []
        for field, final_value in final.items():
            cold_value = cold_label.get(field)
            fields_compared += 1
            if not values_agree(cold_value, final_value):
                diffs.append(field)
                changed_fields.append(field)
        per_page[page_id] = diffs
    field_counts: dict[str, int] = {}
    for f in changed_fields:
        field_counts[f] = field_counts.get(f, 0) + 1
    return {
        "audit_pages": len(per_page),
        "pending": pending,
        "fields_compared": fields_compared,
        "fields_changed": len(changed_fields),
        "residual_error_rate": (len(changed_fields) / fields_compared) if fields_compared else None,
        "per_page": {k: v for k, v in per_page.items() if v},
        "per_field": dict(sorted(field_counts.items(), key=lambda kv: -kv[1])),
    }
