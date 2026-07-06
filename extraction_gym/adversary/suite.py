"""Append-only storage for the adversarial pressure suite.

Accepted pages (hits and non-hits) are stored with category tags, generation metadata,
judge outputs, and the incumbent's failure diff. Synthetic pages NEVER enter the gold
set; they live here.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


class SuiteStore:
    def __init__(self, root: Path) -> None:
        self.root = root

    def store(
        self,
        *,
        page_text: str,
        label: dict,
        category: str,
        invented_category: bool,
        target_artifact_id: str,
        generator_model: str,
        judge_model: str,
        judges: dict,
        incumbent: dict,
    ) -> str:
        self.root.mkdir(parents=True, exist_ok=True)
        page_id = hashlib.sha256(page_text.encode("utf-8")).hexdigest()[:10]
        (self.root / f"{page_id}.txt").write_text(page_text, encoding="utf-8")
        meta = {
            "page_id": page_id,
            "category": category,
            "invented_category": invented_category,
            "target_artifact_id": target_artifact_id,
            "generator_model": generator_model,
            "judge_model": judge_model,
            "judges": judges,
            "label": label,
            "incumbent": incumbent,
        }
        (self.root / f"{page_id}.meta.json").write_text(
            json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        return page_id

    def pages(self) -> list[dict]:
        return [
            json.loads(p.read_text(encoding="utf-8")) for p in sorted(self.root.glob("*.meta.json"))
        ]
