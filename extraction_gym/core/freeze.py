"""Freeze a gold set version: immutable manifest with checksums, strata, residual error.

Gold versions are immutable. Freezing requires every page to have a verified label and
the cold audit to be complete. Silent mutation after freeze is impossible by construction:
gym verify recomputes checksums against the manifest.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from extraction_gym.core.labelize import colddiff


class FreezeError(Exception):
    pass


def freeze(goldset: Path, *, version: str) -> dict:
    manifest_path = goldset / "MANIFEST.json"
    if manifest_path.exists():
        raise FreezeError("MANIFEST.json already exists; gold versions are immutable.")

    pages = []
    missing_labels = []
    for meta_path in sorted((goldset / "pages").glob("*.meta.json")):
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        page_id = meta_path.name.removesuffix(".meta.json")
        if not (goldset / "labels" / f"{page_id}.json").exists():
            missing_labels.append(page_id)
        pages.append(
            {
                "page_id": page_id,
                "url": meta["url"],
                "strata": meta["strata"],
                "sha256": meta["sha256"],
                "chars": meta["chars"],
            }
        )
    if missing_labels:
        raise FreezeError(f"{len(missing_labels)} pages lack verified labels: {' '.join(missing_labels)}")

    audit = colddiff(goldset)
    if audit["pending"]:
        raise FreezeError(f"cold audit incomplete for: {' '.join(audit['pending'])}")

    strata_counts: dict[str, int] = {}
    for page in pages:
        for stratum in page["strata"]:
            strata_counts[stratum] = strata_counts.get(stratum, 0) + 1

    manifest = {
        "version": version,
        "frozen_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "page_count": len(pages),
        "strata_counts": dict(sorted(strata_counts.items())),
        "residual_label_error": {
            "audit_pages": audit["audit_pages"],
            "fields_compared": audit["fields_compared"],
            "fields_changed": audit["fields_changed"],
            "rate": audit["residual_error_rate"],
            "per_field": audit["per_field"],
        },
        "pages": pages,
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest
