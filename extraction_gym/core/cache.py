"""Extraction cache keyed by hash(page_text, prompt_id, model, params).

Re-running an eval or prelabel over unchanged inputs must cost zero API calls.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


class ExtractionCache:
    def __init__(self, root: Path) -> None:
        self.root = root

    @staticmethod
    def key(*, page_text: str, prompt_id: str, model: str, params: dict) -> str:
        payload = json.dumps(
            {
                "page_sha": hashlib.sha256(page_text.encode("utf-8")).hexdigest(),
                "prompt_id": prompt_id,
                "model": model,
                "params": params,
            },
            sort_keys=True,
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]

    def get(self, key: str) -> dict | None:
        path = self.root / f"{key}.json"
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def put(self, key: str, value: dict) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / f"{key}.json").write_text(
            json.dumps(value, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
        )
