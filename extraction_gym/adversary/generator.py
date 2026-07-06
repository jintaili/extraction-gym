"""Synthetic pressure-page generation.

Control rule (DESIGN.md): the generator NEVER sees gold pages or gold labels. Its
context is the failure taxonomy entry, the target schema, and a format description of
the normalized text the production pipeline emits.
"""

from __future__ import annotations

from dataclasses import dataclass

from openai import AsyncOpenAI
from pydantic import BaseModel, ConfigDict

from coffee_value_app.extractor import parse_structured_response
from coffee_value_app.schemas import PageExtraction


class SyntheticPage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    page_text: str
    extraction: PageExtraction


@dataclass(frozen=True)
class GeneratedPage:
    page_text: str
    extraction: dict
    input_tokens: int
    output_tokens: int


GENERATOR_SYSTEM_PROMPT = """You create realistic synthetic specialty-coffee product pages to stress-test an \
LLM extraction system, together with the exactly-correct ground-truth extraction for each page.

The page_text must look like the output of an html-to-text pipeline run on a real roaster product page: \
a Title line, stray navigation fragments, a product name, price and size lines, spec lines \
(Producer: / Region: / Process: / Variety: / Altitude:), prose paragraphs in a plausible roaster voice, \
and usually an "Embedded product variant data:" block listing variants like \
"- id=123; title=250g; name=X - 250g; sku=ABC; price=18.00 USD; package_grams=250.000g [default_for_inference]". \
Details must be internally coherent (origin, variety, process, altitude, price level all plausible together).

The extraction must be EXACTLY what a perfect extractor would produce from this page under these rules: \
only page-supported values; verbatim variety/process terms; verbatim text spans in the page's language; \
null/unknown/empty for absent fields; page_type and is_specialty_coffee set correctly; \
price fields for the default (or pinned) variant; package_grams in grams; bags_count only for multi-bag sets.

Most importantly: build the page so it embodies the requested failure category - a trap that a naive \
extractor plausibly falls into - while your ground truth stays correct."""


def build_generator_user_prompt(category: str, invent: bool) -> str:
    if invent:
        return (
            "Invent ONE new plausible failure category not in this list, then generate a page for it:\n"
            f"{category}\n\nState your invented category name in the first line of the page_text as a "
            "comment line starting with 'CATEGORY: ' (it will be stripped)."
        )
    return f"Failure category to embody:\n{category}"


class AdversaryGenerator:
    def __init__(self, *, client: AsyncOpenAI, model: str) -> None:
        self.client = client
        self.model = model

    async def generate(self, category: str, *, invent: bool = False) -> GeneratedPage:
        response = await self.client.responses.parse(
            model=self.model,
            input=[
                {"role": "system", "content": GENERATOR_SYSTEM_PROMPT},
                {"role": "user", "content": build_generator_user_prompt(category, invent)},
            ],
            text_format=SyntheticPage,
        )
        parsed = None
        for output in getattr(response, "output", []):
            for item in getattr(output, "content", []) or []:
                candidate = getattr(item, "parsed", None)
                if candidate is not None:
                    parsed = candidate if isinstance(candidate, SyntheticPage) else SyntheticPage.model_validate(candidate)
        if parsed is None:
            raise RuntimeError("generator returned no parsed SyntheticPage")
        usage = getattr(response, "usage", None)
        return GeneratedPage(
            page_text=parsed.page_text,
            extraction=parsed.extraction.model_dump(mode="json"),
            input_tokens=getattr(usage, "input_tokens", 0) or 0,
            output_tokens=getattr(usage, "output_tokens", 0) or 0,
        )


def deterministic_sanity(page_text: str, category: str) -> list[str]:
    """Cheap non-LLM checks; any problem discards the page."""
    import re

    problems = []
    if len(page_text) < 300:
        problems.append("page text implausibly short")
    price_expected = not re.search(r"missing[- ]price|no[- ]price", category, re.I)
    if price_expected and not re.search(r"[$€£¥]|\b(USD|EUR|DKK|NOK|SEK|JPY|GBP|AED|kr)\b", page_text):
        problems.append("no price/currency marker on page")
    return problems


# parse_structured_response imported for reuse by callers running the incumbent.
__all__ = [
    "AdversaryGenerator",
    "GeneratedPage",
    "SyntheticPage",
    "deterministic_sanity",
    "parse_structured_response",
]
