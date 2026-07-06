"""Prompt artifact registry: immutable artifacts, append-only ledger, lineage.

An artifact is one focused mutation away from its parent, committed before evaluation,
kept or discarded by the gate. The ledger records every evaluation of every artifact.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path


@dataclass(frozen=True)
class PromptArtifact:
    artifact_id: str
    parent_id: str | None
    text: str
    params: dict
    mutation_note: str
    source: str  # "human" | "optimizer"
    created_at: str


class PromptRegistry:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.artifacts_dir = root / "artifacts"
        self.ledger_path = root / "ledger.jsonl"

    @staticmethod
    def artifact_id_for(text: str, params: dict) -> str:
        payload = json.dumps({"text": text, "params": params}, sort_keys=True)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:10]

    def register(
        self,
        *,
        text: str,
        params: dict | None = None,
        parent_id: str | None = None,
        mutation_note: str,
        source: str,
    ) -> PromptArtifact:
        params = params or {}
        artifact_id = self.artifact_id_for(text, params)
        path = self.artifacts_dir / f"{artifact_id}.json"
        if path.exists():
            return self.get(artifact_id)
        if parent_id is not None and not (self.artifacts_dir / f"{parent_id}.json").exists():
            raise ValueError(f"parent artifact {parent_id} is not registered")
        artifact = PromptArtifact(
            artifact_id=artifact_id,
            parent_id=parent_id,
            text=text,
            params=params,
            mutation_note=mutation_note,
            source=source,
            created_at=datetime.now(UTC).isoformat(timespec="seconds"),
        )
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(artifact), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return artifact

    def get(self, artifact_id: str) -> PromptArtifact:
        path = self.artifacts_dir / f"{artifact_id}.json"
        return PromptArtifact(**json.loads(path.read_text(encoding="utf-8")))

    def lineage(self, artifact_id: str) -> list[PromptArtifact]:
        chain = []
        current: str | None = artifact_id
        while current is not None:
            artifact = self.get(current)
            chain.append(artifact)
            current = artifact.parent_id
        return list(reversed(chain))

    def append_ledger(self, row: dict) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        row = {"logged_at": datetime.now(UTC).isoformat(timespec="seconds"), **row}
        with self.ledger_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    def ledger_rows(self) -> list[dict]:
        if not self.ledger_path.exists():
            return []
        return [json.loads(line) for line in self.ledger_path.read_text(encoding="utf-8").splitlines()]
