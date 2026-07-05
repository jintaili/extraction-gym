"""Coffee extraction adapter: prompt + page text in, PageExtraction dict out.

Reuses coffee-value-app's production prompt, trimming, and response parsing directly
so the harness measures exactly what ships. The OpenAI call is made here (rather than
through OpenAILLMExtractor) to capture token usage for cost reporting.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from openai import AsyncOpenAI

from coffee_value_app.config import load_settings
from coffee_value_app.extractor import (
    EXTRACTION_SYSTEM_PROMPT,
    build_extraction_user_prompt,
    parse_structured_response,
    trim_page_text,
)
from coffee_value_app.schemas import PageExtraction


def production_prompt_id() -> str:
    return hashlib.sha256(EXTRACTION_SYSTEM_PROMPT.encode("utf-8")).hexdigest()[:10]


@dataclass(frozen=True)
class ExtractionResult:
    extraction: dict
    model: str
    prompt_id: str
    input_tokens: int
    output_tokens: int


class CoffeeExtractor:
    def __init__(self, *, client: AsyncOpenAI | None = None) -> None:
        self.settings = load_settings()
        self.client = client or AsyncOpenAI(api_key=self.settings.openai_api_key)

    async def extract(self, *, model: str, url: str, page_text: str) -> ExtractionResult:
        trimmed = trim_page_text(page_text, self.settings.max_page_text_chars)
        response = await self.client.responses.parse(
            model=model,
            input=[
                {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
                {"role": "user", "content": build_extraction_user_prompt(url=url, page_text=trimmed)},
            ],
            text_format=PageExtraction,
        )
        parsed = parse_structured_response(response)
        usage = getattr(response, "usage", None)
        return ExtractionResult(
            extraction=parsed.model_dump(mode="json"),
            model=model,
            prompt_id=production_prompt_id(),
            input_tokens=getattr(usage, "input_tokens", 0) or 0,
            output_tokens=getattr(usage, "output_tokens", 0) or 0,
        )
