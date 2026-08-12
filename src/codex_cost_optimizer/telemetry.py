from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .domain import TokenUsage


def default_telemetry_path() -> Path:
    if sys.platform.startswith("win"):
        root = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        return root / "codex-cost-optimizer" / "telemetry" / "events.jsonl"
    root = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state"))
    return root / "codex-cost-optimizer" / "events.jsonl"


class RoutingEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_type: str
    session_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    thread_id: str | None = None
    phase: str | None = None
    confidence: str | None = None
    decision_source: str | None = None
    source_type: str | None = None
    source_name: str | None = None
    source_capability: str | None = None
    agent_name: str | None = None
    agent_id: str | None = None
    parent_agent_id: str | None = None
    current_model: str | None = None
    current_effort: str | None = None
    target_model: str | None = None
    target_effort: str | None = None
    actual_model: str | None = None
    actual_effort: str | None = None
    parent_model: str | None = None
    parent_effort: str | None = None
    authorized: bool | None = None
    switch_confirmed: bool | None = None
    reason_code: str | None = None
    phase_fingerprint: str | None = None
    input_tokens: int | None = None
    cached_input_tokens: int | None = None
    output_tokens: int | None = None
    reasoning_tokens: int | None = None
    total_tokens: int | None = None
    actual_cost: float | None = None
    actual_cost_unit: str | None = None
    cost_estimated: float | None = None
    cost_estimated_unit: str | None = None
    cost_if_parent_estimated: float | None = None
    savings_estimated: float | None = None
    savings_percent_estimated: float | None = None
    pricing_stale: bool | None = None
    workspace_hash: str | None = None


def usage_fields(usage: TokenUsage) -> dict[str, int | None]:
    return {
        "input_tokens": usage.input_tokens,
        "cached_input_tokens": usage.cached_input_tokens,
        "output_tokens": usage.output_tokens,
        "reasoning_tokens": usage.reasoning_tokens,
        "total_tokens": usage.total_tokens,
    }


class TelemetryStore:
    def __init__(self, path: str | Path | None = None):
        self.path = Path(path) if path else default_telemetry_path()

    def append(self, event: RoutingEvent) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        line = event.model_dump_json(exclude_none=False) + "\n"
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(line)
            handle.flush()
            os.fsync(handle.fileno())

    def session_summary(self, session_id: str) -> dict[str, Any]:
        totals = {"events": 0, "input_tokens": 0, "cached_input_tokens": 0, "output_tokens": 0, "reasoning_tokens": 0, "total_tokens": 0, "actual_cost": 0.0, "cost_estimated": 0.0, "savings_estimated": 0.0, "router_actual_cost": 0.0, "router_cost_estimated": 0.0, "router_input_tokens": 0, "router_output_tokens": 0, "local_decisions": 0, "ai_decisions": 0}
        if not self.path.exists():
            return totals
        with self.path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                raw = json.loads(line)
                if raw.get("session_id") != session_id:
                    continue
                totals["events"] += 1
                for key in ("input_tokens", "cached_input_tokens", "output_tokens", "reasoning_tokens", "total_tokens"):
                    totals[key] += raw.get(key) or 0
                totals["actual_cost"] += raw.get("actual_cost") or 0.0
                totals["cost_estimated"] += raw.get("cost_estimated") or 0.0
                totals["savings_estimated"] += raw.get("savings_estimated") or 0.0
                if raw.get("event_type") == "router_ai_overhead":
                    totals["ai_decisions"] += 1
                    totals["router_actual_cost"] += raw.get("actual_cost") or 0.0
                    totals["router_cost_estimated"] += raw.get("cost_estimated") or 0.0
                    totals["router_input_tokens"] += raw.get("input_tokens") or 0
                    totals["router_output_tokens"] += raw.get("output_tokens") or 0
                elif raw.get("event_type") == "routing" and raw.get("decision_source") == "local":
                    totals["local_decisions"] += 1
        return totals
