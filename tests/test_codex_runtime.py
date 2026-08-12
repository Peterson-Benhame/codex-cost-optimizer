import pytest

from codex_cost_optimizer.catalog import CatalogSnapshot
from codex_cost_optimizer.codex_runtime import CodexRuntime, UnsupportedConfiguration
from codex_cost_optimizer.domain import ModelDescriptor, ReasoningEffort


class FakeResult:
    id = "turn-1"
    usage = type("Usage", (), {"input_tokens": 100, "cached_input_tokens": 20, "output_tokens": 30})()


class FakeThread:
    id = "thread-1"
    def __init__(self): self.calls = []
    def run(self, input, *, model=None, effort=None):
        self.calls.append({"input": input, "model": model, "effort": getattr(effort, "value", effort)})
        return FakeResult()


def catalog():
    return CatalogSnapshot((ModelDescriptor("gpt-x", "GPT X", "", (ReasoningEffort.LOW, ReasoningEffort.MEDIUM), ReasoningEffort.MEDIUM),))


def test_run_turn_passes_exact_authorized_configuration():
    thread = FakeThread(); runtime = CodexRuntime(codex=None, catalog_snapshot=catalog())
    runtime.run_turn(thread, "do work", model="gpt-x", effort=ReasoningEffort.MEDIUM)
    assert thread.calls == [{"input": "do work", "model": "gpt-x", "effort": "medium"}]


def test_unsupported_pair_is_blocked_before_runtime_call():
    thread = FakeThread(); runtime = CodexRuntime(codex=None, catalog_snapshot=catalog())
    with pytest.raises(UnsupportedConfiguration):
        runtime.run_turn(thread, "do work", model="gpt-x", effort=ReasoningEffort.HIGH)
    assert thread.calls == []


def test_usage_is_mapped_without_inventing_missing_reasoning_tokens():
    usage = CodexRuntime(codex=None, catalog_snapshot=catalog()).read_usage(FakeResult())
    assert usage.input_tokens == 100
    assert usage.cached_input_tokens == 20
    assert usage.output_tokens == 30
    assert usage.reasoning_tokens is None
    assert usage.total_tokens == 130
