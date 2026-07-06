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
