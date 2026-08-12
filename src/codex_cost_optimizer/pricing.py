from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from .domain import CostQuote, TokenUsage


@dataclass(frozen=True)
class PricingEntry:
    model: str
    effective_date: date
    input_per_million: float
    cached_input_per_million: float
    output_per_million: float
    unit: str
    source_url: str

    @property
    def stale(self) -> bool:
        return (date.today() - self.effective_date).days > 30


class PricingRegistry:
    def __init__(self, entries: dict[str, PricingEntry]):
        self.entries = entries

    @classmethod
    def from_file(cls, path: str | Path) -> "PricingRegistry":
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        entries = {}
        for model, item in raw.get("pricing", {}).items():
            entries[model] = PricingEntry(
                model=model,
                effective_date=date.fromisoformat(item["effective_date"]),
                input_per_million=float(item["input_per_million"]),
                cached_input_per_million=float(item["cached_input_per_million"]),
                output_per_million=float(item["output_per_million"]),
                unit=item["currency_or_credit_unit"],
                source_url=item["source_url"],
            )
        return cls(entries)

    def quote(self, usage: TokenUsage, model: str) -> CostQuote:
        entry = self.entries.get(model)
        if entry is None or usage.input_tokens is None:
            return CostQuote(model=model, amount=None, unit=entry.unit if entry else None, is_estimated=False, pricing_stale=entry.stale if entry else False)
        cached = usage.cached_input_tokens or 0
        uncached = max(0, usage.input_tokens - cached)
        output = usage.output_tokens or 0
        amount = (uncached * entry.input_per_million + cached * entry.cached_input_per_million + output * entry.output_per_million) / 1_000_000
        return CostQuote(model=model, amount=amount, unit=entry.unit, is_estimated=False, pricing_stale=entry.stale)

    def estimate_parent_counterfactual(self, usage: TokenUsage, parent_model: str) -> CostQuote:
        quote = self.quote(usage, parent_model)
        return CostQuote(model=parent_model, amount=quote.amount, unit=quote.unit, is_estimated=True, pricing_stale=quote.pricing_stale)
