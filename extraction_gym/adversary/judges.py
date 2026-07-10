"""Consistency and realism judges for generated pages.

The judge model must differ from the generator model (correlated blind spots); a
different provider family is preferred when available (see DESIGN.md limitations).
Consistency is mandatory: a generator can easily write a page and labels that disagree,
which would poison the suite.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from openai import AsyncOpenAI
from pydantic import BaseModel, ConfigDict


class ConsistencyVerdict(BaseModel):
    model_config = ConfigDict(extra="forbid")

    unsupported_fields: list[str]
    notes: str


class RealismVerdict(BaseModel):
    model_config = ConfigDict(extra="forbid")

    score: int
    reasons: str


CONSISTENCY_PROMPT = """You verify that every ground-truth label value is entailed by the page text. \
For each non-null, non-"unknown", non-empty label value, check the page text supports it exactly \
(verbatim fields must appear on the page; numbers must match page evidence; enums must follow from \
page statements). List the label field names that are NOT supported. An empty list means all supported. \
Do not penalize null/unknown/empty labels."""

REALISM_PROMPT = """Score 1-5 how plausibly this text could be the html-to-text rendering of a real \
specialty coffee roaster product page. 5 = indistinguishable from real; 4 = minor tells; \
3 = noticeably synthetic; 2 = clearly fake; 1 = nonsense. Judge voice, structure, coherence of \
origin/variety/process/price details, and the variant data block."""


@dataclass(frozen=True)
class JudgeResult:
    passed: bool
    detail: dict
    input_tokens: int
    output_tokens: int


class Judges:
    """provider="openai" uses the given AsyncOpenAI client; provider="anthropic" builds an
    AsyncAnthropic client from the environment (cross-family judging: removes the
    correlated-blind-spot caveat when the generator is an OpenAI model)."""

    def __init__(
        self, *, client: AsyncOpenAI | None = None, model: str, realism_threshold: int = 4,
        provider: str = "openai",
    ) -> None:
        self.provider = provider
        self.model = model
        self.realism_threshold = realism_threshold
        if provider == "anthropic":
            from anthropic import AsyncAnthropic

            self.client = AsyncAnthropic()
        else:
            self.client = client

    async def _parse(self, system: str, user: str, fmt):
        if self.provider == "anthropic":
            response = await self.client.messages.parse(
                model=self.model, max_tokens=2048, system=system,
                messages=[{"role": "user", "content": user}], output_format=fmt,
            )
            parsed = response.parsed_output
            if parsed is None:
                raise RuntimeError(f"judge returned no parsed {fmt.__name__}")
            return parsed, response.usage.input_tokens, response.usage.output_tokens
        response = await self.client.responses.parse(
            model=self.model,
            input=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            text_format=fmt,
        )
        parsed = None
        for output in getattr(response, "output", []):
            for item in getattr(output, "content", []) or []:
                candidate = getattr(item, "parsed", None)
                if candidate is not None:
                    parsed = candidate if isinstance(candidate, fmt) else fmt.model_validate(candidate)
        if parsed is None:
            raise RuntimeError(f"judge returned no parsed {fmt.__name__}")
        usage = getattr(response, "usage", None)
        return parsed, (getattr(usage, "input_tokens", 0) or 0), (getattr(usage, "output_tokens", 0) or 0)

    async def consistency(self, page_text: str, flat_label: dict) -> JudgeResult:
        user = f"PAGE TEXT:\n{page_text}\n\nGROUND-TRUTH LABELS:\n{json.dumps(flat_label, ensure_ascii=False, indent=1)}"
        verdict, tin, tout = await self._parse(CONSISTENCY_PROMPT, user, ConsistencyVerdict)
        return JudgeResult(
            passed=not verdict.unsupported_fields,
            detail={"unsupported_fields": verdict.unsupported_fields, "notes": verdict.notes},
            input_tokens=tin,
            output_tokens=tout,
        )

    async def realism(self, page_text: str) -> JudgeResult:
        verdict, tin, tout = await self._parse(REALISM_PROMPT, page_text, RealismVerdict)
        return JudgeResult(
            passed=verdict.score >= self.realism_threshold,
            detail={"score": verdict.score, "reasons": verdict.reasons},
            input_tokens=tin,
            output_tokens=tout,
        )
