"""MIPROv2 baseline under the same fairness contract as GEPA (see dspy_gepa.py).

Run demo-free (max_bootstrapped_demos=0, max_labeled_demos=0) so the optimized artifact
is instructions-only and directly comparable to GEPA and to the gym loop: same starting
prompt, same student/prompt models, trains on the pressure suite only, gym referee on
frozen gold, transplantable into the production runtime.

MIPROv2's metric is scalar (no feedback text), unlike GEPA's.
"""

from __future__ import annotations

from pathlib import Path

import dspy

from extraction_gym.baselines.dspy_gepa import (
    _score_and_feedback,
    build_program,
    evaluate_program_on_gold,
    suite_examples,
)


def mipro_metric(gold, pred, trace=None):
    score, _ = _score_and_feedback(gold.label, getattr(pred, "extraction", None))
    return score


def run_miprov2(
    *, root_prompt: str, suite_root: Path, goldset: Path, api_key: str,
    student_model: str = "gpt-4o-mini", prompt_model: str = "gpt-5.5", auto: str = "light",
) -> dict:
    student_lm = dspy.LM(f"openai/{student_model}", api_key=api_key, max_tokens=6000, temperature=1.0)
    prompt_lm = dspy.LM(f"openai/{prompt_model}", api_key=api_key, max_tokens=16000, temperature=1.0)
    dspy.configure(lm=student_lm, adapter=dspy.JSONAdapter())

    examples = suite_examples(suite_root)
    split = max(2, int(len(examples) * 0.7))
    trainset, valset = examples[:split], examples[split:] or examples[:2]

    program = build_program(root_prompt)
    optimizer = dspy.MIPROv2(
        metric=mipro_metric,
        prompt_model=prompt_lm,
        task_model=student_lm,
        max_bootstrapped_demos=0,
        max_labeled_demos=0,
        auto=auto,
        seed=20260709,
    )
    optimized = optimizer.compile(
        program, trainset=trainset, valset=valset, requires_permission_to_run=False
    )
    optimized_gold = evaluate_program_on_gold(optimized, goldset)

    instructions = optimized.signature.instructions if hasattr(optimized, "signature") else None
    return {
        "student_model": student_model,
        "prompt_model": prompt_model,
        "demo_free": True,
        "suite_examples": len(examples),
        "miprov2_optimized_on_gold": optimized_gold,
        "optimized_instructions": instructions,
    }
