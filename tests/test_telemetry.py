from pathlib import Path

import pytest
from pydantic import ValidationError

from codex_cost_optimizer.domain import TokenUsage
from codex_cost_optimizer.telemetry import RoutingEvent, TelemetryStore, default_telemetry_path, usage_fields


def test_default_telemetry_path_is_not_relative_to_project(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    path = default_telemetry_path()
    assert path == tmp_path / "state" / "codex-cost-optimizer" / "events.jsonl"


def test_event_schema_rejects_prompt_content():
    with pytest.raises(ValidationError):
        RoutingEvent(event_type="routing", session_id="s", prompt="secret source code")


def test_jsonl_append_and_session_summary(tmp_path):
    store = TelemetryStore(tmp_path / "events.jsonl")
    store.append(RoutingEvent(event_type="routing", session_id="s", current_model="sol", target_model="luna", authorized=True))
    store.append(RoutingEvent(event_type="turn_usage", session_id="s", actual_model="luna", input_tokens=100, output_tokens=20, total_tokens=120))
    summary = store.session_summary("s")
    assert summary["events"] == 2
    assert summary["input_tokens"] == 100
    assert summary["output_tokens"] == 20


def test_usage_fields_preserve_unavailable_values():
    fields = usage_fields(TokenUsage(input_tokens=10, cached_input_tokens=None, output_tokens=2))
    assert fields["cached_input_tokens"] is None
    assert fields["reasoning_tokens"] is None


def test_rate_card_calculation_is_not_recorded_as_actual_cost(tmp_path):
    store = TelemetryStore(tmp_path / "events.jsonl")
    store.append(RoutingEvent(event_type="turn_usage", session_id="s", cost_estimated=1.25, cost_estimated_unit="credits"))
    summary = store.session_summary("s")
    assert summary["actual_cost"] == 0.0
    assert summary["cost_estimated"] == 1.25
