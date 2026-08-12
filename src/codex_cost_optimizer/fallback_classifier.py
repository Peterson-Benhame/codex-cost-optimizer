from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Any, Protocol

from .catalog import CatalogSnapshot
from .domain import Classification, Confidence, ReasoningEffort, TaskPhase, TokenUsage
from .pricing import PricingRegistry
from .routing import ModelPolicy
from .telemetry import RoutingEvent, TelemetryStore


@dataclass(frozen=True)
class RoutingSummary:
    estimated_files: int = 1
    cross_module: bool = False
    risk: str = "medium"
    spec_available: bool = False
    root_cause_known: bool | None = None
    unexpected_error: bool = False
    expected_work_units: int = 5


class TokenEstimator(Protocol):
    def estimate(self, payload: str) -> int: ...


class RoughTokenEstimator:
    def estimate(self, payload: str) -> int:
        return max(1, (len(payload) + 2) // 3)


class ClassifierClient(Protocol):
    def classify(self, *, payload: str, model: str, max_output_tokens: int, output_schema: dict[str, Any]) -> tuple[dict[str, Any], dict[str, int | None]]: ...


OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "phase": {"enum": ["mechanical", "defined_implementation", "complex_engineering", "investigation"]},
        "confidence": {"enum": ["low", "medium", "high"]},
    },
    "required": ["phase", "confidence"],
    "additionalProperties": False,
}


class FallbackBudgetExceeded(RuntimeError):
    pass


def select_fallback_model(catalog: CatalogSnapshot, policy: ModelPolicy) -> tuple[str, ReasoningEffort] | None:
    candidates=[]
    for descriptor in catalog.models:
        profile=policy.profile(descriptor.id)
        if profile is None:
            continue
        effort=ReasoningEffort.LOW if descriptor.supports(ReasoningEffort.LOW) else descriptor.default_effort
        pricing_penalty=1 if profile.pricing_status == "research_preview" else 0
        candidates.append((profile.cost_rank,pricing_penalty,profile.capability_rank,descriptor.id,effort))
    if not candidates:
        return None
    _,_,_,model,effort=min(candidates)
    return model,effort


class CodexClassifierClient:
    """Production metadata-only classifier using an ephemeral Codex thread."""
    def __init__(self, *, codex: Any, runtime: Any, effort: ReasoningEffort):
        self.codex=codex; self.runtime=runtime; self.effort=effort

    def classify(self, *, payload: str, model: str, max_output_tokens: int, output_schema: dict[str, Any]) -> tuple[dict[str, Any], dict[str, int | None]]:
        thread=self.codex.thread_start(ephemeral=True,model=model)
        instruction=(
            "Classify ONLY the routing metadata below. Do not infer repository contents. "
            "Return only the structured schema fields phase and confidence. Metadata: " + payload
        )
        result=thread.run(instruction,model=model,effort=self.runtime._to_sdk_effort(self.effort),output_schema=output_schema)
        usage=self.runtime.read_usage(result)
        if usage.output_tokens is not None and usage.output_tokens > max_output_tokens:
            raise FallbackBudgetExceeded(f"fallback output used {usage.output_tokens} tokens, budget {max_output_tokens}")
        raw=json.loads(result.final_response or "{}")
        return raw,{
            "input_tokens":usage.input_tokens,"cached_input_tokens":usage.cached_input_tokens,"output_tokens":usage.output_tokens,
            "reasoning_tokens":usage.reasoning_tokens,"total_tokens":usage.total_tokens,
        }


class FallbackClassifier:
    MAX_INPUT_TOKENS = 1000
    MAX_OUTPUT_TOKENS = 80

    def __init__(self, *, client: ClassifierClient, estimator: TokenEstimator | None = None, model_id: str, telemetry: TelemetryStore | None = None, session_id: str = "router", pricing: PricingRegistry | None = None):
        self.client = client
        self.estimator = estimator or RoughTokenEstimator()
        self.model_id = model_id
        self.telemetry = telemetry
        self.session_id = session_id
        self.pricing = pricing

    def classify(self, summary: RoutingSummary, local: Classification, *, material_benefit: bool, session_id: str | None = None) -> Classification:
        if local.confidence is not Confidence.LOW or not material_benefit:
            return local
        payload = json.dumps(asdict(summary), separators=(",", ":"), ensure_ascii=False)
        estimated_tokens = self.estimator.estimate(payload)
        if estimated_tokens > self.MAX_INPUT_TOKENS:
            return local
        raw, usage = self.client.classify(payload=payload, model=self.model_id, max_output_tokens=self.MAX_OUTPUT_TOKENS, output_schema=OUTPUT_SCHEMA)
        try:
            result = Classification(TaskPhase(raw["phase"]), Confidence[raw["confidence"].upper()], ("ai fallback metadata classification",), local.score)
        except (KeyError, ValueError):
            return local
        if self.telemetry:
            cost_estimated=None; cost_unit=None; stale=None
            if self.pricing is not None:
                token_usage=TokenUsage(input_tokens=usage.get("input_tokens"),cached_input_tokens=usage.get("cached_input_tokens"),output_tokens=usage.get("output_tokens"),reasoning_tokens=usage.get("reasoning_tokens"),total_tokens=usage.get("total_tokens"))
                quote=self.pricing.quote(token_usage,self.model_id); cost_estimated=quote.amount; cost_unit=quote.unit; stale=quote.pricing_stale
            self.telemetry.append(RoutingEvent(
                event_type="router_ai_overhead",
                session_id=session_id or self.session_id,
                actual_model=self.model_id,
                actual_effort=getattr(getattr(self.client,"effort",None),"value",None),
                decision_source="ai_fallback",
                input_tokens=usage.get("input_tokens"),
                cached_input_tokens=usage.get("cached_input_tokens"),
                output_tokens=usage.get("output_tokens"),
                reasoning_tokens=usage.get("reasoning_tokens"),
                total_tokens=usage.get("total_tokens"),
                cost_estimated=cost_estimated,cost_estimated_unit=cost_unit,pricing_stale=stale,
            ))
        return result
