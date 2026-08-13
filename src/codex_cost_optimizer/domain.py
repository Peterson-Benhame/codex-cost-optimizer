from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Literal


class ReasoningEffort(str, Enum):
    NONE = "none"
    MINIMAL = "minimal"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    XHIGH = "xhigh"
    MAX = "max"
    ULTRA = "ultra"


class ExecutionScope(str, Enum):
    MAIN_THREAD = "main_thread"
    SUBAGENT = "subagent"


class TaskPhase(str, Enum):
    MECHANICAL = "mechanical"
    DEFINED_IMPLEMENTATION = "defined_implementation"
    COMPLEX_ENGINEERING = "complex_engineering"
    INVESTIGATION = "investigation"


class Confidence(Enum):
    LOW = 1
    MEDIUM = 2
    HIGH = 3

    @property
    def score(self) -> int:
        return self.value


@dataclass(frozen=True)
class ModelDescriptor:
    id: str
    display_name: str
    description: str
    supported_efforts: tuple[ReasoningEffort, ...]
    default_effort: ReasoningEffort

    def __post_init__(self) -> None:
        if not self.id.strip():
            raise ValueError("model id must not be empty")
        if self.default_effort not in self.supported_efforts:
            raise ValueError("default effort must be advertised by model")

    def supports(self, effort: ReasoningEffort) -> bool:
        return effort in self.supported_efforts


@dataclass(frozen=True)
class RuntimeState:
    current_model: str
    current_effort: ReasoningEffort
    session_id: str | None = None
    thread_id: str | None = None


@dataclass(frozen=True)
class TaskMetadata:
    execution_scope: ExecutionScope = ExecutionScope.MAIN_THREAD
    spec_available: bool = False
    root_cause_known: bool | None = None
    estimated_files: int = 1
    cross_module: bool = False
    unexpected_error: bool = False
    risk: Literal["low", "medium", "high"] = "medium"
    expected_work_units: int = 5
    context_replay_risk: Literal["low", "medium", "high"] = "low"
    source_type: str | None = None
    source_name: str | None = None
    source_capability: str | None = None
    agent_name: str | None = None
    parent_agent_id: str | None = None
    parent_model: str | None = None
    parent_effort: ReasoningEffort | None = None

    def __post_init__(self) -> None:
        if self.estimated_files < 0:
            raise ValueError("estimated_files must be >= 0")
        if self.expected_work_units < 0:
            raise ValueError("expected_work_units must be >= 0")


@dataclass(frozen=True)
class TaskSignals:
    spec_available: bool
    root_cause_known: bool | None
    estimated_files: int
    cross_module: bool
    unexpected_error: bool
    risk: Literal["low", "medium", "high"]
    expected_work_units: int
    context_replay_risk: Literal["low", "medium", "high"]
    mechanical_hint: bool = False
    investigation_hint: bool = False
    implementation_hint: bool = False
    review_hint: bool = False


@dataclass(frozen=True)
class Classification:
    phase: TaskPhase
    confidence: Confidence
    reasons: tuple[str, ...] = field(default_factory=tuple)
    score: int = 0


@dataclass(frozen=True)
class RoutingRecommendation:
    current_model: str
    current_effort: ReasoningEffort
    target_model: str
    target_effort: ReasoningEffort
    reason: str
    cost_impact: str
    phase: TaskPhase
    confidence: Confidence
    phase_fingerprint: str
    estimated: bool = True

    @property
    def changes_configuration(self) -> bool:
        return (self.current_model, self.current_effort) != (self.target_model, self.target_effort)


@dataclass(frozen=True)
class ApprovalResult:
    approved: bool
    raw_answer: str | None = None


@dataclass(frozen=True)
class TokenUsage:
    input_tokens: int | None = None
    cached_input_tokens: int | None = None
    output_tokens: int | None = None
    reasoning_tokens: int | None = None
    total_tokens: int | None = None

    @classmethod
    def empty(cls) -> "TokenUsage":
        return cls()


@dataclass(frozen=True)
class MaterialityDecision:
    propose: bool
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class CostQuote:
    model: str
    amount: float | None
    unit: str | None
    is_estimated: bool
    pricing_stale: bool = False


@dataclass(frozen=True)
class PreparedTurn:
    task_text: str
    metadata: TaskMetadata
    runtime_state: RuntimeState
    signals: TaskSignals
    classification: Classification
    recommendation: RoutingRecommendation | None
    approval: ApprovalResult | None = None

    def with_approval(self, approval: ApprovalResult) -> "PreparedTurn":
        return PreparedTurn(
            task_text=self.task_text,
            metadata=self.metadata,
            runtime_state=self.runtime_state,
            signals=self.signals,
            classification=self.classification,
            recommendation=self.recommendation,
            approval=approval,
        )


@dataclass(frozen=True)
class ManualSwitchRequired:
    target_model: str
    target_effort: ReasoningEffort
    reason: str
    cost_impact: str


@dataclass(frozen=True)
class SubagentDispatch:
    model: str
    effort: ReasoningEffort
    change_authorized: bool
