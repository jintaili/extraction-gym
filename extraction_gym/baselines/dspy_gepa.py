"""DSPy/GEPA baseline: the state-of-the-art prompt optimizer run under this harness's rules.

Fairness contract (mirrors the gym optimizer exactly):
- same starting point: the root artifact's prompt text as initial instructions
- same model under test (gpt-4o-mini) and same frontier reflection model (gpt-5.5)
- same information access: trains on the adversarial pressure suite ONLY; gold never
  enters GEPA's context
- same referee: the optimized program is scored by the gym's deterministic scorers on
  frozen gold v1

Runtime caveat, stated in the report: DSPy formats its own messages (instructions +
field markers), so the GEPA candidate is a dspy program rather than a drop-in production
system prompt. Scores are comparable; deployability differs.
"""

from __future__ import annotations

import json
from pathlib import Path

import dspy

from coffee_value_app.schemas import PageExtraction
from extraction_gym.adapters.coffee.scoring import FIELD_SPECS, composite, score_page
from extraction_gym.core.prelabel import canonicalize_label, label_fields


class CoffeeExtraction(dspy.Signature):
    """placeholder; replaced with the root artifact prompt via with_instructions"""

    page_text: str = dspy.InputField(desc="normalized product page text")
    extraction: PageExtraction = dspy.OutputField()


def build_program(root_prompt: str) -> dspy.Module:
    sig = CoffeeExtraction.with_instructions(root_prompt)
    return dspy.Predict(sig)


def _score_and_feedback(gold_label: dict, extraction: PageExtraction | None) -> tuple[float, str]:
    if extraction is None:
        return 0.0, "Output did not parse into the PageExtraction schema."
    got = canonicalize_label(label_fields(extraction.model_dump(mode="json")))
    scores = score_page(canonicalize_label(gold_label), got)
    comp = composite(scores)
    worst = sorted(
        ((f, s) for f, s in scores.items() if s is not None and FIELD_SPECS[f][1] >= 2.0 and s < 0.999),
        key=lambda kv: kv[1],
    )[:4]
    if not worst:
        return comp, "All weighted fields correct."
    parts = []
    for field, s in worst:
        parts.append(
            f"{field} (score {s:.2f}): expected {json.dumps(gold_label.get(field), ensure_ascii=False)}, "
            f"got {json.dumps(got.get(field), ensure_ascii=False)}"
        )
    return comp, "Weighted-field errors: " + " | ".join(parts)


def gepa_metric(gold, pred, trace=None, pred_name=None, pred_trace=None):
    extraction = getattr(pred, "extraction", None)
    score, feedback = _score_and_feedback(gold.label, extraction)
    return dspy.Prediction(score=score, feedback=feedback)


def suite_examples(suite_root: Path) -> list[dspy.Example]:
    examples = []
    for meta_path in sorted(suite_root.glob("*.meta.json")):
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        page_text = (suite_root / f"{meta['page_id']}.txt").read_text(encoding="utf-8")
        examples.append(dspy.Example(page_text=page_text, label=meta["label"]).with_inputs("page_text"))
    return examples


def gold_examples(goldset: Path) -> list[dspy.Example]:
    examples = []
    for label_path in sorted((goldset / "labels").glob("*.json")):
        doc = json.loads(label_path.read_text(encoding="utf-8"))
        page_text = (goldset / "pages" / f"{doc['page_id']}.txt").read_text(encoding="utf-8")
        examples.append(
            dspy.Example(page_text=page_text, label=doc["label"], page_id=doc["page_id"]).with_inputs("page_text")
        )
    return examples


def evaluate_program_on_gold(program: dspy.Module, goldset: Path) -> dict:
    composites = {}
    parse_failures = 0
    for example in gold_examples(goldset):
        try:
            pred = program(page_text=example.page_text)
            extraction = getattr(pred, "extraction", None)
        except Exception:
            extraction = None
        if extraction is None:
            parse_failures += 1
            composites[example.page_id] = 0.0
            continue
        got = canonicalize_label(label_fields(extraction.model_dump(mode="json")))
        composites[example.page_id] = composite(
            score_page(canonicalize_label(example.label), got)
        )
    return {
        "pages": len(composites),
        "composite_mean": sum(composites.values()) / len(composites),
        "composite_by_page": composites,
        "parse_failures": parse_failures,
    }


def run_gepa(
    *, root_prompt: str, suite_root: Path, goldset: Path, api_key: str,
    student_model: str = "gpt-4o-mini", reflection_model: str = "gpt-5.5", auto: str = "light",
) -> dict:
    student_lm = dspy.LM(f"openai/{student_model}", api_key=api_key, max_tokens=6000, temperature=1.0)
    reflection_lm = dspy.LM(f"openai/{reflection_model}", api_key=api_key, max_tokens=16000, temperature=1.0)
    dspy.configure(lm=student_lm, adapter=dspy.JSONAdapter())

    examples = suite_examples(suite_root)
    split = max(2, int(len(examples) * 0.7))
    trainset, valset = examples[:split], examples[split:] or examples[:2]

    program = build_program(root_prompt)
    baseline_gold = evaluate_program_on_gold(program, goldset)

    gepa = dspy.GEPA(metric=gepa_metric, auto=auto, reflection_lm=reflection_lm)
    optimized = gepa.compile(program, trainset=trainset, valset=valset)
    optimized_gold = evaluate_program_on_gold(optimized, goldset)

    instructions = optimized.signature.instructions if hasattr(optimized, "signature") else None
    return {
        "student_model": student_model,
        "reflection_model": reflection_model,
        "suite_examples": len(examples),
        "dspy_runtime_root_on_gold": baseline_gold,
        "gepa_optimized_on_gold": optimized_gold,
        "optimized_instructions": instructions,
    }
