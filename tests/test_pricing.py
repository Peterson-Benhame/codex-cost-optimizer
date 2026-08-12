import json
from datetime import date, timedelta
from pathlib import Path

from codex_cost_optimizer.domain import TokenUsage
from codex_cost_optimizer.pricing import PricingRegistry


def write_policy(path: Path, effective: str):
    path.write_text(json.dumps({"pricing": {"parent": {"effective_date": effective, "input_per_million": 100, "cached_input_per_million": 10, "output_per_million": 500, "currency_or_credit_unit": "credits", "source_url": "https://example"}}}))


def test_counterfactual_is_always_marked_estimated(tmp_path):
    p=tmp_path/"p.json"; write_policy(p, date.today().isoformat())
    estimate = PricingRegistry.from_file(p).estimate_parent_counterfactual(TokenUsage(input_tokens=1000, cached_input_tokens=200, output_tokens=100), "parent")
    assert estimate.is_estimated is True


def test_cached_input_is_not_double_charged_as_uncached(tmp_path):
    p=tmp_path/"p.json"; write_policy(p, date.today().isoformat())
    quote = PricingRegistry.from_file(p).quote(TokenUsage(input_tokens=1000, cached_input_tokens=200, output_tokens=100), "parent")
    expected = (800*100 + 200*10 + 100*500)/1_000_000
    assert quote.amount == expected


def test_old_pricing_is_marked_stale(tmp_path):
    p=tmp_path/"p.json"; write_policy(p, (date.today()-timedelta(days=31)).isoformat())
    assert PricingRegistry.from_file(p).quote(TokenUsage(input_tokens=100), "parent").pricing_stale is True
