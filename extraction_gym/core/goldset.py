"""Gold set page storage: frozen snapshots with strata tags and checksums.

Layout per gold version directory (e.g. goldset/v1/):
  pages/<id>.txt        normalized page text, immutable once written
  pages/<id>.meta.json  url, final_url, fetched_at, strata, sha256, chars
  labels/<id>.json      human-verified labels (written in the labeling phase)
  MANIFEST.json         written by `gym freeze`; checksums make silent mutation impossible
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path


def page_id_for_url(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()[:10]


def text_sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class StoredPage:
    page_id: str
    created: bool
    strata: list[str]
    chars: int


class GoldsetStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.pages_dir = root / "pages"
        self.labels_dir = root / "labels"

    def store_snapshot(
        self,
        *,
        url: str,
        final_url: str,
        fetched_at: str,
        text: str,
        strata: list[str],
        force: bool = False,
    ) -> StoredPage:
        if not text.strip():
            raise ValueError("Refusing to store an empty snapshot.")
        self.pages_dir.mkdir(parents=True, exist_ok=True)
        page_id = page_id_for_url(url)
        text_path = self.pages_dir / f"{page_id}.txt"
        meta_path = self.pages_dir / f"{page_id}.meta.json"

        if text_path.exists() and not force:
            # Existing snapshot is immutable; merge strata tags only (multi-stratum pages).
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            merged = sorted(set(meta["strata"]) | set(strata))
            if merged != meta["strata"]:
                meta["strata"] = merged
                meta_path.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
            return StoredPage(page_id=page_id, created=False, strata=merged, chars=meta["chars"])

        meta = {
            "url": url,
            "final_url": final_url,
            "fetched_at": fetched_at,
            "strata": sorted(set(strata)),
            "sha256": text_sha256(text),
            "chars": len(text),
        }
        text_path.write_text(text, encoding="utf-8")
        meta_path.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
        return StoredPage(page_id=page_id, created=True, strata=meta["strata"], chars=meta["chars"])

    def verify_checksums(self) -> list[str]:
        """Return page ids whose text no longer matches its recorded sha256."""
        corrupted = []
        for meta_path in sorted(self.pages_dir.glob("*.meta.json")):
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            page_id = meta_path.name.removesuffix(".meta.json")
            text = (self.pages_dir / f"{page_id}.txt").read_text(encoding="utf-8")
            if text_sha256(text) != meta["sha256"]:
                corrupted.append(page_id)
        return corrupted

    def verify_manifest(self) -> list[str]:
        """After freeze: page set and checksums must match MANIFEST.json exactly."""
        manifest_path = self.root / "MANIFEST.json"
        if not manifest_path.exists():
            return []
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        problems = []
        manifest_ids = set()
        for page in manifest["pages"]:
            page_id = page["page_id"]
            manifest_ids.add(page_id)
            text_path = self.pages_dir / f"{page_id}.txt"
            if not text_path.exists():
                problems.append(f"missing page {page_id}")
            elif text_sha256(text_path.read_text(encoding="utf-8")) != page["sha256"]:
                problems.append(f"checksum mismatch {page_id}")
        on_disk = {p.name.removesuffix(".txt") for p in self.pages_dir.glob("*.txt")}
        for extra in sorted(on_disk - manifest_ids):
            problems.append(f"page not in manifest: {extra}")
        return problems
