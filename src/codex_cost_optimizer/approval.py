from __future__ import annotations

from typing import Callable, Protocol

from .domain import ApprovalResult, RoutingRecommendation


class ApprovalProvider(Protocol):
    def request(self, recommendation: RoutingRecommendation) -> ApprovalResult: ...


class TerminalApprovalProvider:
    YES = {"s", "sim", "y", "yes"}

    def __init__(self, input_fn: Callable[[str], str] = input):
        self._input = input_fn

    def render(self, rec: RoutingRecommendation) -> str:
        return (
            "Troca recomendada\n\n"
            f"Atual: {rec.current_model} / {rec.current_effort.value}\n"
            f"Novo: {rec.target_model} / {rec.target_effort.value}\n\n"
            f"Motivo:\n{rec.reason}\n\n"
            f"Impacto:\n{rec.cost_impact}\n\n"
            "Autorizar troca? [S/N] "
        )

    def request(self, recommendation: RoutingRecommendation) -> ApprovalResult:
        raw = self._input(self.render(recommendation))
        return ApprovalResult(approved=(raw or "").strip().lower() in self.YES, raw_answer=raw)
