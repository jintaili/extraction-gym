"""The main generation loop: adversary round, optimizer round, gates, checkpoint.

Dependency-injected so every rule is testable without API calls. Control rules:
a candidate becomes incumbent only if it improves on the pressure suite beyond the
suite band AND does not regress on frozen gold (composite within 2x gold noise band,
no critical-field regression). Without a gold evaluator the loop refuses to promote.
Stopping: N consecutive generations with no accepted candidate, generation cap, or
BudgetExceeded. Resume continues from the checkpoint; finished evals come from cache.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Awaitable, Callable

from extraction_gym.adapters.coffee.scoring import CRITICAL_FIELDS
from extraction_gym.core.budget import BudgetExceeded
from extraction_gym.core.registry import PromptArtifact, PromptRegistry
from extraction_gym.optimizer.mutate import ProposedMutation
from extraction_gym.optimizer.state import LoopState


@dataclass
class LoopDeps:
    registry: PromptRegistry
    runs_dir: Path
    adversary_round_fn: Callable[[PromptArtifact], Awaitable[dict]]
    suite_eval_fn: Callable[[PromptArtifact], Awaitable[dict]]  # {"composite_mean": float}
    gold_eval_fn: Callable[[PromptArtifact], Awaitable[dict]] | None  # full report or None
    propose_fn: Callable[..., Awaitable[ProposedMutation]]
    exemplars_fn: Callable[[], list[dict]]
    gold_band: dict  # {"composite_std": float, "field_stds": {...}}
    suite_band: float = 0.01


def gate_candidate(
    *, suite_inc: float, suite_cand: float, gold_inc: dict | None, gold_cand: dict | None,
    gold_band: dict, suite_band: float,
) -> tuple[bool, list[str]]:
    reasons = []
    if suite_cand <= suite_inc + suite_band:
        reasons.append(
            f"pressure-suite improvement {suite_cand - suite_inc:+.4f} does not exceed band {suite_band}"
        )
    if gold_inc is None or gold_cand is None:
        reasons.append("gold gate unavailable (gold set not frozen/labeled): promotion refused")
        return False, reasons
    threshold = 2 * gold_band["composite_std"]
    if gold_cand["composite_mean"] < gold_inc["composite_mean"] - threshold:
        reasons.append(
            f"gold composite regression {gold_cand['composite_mean'] - gold_inc['composite_mean']:+.4f} "
            f"beyond 2x band {threshold:.4f}"
        )
    for field in CRITICAL_FIELDS:
        inc_mean = gold_inc["field_means"].get(field)
        cand_mean = gold_cand["field_means"].get(field)
        if inc_mean is None or cand_mean is None:
            continue
        band = gold_band["field_stds"].get(field) or 0.0
        if cand_mean < inc_mean - max(band, 1e-9):
            reasons.append(f"critical gold field regression: {field} {inc_mean:.3f} -> {cand_mean:.3f}")
    return not reasons, reasons


async def run_generation(state: LoopState, deps: LoopDeps, *, candidates_per_gen: int = 4) -> dict:
    incumbent = deps.registry.get(state.incumbent_id)
    adversary_report = await deps.adversary_round_fn(incumbent)
    suite_inc = (await deps.suite_eval_fn(incumbent))["composite_mean"]
    gold_inc = await deps.gold_eval_fn(incumbent) if deps.gold_eval_fn else None

    record: dict = {
        "generation": state.generation,
        "incumbent_id": incumbent.artifact_id,
        "suite_incumbent": suite_inc,
        "gold_incumbent": gold_inc["composite_mean"] if gold_inc else None,
        "adversary": adversary_report.get("stats"),
        "candidates": [],
        "accepted": None,
    }

    history_summary = "; ".join(
        f"gen {h['generation']}: {'accepted ' + h['accepted'] if h['accepted'] else 'no accept'}"
        for h in state.history[-5:]
    )
    for _ in range(candidates_per_gen):
        proposal = await deps.propose_fn(
            incumbent_text=incumbent.text, exemplars=deps.exemplars_fn(), history_summary=history_summary
        )
        candidate = deps.registry.register(
            text=proposal.new_prompt, parent_id=incumbent.artifact_id,
            mutation_note=proposal.mutation_note, source="optimizer",
        )
        suite_cand = (await deps.suite_eval_fn(candidate))["composite_mean"]
        gold_cand = await deps.gold_eval_fn(candidate) if deps.gold_eval_fn else None
        accepted, reasons = gate_candidate(
            suite_inc=suite_inc, suite_cand=suite_cand, gold_inc=gold_inc, gold_cand=gold_cand,
            gold_band=deps.gold_band, suite_band=deps.suite_band,
        )
        entry = {
            "artifact_id": candidate.artifact_id, "mutation_note": proposal.mutation_note,
            "suite": suite_cand, "gold": gold_cand["composite_mean"] if gold_cand else None,
            "accepted": accepted, "gate_reasons": reasons,
        }
        record["candidates"].append(entry)
        deps.registry.append_ledger({"event": "candidate", "generation": state.generation, **entry})
        if accepted:
            record["accepted"] = candidate.artifact_id
            state.incumbent_id = candidate.artifact_id
            break

    state.history.append(record)
    state.no_improve_streak = 0 if record["accepted"] else state.no_improve_streak + 1
    state.generation += 1
    state.save(deps.runs_dir)
    return record


async def run_loop(
    state: LoopState, deps: LoopDeps, *, max_generations: int = 12,
    stop_after_no_improve: int = 3, candidates_per_gen: int = 4,
) -> LoopState:
    while state.generation < max_generations and state.no_improve_streak < stop_after_no_improve:
        try:
            await run_generation(state, deps, candidates_per_gen=candidates_per_gen)
        except BudgetExceeded as exc:
            state.history.append({"generation": state.generation, "stopped": f"budget: {exc}"})
            state.save(deps.runs_dir)
            break
    state.save(deps.runs_dir)
    return state
