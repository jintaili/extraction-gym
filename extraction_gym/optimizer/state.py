"""Checkpointed, resumable loop state. Every completed step is durable; a killed run
resumes from the last checkpoint with all finished evaluations coming from cache."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass
class LoopState:
    run_id: str
    incumbent_id: str
    generation: int = 0
    no_improve_streak: int = 0
    spend_usd: float = 0.0
    history: list[dict] = field(default_factory=list)

    def checkpoint_path(self, runs_dir: Path) -> Path:
        return runs_dir / self.run_id / "state.json"

    def save(self, runs_dir: Path) -> None:
        path = self.checkpoint_path(runs_dir)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(self), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    @classmethod
    def load(cls, runs_dir: Path, run_id: str) -> "LoopState":
        path = runs_dir / run_id / "state.json"
        return cls(**json.loads(path.read_text(encoding="utf-8")))
