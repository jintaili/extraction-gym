import asyncio

from extraction_gym.core.registry import PromptRegistry
from extraction_gym.optimizer.loop import LoopDeps, gate_candidate, run_loop
from extraction_gym.optimizer.mutate import ProposedMutation
from extraction_gym.optimizer.state import LoopState

BAND = {"composite_std": 0.005, "field_stds": {f: 0.01 for f in ["page_type", "coffee.origin_country",
        "coffee.process_method", "coffee.variety", "price.listed_price", "price.package_grams"]}}


def _gold(composite, price=0.9):
    means = {f: 0.9 for f in BAND["field_stds"]}
    means["price.listed_price"] = price
    return {"composite_mean": composite, "field_means": means}


def test_gate_requires_gold():
    ok, reasons = gate_candidate(suite_inc=0.5, suite_cand=0.9, gold_inc=None, gold_cand=None,
                                 gold_band=BAND, suite_band=0.01)
    assert not ok and any("gold gate unavailable" in r for r in reasons)


def test_gate_blocks_prompt_bloat():
    ok, reasons = gate_candidate(suite_inc=0.5, suite_cand=0.9, gold_inc=_gold(0.85),
                                 gold_cand=_gold(0.85), gold_band=BAND, suite_band=0.01,
                                 candidate_len=1600, root_len=1000)
    assert not ok and "prompt length" in reasons[0]
    ok, _ = gate_candidate(suite_inc=0.5, suite_cand=0.9, gold_inc=_gold(0.85),
                           gold_cand=_gold(0.85), gold_band=BAND, suite_band=0.01,
                           candidate_len=1400, root_len=1000)
    assert ok


def test_gate_paths():
    ok, _ = gate_candidate(suite_inc=0.5, suite_cand=0.9, gold_inc=_gold(0.85), gold_cand=_gold(0.85),
                           gold_band=BAND, suite_band=0.01)
    assert ok
    ok, reasons = gate_candidate(suite_inc=0.5, suite_cand=0.505, gold_inc=_gold(0.85),
                                 gold_cand=_gold(0.85), gold_band=BAND, suite_band=0.01)
    assert not ok and "does not exceed band" in reasons[0]
    ok, reasons = gate_candidate(suite_inc=0.5, suite_cand=0.9, gold_inc=_gold(0.85, price=0.9),
                                 gold_cand=_gold(0.85, price=0.7), gold_band=BAND, suite_band=0.01)
    assert not ok and "critical gold field regression" in reasons[0]


def _deps(tmp_path, registry, suite_scores, gold_scores, proposals):
    counter = {"i": 0}

    async def adversary(_incumbent):
        return {"stats": {"accepted": 0}}

    async def suite_eval(artifact):
        return {"composite_mean": suite_scores[artifact.text]}

    async def gold_eval(artifact):
        return gold_scores[artifact.text]

    async def propose(*, incumbent_text, exemplars, history_summary):
        proposal = proposals[counter["i"] % len(proposals)]
        counter["i"] += 1
        return ProposedMutation(rationale="r", mutation_note=f"note {counter['i']}",
                                new_prompt=proposal, input_tokens=0, output_tokens=0)

    return LoopDeps(registry=registry, runs_dir=tmp_path / "runs", adversary_round_fn=adversary,
                    suite_eval_fn=suite_eval, gold_eval_fn=gold_eval, propose_fn=propose,
                    exemplars_fn=lambda: [], gold_band=BAND, suite_band=0.01)


def test_loop_accepts_promotes_and_checkpoints(tmp_path):
    registry = PromptRegistry(tmp_path / "registry")
    root = registry.register(text="v0", mutation_note="root", source="human")
    suite_scores = {"v0": 0.50, "v1": 0.70}
    gold_scores = {"v0": _gold(0.85), "v1": _gold(0.86)}
    deps = _deps(tmp_path, registry, suite_scores, gold_scores, ["v1"])
    state = LoopState(run_id="t1", incumbent_id=root.artifact_id)

    state = asyncio.run(run_loop(state, deps, max_generations=1))
    assert state.history[0]["accepted"] is not None
    assert state.incumbent_id != root.artifact_id
    reloaded = LoopState.load(tmp_path / "runs", "t1")
    assert reloaded.incumbent_id == state.incumbent_id
    assert registry.get(state.incumbent_id).parent_id == root.artifact_id


def test_loop_stops_after_no_improve_and_resumes(tmp_path):
    registry = PromptRegistry(tmp_path / "registry")
    root = registry.register(text="v0", mutation_note="root", source="human")
    suite_scores = {"v0": 0.50, "bad": 0.50}
    gold_scores = {"v0": _gold(0.85), "bad": _gold(0.85)}
    deps = _deps(tmp_path, registry, suite_scores, gold_scores, ["bad"])
    state = LoopState(run_id="t2", incumbent_id=root.artifact_id)

    state = asyncio.run(run_loop(state, deps, max_generations=12, stop_after_no_improve=3,
                                 candidates_per_gen=1))
    assert state.no_improve_streak == 3
    assert state.generation == 3, "stopped by streak, not by cap"

    resumed = LoopState.load(tmp_path / "runs", "t2")
    assert resumed.generation == 3
    resumed = asyncio.run(run_loop(resumed, deps, max_generations=12, stop_after_no_improve=3))
    assert resumed.generation == 3, "already-stopped state does not advance"
