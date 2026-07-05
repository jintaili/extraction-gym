"""URL to normalized page text, using coffee-value-app's exact inference-time pipeline.

Parity constraint: the referee must see what production sees. This module therefore
imports the production fetch and page-context code directly instead of reimplementing it.
coffee-value-app must be installed (pip install -e ../coffee-value-app).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from coffee_value_app.analysis import build_page_context
from coffee_value_app.fetcher import fetch_product_page


@dataclass(frozen=True)
class PageSnapshot:
    url: str
    final_url: str
    fetched_at: str
    text: str


async def fetch_normalized_page(url: str) -> PageSnapshot:
    page = await fetch_product_page(url)
    text = build_page_context(page.text, page.final_url)
    return PageSnapshot(
        url=url,
        final_url=page.final_url,
        fetched_at=datetime.now(UTC).isoformat(timespec="seconds"),
        text=text,
    )
