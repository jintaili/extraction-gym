"""Per-run USD spend tracking with a hard cap.

Prices are $/1M tokens (input, output), config-driven; defaults reflect OpenAI list
prices as of July 2026. Unknown models raise rather than silently costing $0.
"""

from __future__ import annotations

DEFAULT_PRICES: dict[str, tuple[float, float]] = {
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-5.5": (5.00, 30.00),
    "gpt-5.4": (2.50, 15.00),
    "claude-haiku-4-5": (1.00, 5.00),
    "claude-sonnet-4-6": (3.00, 15.00),
}


class BudgetExceeded(Exception):
    pass


class BudgetTracker:
    def __init__(self, max_usd: float, prices: dict[str, tuple[float, float]] | None = None) -> None:
        self.max_usd = max_usd
        self.prices = prices or DEFAULT_PRICES
        self.spent_usd = 0.0
        self.by_model: dict[str, float] = {}

    def cost_of(self, model: str, input_tokens: int, output_tokens: int) -> float:
        if model not in self.prices:
            raise KeyError(f"no price configured for model {model!r}; add it to the price table")
        rate_in, rate_out = self.prices[model]
        return input_tokens / 1_000_000 * rate_in + output_tokens / 1_000_000 * rate_out

    def add(self, model: str, input_tokens: int, output_tokens: int) -> float:
        cost = self.cost_of(model, input_tokens, output_tokens)
        self.spent_usd += cost
        self.by_model[model] = self.by_model.get(model, 0.0) + cost
        if self.spent_usd > self.max_usd:
            raise BudgetExceeded(
                f"spend ${self.spent_usd:.2f} exceeds hard cap ${self.max_usd:.2f}"
            )
        return cost
