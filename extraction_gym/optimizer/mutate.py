"""Propose one focused prompt mutation from pressure-suite failure exemplars.

Control rule: the optimizer NEVER sees gold pages or gold labels. Its context is the
incumbent prompt, a ledger-history summary, and failure exemplars from the adversarial
suite (synthetic page text + expected-vs-got diffs).
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from openai import AsyncOpenAI
from pydantic import BaseModel, ConfigDict

from extraction_gym.core.prelabel import label_fields


class MutationProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rationale: str
    mutation_note: str  # one sentence, one focused change
    new_prompt: str


@dataclass(frozen=True)
class ProposedMutation:
    rationale: str
    mutation_note: str
    new_prompt: str
    input_tokens: int
    output_tokens: int


MUTATE_SYSTEM_PROMPT = """You improve a production system prompt for an LLM that extracts structured \
coffee-product data from web pages. You will see the current prompt and concrete failure exemplars: \
synthetic test pages where the extractor's output diverged from ground truth on specific fields.

Propose exactly ONE focused mutation to the prompt: a single coherent change (add, tighten, or fix one \
instruction or one example block) that plausibly fixes the observed failure pattern without disturbing \
unrelated behavior. Do not rewrite the whole prompt. Do not change the schema, field names, or output \
format. Return the complete edited prompt text with your one change applied, a one-sentence \
mutation_note describing the change, and a short rationale tied to the exemplars."""


def failure_exemplars_from_suite(suite_pages: list[dict], *, limit: int = 3, max_page_chars: int = 4000) -> list[dict]:
    exemplars = []
    for meta in reversed(suite_pages):  # most recent first
        hit_fields = meta.get("incumbent", {}).get("hit_fields") or []
        if not hit_fields:
            continue
        got = label_fields(meta["incumbent"]["extraction"])
        page_path_text = meta.get("page_text")  # optional pre-loaded
        exemplars.append(
            {
                "category": meta["category"],
                "page_text": (page_path_text or "")[:max_page_chars],
                "page_id": meta["page_id"],
                "diffs": {
                    f: {"expected": meta["label"].get(f), "got": got.get(f)} for f in hit_fields
                },
            }
        )
        if len(exemplars) >= limit:
            break
    return exemplars


def build_mutate_user_prompt(incumbent_text: str, exemplars: list[dict], history_summary: str) -> str:
    return (
        f"CURRENT PROMPT:\n---\n{incumbent_text}\n---\n\n"
        f"LEDGER HISTORY SUMMARY:\n{history_summary or '(first mutation)'}\n\n"
        f"FAILURE EXEMPLARS (expected vs got on weighted fields):\n"
        f"{json.dumps(exemplars, ensure_ascii=False, indent=1)}"
    )


def build_failure_inventory(
    suite_root, incumbent_id: str, scores_by_page: dict, model: str, cache,
) -> str:
    """Structured failure inventory: every weighted field the incumbent gets wrong on
    the suite, grouped by field with expected-vs-got values, followed by the FULL
    verbatim text of every failing page. Passing pages are omitted entirely."""
    import json
    from pathlib import Path

    from extraction_gym.adapters.coffee.scoring import FIELD_SPECS
    from extraction_gym.adversary.round import CONTINUOUS_FIELDS, CONTINUOUS_HIT_BELOW, HIT_WEIGHT_THRESHOLD
    from extraction_gym.core.cache import ExtractionCache
    from extraction_gym.core.prelabel import canonicalize_label

    suite_root = Path(suite_root)
    by_field: dict[str, list[dict]] = {}
    failing_pages: dict[str, str] = {}
    for page_id, scores in scores_by_page.items():
        meta = json.loads((suite_root / f"{page_id}.meta.json").read_text(encoding="utf-8"))
        text = (suite_root / f"{page_id}.txt").read_text(encoding="utf-8")
        got = None
        key = ExtractionCache.key(page_text=text, prompt_id=incumbent_id, model=model,
                                  params={"decoding": "default"})
        cached = cache.get(key)
        if cached:
            got = canonicalize_label(label_fields(cached["extraction"]))
        gold = canonicalize_label(meta["label"])
        for field, score in scores.items():
            if score is None or FIELD_SPECS[field][1] < HIT_WEIGHT_THRESHOLD:
                continue
            threshold = CONTINUOUS_HIT_BELOW if field in CONTINUOUS_FIELDS else 0.999
            if score < threshold:
                by_field.setdefault(field, []).append({
                    "page": page_id, "expected": gold.get(field),
                    "got": got.get(field) if got else "(unavailable)",
                })
                failing_pages[page_id] = text

    lines = [f"FAILURE INVENTORY: incumbent fails {sum(len(v) for v in by_field.values())} "
             f"weighted fields across {len(failing_pages)} of {len(scores_by_page)} suite pages.\n"]
    for field, fails in sorted(by_field.items(), key=lambda kv: -len(kv[1])):
        lines.append(f"## {field} - wrong on {len(fails)} pages:")
        for f in fails:
            lines.append(f"  {f['page']}: expected {json.dumps(f['expected'], ensure_ascii=False)}"
                         f" | got {json.dumps(f['got'], ensure_ascii=False)}")
    lines.append("\nFULL TEXT OF EVERY FAILING PAGE (passing pages omitted):")
    for page_id, text in sorted(failing_pages.items()):
        lines.append(f"\n===== PAGE {page_id} =====\n{text}")
    return "\n".join(lines)


ANTHROPIC_MUTATE_SYSTEM = """You improve a production system prompt for an LLM extractor. You will see the \
current prompt, a structured inventory of every field it currently gets wrong on a test suite, and the full \
text of every failing page.

Propose exactly ONE narrow, surgical edit to the prompt that targets the largest failure cluster(s) you can \
fix WITHOUT touching guidance for behaviors that currently work. Hard constraints: do not rewrite or reorder \
unrelated sections; do not change the schema, field names, or output format; keep total prompt length no \
longer than the original. Return the complete edited prompt, a one-sentence mutation_note, and a short \
rationale naming which inventory clusters the edit targets."""


class AnthropicMutationProposer:
    """Fable 5 proposer: structured outputs via output_config.format; effort=high
    (bounded single-shot editing task - higher effort risks over-engineered edits);
    thinking is always on for this model and must not be configured."""

    def __init__(self, *, model: str = "claude-fable-5", effort: str = "high") -> None:
        from anthropic import AsyncAnthropic

        self.client = AsyncAnthropic()
        self.model = model
        self.effort = effort

    async def propose(
        self, *, incumbent_text: str, exemplars, history_summary: str = ""
    ) -> ProposedMutation:
        import json as _json

        inventory = exemplars if isinstance(exemplars, str) else _json.dumps(exemplars, ensure_ascii=False)
        schema = MutationProposal.model_json_schema()
        response = await self.client.messages.create(
            model=self.model,
            max_tokens=16000,
            output_config={"effort": self.effort,
                           "format": {"type": "json_schema", "schema": schema}},
            system=ANTHROPIC_MUTATE_SYSTEM,
            messages=[{"role": "user", "content":
                       f"CURRENT PROMPT:\n---\n{incumbent_text}\n---\n\n"
                       f"LEDGER HISTORY:\n{history_summary or '(first mutation)'}\n\n{inventory}"}],
        )
        if response.stop_reason == "refusal":
            raise RuntimeError("proposer request was refused")
        text = next(b.text for b in response.content if b.type == "text")
        parsed = MutationProposal.model_validate_json(text)
        return ProposedMutation(
            rationale=parsed.rationale, mutation_note=parsed.mutation_note,
            new_prompt=parsed.new_prompt,
            input_tokens=response.usage.input_tokens, output_tokens=response.usage.output_tokens,
        )


class MutationProposer:
    def __init__(self, *, client: AsyncOpenAI, model: str) -> None:
        self.client = client
        self.model = model

    async def propose(
        self, *, incumbent_text: str, exemplars: list[dict], history_summary: str = ""
    ) -> ProposedMutation:
        response = await self.client.responses.parse(
            model=self.model,
            input=[
                {"role": "system", "content": MUTATE_SYSTEM_PROMPT},
                {"role": "user", "content": build_mutate_user_prompt(incumbent_text, exemplars, history_summary)},
            ],
            text_format=MutationProposal,
        )
        parsed = None
        for output in getattr(response, "output", []):
            for item in getattr(output, "content", []) or []:
                candidate = getattr(item, "parsed", None)
                if candidate is not None:
                    parsed = candidate if isinstance(candidate, MutationProposal) else MutationProposal.model_validate(candidate)
        if parsed is None:
            raise RuntimeError("proposer returned no parsed MutationProposal")
        usage = getattr(response, "usage", None)
        return ProposedMutation(
            rationale=parsed.rationale,
            mutation_note=parsed.mutation_note,
            new_prompt=parsed.new_prompt,
            input_tokens=getattr(usage, "input_tokens", 0) or 0,
            output_tokens=getattr(usage, "output_tokens", 0) or 0,
        )
