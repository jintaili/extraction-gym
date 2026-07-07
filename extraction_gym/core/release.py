"""Release attestation: a small committed artifact that lets coffee-value-app CI assert,
with no API calls, that its shipped prompt is a registered artifact with a PASS verdict
(or the registered root under a documented NOOP) against a specific frozen gold version.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path


def write_attestation(
    *,
    out_path: Path,
    artifact_id: str,
    prompt_text: str,
    gold_version: str,
    gold_manifest: dict,
    verdict: str,  # "PASS" | "NOOP_ROOT"
    evidence: dict,
) -> dict:
    attestation = {
        "artifact_id": artifact_id,
        "prompt_sha256": hashlib.sha256(prompt_text.encode("utf-8")).hexdigest(),
        "gold_version": gold_version,
        "gold_manifest_frozen_at": gold_manifest["frozen_at"],
        "gold_page_count": gold_manifest["page_count"],
        "verdict": verdict,
        "evidence": evidence,
        "attested_at": datetime.now(UTC).isoformat(timespec="seconds"),
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(attestation, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return attestation


def check_attestation(attestation: dict, shipped_prompt_text: str) -> list[str]:
    """The assertion CI runs: shipped prompt bytes match the attested artifact."""
    problems = []
    shipped_sha = hashlib.sha256(shipped_prompt_text.encode("utf-8")).hexdigest()
    if shipped_sha != attestation["prompt_sha256"]:
        problems.append(
            f"shipped prompt sha {shipped_sha[:12]} != attested {attestation['prompt_sha256'][:12]}"
        )
    if attestation["verdict"] not in {"PASS", "NOOP_ROOT"}:
        problems.append(f"attestation verdict {attestation['verdict']!r} is not releasable")
    return problems
