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

from extraction_gym.adapters.coffee.scoring import CRITICAL_FIELDS, FIELD_SPECS
from extraction_gym.adversary.round import CONTINUOUS_FIELDS, CONTINUOUS_HIT_BELOW, HIT_WEIGHT_THRESHOLD
from extraction_gym.core.budget import BudgetExceeded
from extraction_gym.core.registry import PromptArtifact, PromptRegistry
from extraction_gym.eval.stats import binom_one_sided_p
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
    exemplars_fn: Callable[..., object]  # (incumbent, suite_report) -> list[dict] | str
    gold_band: dict  # {"composite_std": float, "field_stds": {...}}
    suite_band: float = 0.01
    gate: str = "v2"  # "v1" (composite band) or "v2" (repair test); see gate_candidate_v2


def gate_candidate(
    *, suite_inc: float, suite_cand: float, gold_inc: dict | None, gold_cand: dict | None,
    gold_band: dict, suite_band: float,
    candidate_len: int | None = None, root_len: int | None = None, max_len_ratio: float = 1.5,
) -> tuple[bool, list[str]]:
    reasons = []
    if candidate_len is not None and root_len:
        ratio = candidate_len / root_len
        if ratio > max_len_ratio:
            reasons.append(
                f"prompt length {candidate_len} chars is {ratio:.2f}x root ({root_len}); cap {max_len_ratio}x"
            )
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


def _field_wrong(field: str, score: float) -> bool:
    threshold = CONTINUOUS_HIT_BELOW if field in CONTINUOUS_FIELDS else 0.999
    return score < threshold


def suite_repairs(inc_scores: dict, cand_scores: dict) -> tuple[int, int]:
    """Count (repairs, breakages) over weighted fields across suite pages: a repair is a
    field the incumbent gets wrong and the candidate gets right; a breakage the reverse."""
    repairs = breakages = 0
    for page_id, inc_page in inc_scores.items():
        cand_page = cand_scores.get(page_id, {})
        for field, inc_score in inc_page.items():
            if inc_score is None or FIELD_SPECS[field][1] < HIT_WEIGHT_THRESHOLD:
                continue
            cand_score = cand_page.get(field)
            if cand_score is None:
                continue
            iw, cw = _field_wrong(field, inc_score), _field_wrong(field, cand_score)
            if iw and not cw:
                repairs += 1
            elif cw and not iw:
                breakages += 1
    return repairs, breakages


def gate_candidate_v2(
    *, suite_inc_scores: dict, suite_cand_scores: dict,
    gold_inc: dict | None, gold_cand: dict | None, gold_band: dict,
    candidate_len: int | None = None, root_len: int | None = None, max_len_ratio: float = 1.5,
    alpha: float = 0.05,
) -> tuple[bool, list[str], dict]:
    """Gate v2 (introduced 2026-07-10, motivated by the measured zero sensitivity of v1
    in the positive-control experiment; see reports/BENCHMARK.md):

    Suite side: instead of the composite band (which dilutes targeted fixes across all
    fields of all pages), acceptance requires the candidate to REPAIR significantly more
    incumbent-failure fields than it breaks (one-sided sign test, p < alpha).

    Gold side: composite non-regression unchanged (2x noise band). Critical-field
    regressions block only beyond ~1.5x the one-page quantum (1/n per field): at n=42 a
    single flipped page is indistinguishable from extraction stochasticity, so v1's
    single-page blocking was noise-triggered. Two or more net page-flips still block.
    Anti-Goodhart invariants untouched: gold is never a training signal, only a veto.
    """
    reasons: list[str] = []
    if candidate_len is not None and root_len:
        ratio = candidate_len / root_len
        if ratio > max_len_ratio:
            reasons.append(f"prompt length {ratio:.2f}x root; cap {max_len_ratio}x")
    repairs, breakages = suite_repairs(suite_inc_scores, suite_cand_scores)
    p = binom_one_sided_p(repairs, breakages)
    detail = {"repairs": repairs, "breakages": breakages, "p": round(p, 4)}
    if not (repairs > breakages and p < alpha):
        reasons.append(f"suite repair test not significant: {repairs} repairs vs "
                       f"{breakages} breakages (one-sided p={p:.3f}, need <{alpha})")
    if gold_inc is None or gold_cand is None:
        reasons.append("gold gate unavailable (gold set not frozen/labeled): promotion refused")
        return False, reasons, detail
    threshold = 2 * gold_band["composite_std"]
    if gold_cand["composite_mean"] < gold_inc["composite_mean"] - threshold:
        reasons.append(f"gold composite regression beyond 2x band {threshold:.4f}")
    coverage = gold_cand.get("field_coverage", {})
    for field in CRITICAL_FIELDS:
        inc_mean = gold_inc["field_means"].get(field)
        cand_mean = gold_cand["field_means"].get(field)
        if inc_mean is None or cand_mean is None:
            continue
        n = coverage.get(field) or 40
        quantum = 1.0 / n
        block_at = max(gold_band["field_stds"].get(field) or 0.0, 1.5 * quantum)
        if inc_mean - cand_mean > block_at:
            reasons.append(f"critical gold field regression: {field} {inc_mean:.3f} -> "
                           f"{cand_mean:.3f} (beyond {block_at:.3f} = max(band, 1.5/n))")
    return not reasons, reasons, detail


async def run_generation(state: LoopState, deps: LoopDeps, *, candidates_per_gen: int = 4) -> dict:
    incumbent = deps.registry.get(state.incumbent_id)
    adversary_report = await deps.adversary_round_fn(incumbent)
    suite_inc_report = await deps.suite_eval_fn(incumbent)
    suite_inc = suite_inc_report["composite_mean"]
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
            incumbent_text=incumbent.text,
            exemplars=deps.exemplars_fn(incumbent, suite_inc_report),
            history_summary=history_summary
        )
        candidate = deps.registry.register(
            text=proposal.new_prompt, parent_id=incumbent.artifact_id,
            mutation_note=proposal.mutation_note, source="optimizer",
        )
        suite_cand_report = await deps.suite_eval_fn(candidate)
        suite_cand = suite_cand_report["composite_mean"]
        gold_cand = await deps.gold_eval_fn(candidate) if deps.gold_eval_fn else None
        root_text = deps.registry.lineage(incumbent.artifact_id)[0].text
        if deps.gate == "v2":
            accepted, reasons, detail = gate_candidate_v2(
                suite_inc_scores=suite_inc_report["scores_by_page"],
                suite_cand_scores=suite_cand_report["scores_by_page"],
                gold_inc=gold_inc, gold_cand=gold_cand, gold_band=deps.gold_band,
                candidate_len=len(candidate.text), root_len=len(root_text),
            )
        else:
            accepted, reasons = gate_candidate(
                suite_inc=suite_inc, suite_cand=suite_cand, gold_inc=gold_inc, gold_cand=gold_cand,
                gold_band=deps.gold_band, suite_band=deps.suite_band,
                candidate_len=len(candidate.text), root_len=len(root_text),
            )
            detail = {}
        entry = {
            "artifact_id": candidate.artifact_id, "mutation_note": proposal.mutation_note,
            "suite": suite_cand, "gold": gold_cand["composite_mean"] if gold_cand else None,
            "accepted": accepted, "gate_reasons": reasons, "gate": deps.gate, **detail,
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
