"""SROIE receipt extractors: OpenAI and Anthropic providers behind one interface.

Two provider families so the label audit's prelabel votes are cross-family
(contamination note: both providers have seen SROIE in training, so agreement with the
official label is still not an independent vote - see the audit protocol).
"""

from __future__ import annotations

from dataclasses import dataclass

from extraction_gym.adapters.sroie.schema import ReceiptExtraction

NAIVE_BASELINE_PROMPT = """Extract the company, date, address, and total from this receipt text. \
Return the values exactly as they appear on the receipt. Use null when a field is absent."""


@dataclass(frozen=True)
class SroieResult:
    extraction: dict
    input_tokens: int
    output_tokens: int


class OpenAISroieExtractor:
    def __init__(self, *, api_key: str, model: str = "gpt-4o-mini") -> None:
        from openai import AsyncOpenAI

        self.client = AsyncOpenAI(api_key=api_key)
        self.model = model

    async def extract(self, *, page_text: str, system_prompt: str) -> SroieResult:
        response = await self.client.responses.parse(
            model=self.model,
            input=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Receipt text:\n{page_text}"},
            ],
            text_format=ReceiptExtraction,
        )
        parsed = None
        for output in getattr(response, "output", []):
            for item in getattr(output, "content", []) or []:
                candidate = getattr(item, "parsed", None)
                if candidate is not None:
                    parsed = candidate
        usage = getattr(response, "usage", None)
        return SroieResult(
            extraction=parsed.model_dump(mode="json") if parsed else {},
            input_tokens=getattr(usage, "input_tokens", 0) or 0,
            output_tokens=getattr(usage, "output_tokens", 0) or 0,
        )


class AnthropicSroieExtractor:
    def __init__(self, *, model: str = "claude-haiku-4-5") -> None:
        from anthropic import AsyncAnthropic

        self.client = AsyncAnthropic()  # ANTHROPIC_API_KEY from env
        self.model = model

    async def extract(self, *, page_text: str, system_prompt: str) -> SroieResult:
        response = await self.client.messages.parse(
            model=self.model,
            max_tokens=1024,
            system=system_prompt,
            messages=[{"role": "user", "content": f"Receipt text:\n{page_text}"}],
            output_format=ReceiptExtraction,
        )
        parsed = response.parsed_output
        return SroieResult(
            extraction=parsed.model_dump(mode="json") if parsed else {},
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
        )
