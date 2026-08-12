from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from .catalog import CatalogSnapshot
from .domain import Classification, Confidence, ReasoningEffort, RoutingRecommendation, RuntimeState, TaskPhase


EFFORT_ORDER = [
    ReasoningEffort.NONE,
    ReasoningEffort.MINIMAL,
    ReasoningEffort.LOW,
    ReasoningEffort.MEDIUM,
    ReasoningEffort.HIGH,
    ReasoningEffort.XHIGH,
    ReasoningEffort.MAX,
    ReasoningEffort.ULTRA,
]


@dataclass(frozen=True)
class ModelProfile:
    model_id: str
    capability_rank: int
    cost_rank: int
    preferred_for: tuple[TaskPhase, ...]
    pricing_status: str = "known"


class ModelPolicy:
    def __init__(self, profiles: dict[str, ModelProfile]):
        self.profiles = profiles

    @classmethod
    def from_file(cls, path: str | Path) -> "ModelPolicy":
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        profiles = {}
        for model_id, raw in payload.get("profiles", {}).items():
            profiles[model_id] = ModelProfile(
                model_id=model_id,
                capability_rank=int(raw["capability_rank"]),
                cost_rank=int(raw["cost_rank"]),
                preferred_for=tuple(TaskPhase(v) for v in raw.get("preferred_for", [])),
                pricing_status=raw.get("pricing_status", "known"),
            )
        return cls(profiles)

    def profile(self, model_id: str) -> ModelProfile | None:
        return self.profiles.get(model_id)


class Router:
    _phase_capability = {
        TaskPhase.MECHANICAL: 1,
        TaskPhase.DEFINED_IMPLEMENTATION: 2,
        TaskPhase.COMPLEX_ENGINEERING: 3,
        TaskPhase.INVESTIGATION: 4,
    }
    _phase_effort = {
        TaskPhase.MECHANICAL: ReasoningEffort.LOW,
        TaskPhase.DEFINED_IMPLEMENTATION: ReasoningEffort.MEDIUM,
        TaskPhase.COMPLEX_ENGINEERING: ReasoningEffort.MEDIUM,
        TaskPhase.INVESTIGATION: ReasoningEffort.HIGH,
    }

    def __init__(self, policy: ModelPolicy):
        self.policy = policy

    def recommend(self, classification: Classification, catalog: CatalogSnapshot, current: RuntimeState) -> RoutingRecommendation | None:
        required = self._phase_capability[classification.phase]
        if classification.confidence is Confidence.LOW:
            required = min(4, required + 1)
        candidates = []
        for descriptor in catalog.models:
            profile = self.policy.profile(descriptor.id)
            if profile is None or profile.capability_rank < required:
                continue
            target_effort = self._best_effort(descriptor.supported_efforts, self._phase_effort[classification.phase])
            if target_effort is None:
                continue
            preferred_penalty = 0 if classification.phase in profile.preferred_for else 1
            candidates.append((profile.cost_rank, preferred_penalty, profile.capability_rank, descriptor.id, target_effort))
        if not candidates:
            return None
        _, _, _, target_model, target_effort = min(candidates)
        if target_model == current.current_model and target_effort == current.current_effort:
            return None
        current_profile = self.policy.profile(current.current_model)
        target_profile = self.policy.profile(target_model)
        if current_profile and target_profile:
            if target_profile.cost_rank < current_profile.cost_rank:
                impact = "Redução esperada de custo para esta fase."
            elif target_profile.cost_rank > current_profile.cost_rank:
                impact = "Aumento esperado de custo para reduzir risco de erro ou retrabalho."
            else:
                impact = "Custo relativo semelhante; mudança recomendada por adequação de capacidade/reasoning."
        else:
            impact = "Impacto exato de custo desconhecido; decisão baseada apenas em perfis conhecidos."
        reason = self._reason(classification, target_model, target_effort)
        fp_data = f"{classification.phase.value}|{classification.score}|{classification.confidence.name}|{target_model}|{target_effort.value}"
        fingerprint = hashlib.sha256(fp_data.encode()).hexdigest()[:16]
        return RoutingRecommendation(
            current_model=current.current_model,
            current_effort=current.current_effort,
            target_model=target_model,
            target_effort=target_effort,
            reason=reason,
            cost_impact=impact,
            phase=classification.phase,
            confidence=classification.confidence,
            phase_fingerprint=fingerprint,
        )

    @staticmethod
    def _best_effort(supported: tuple[ReasoningEffort, ...], preferred: ReasoningEffort) -> ReasoningEffort | None:
        if preferred in supported:
            return preferred
        preferred_index = EFFORT_ORDER.index(preferred)
        lower = [e for e in supported if EFFORT_ORDER.index(e) < preferred_index]
        if lower:
            return max(lower, key=EFFORT_ORDER.index)
        higher = [e for e in supported if EFFORT_ORDER.index(e) > preferred_index]
        return min(higher, key=EFFORT_ORDER.index) if higher else None

    @staticmethod
    def _reason(classification: Classification, model: str, effort: ReasoningEffort) -> str:
        core = ", ".join(classification.reasons[:3]) or "sinais locais"
        safety = " Foi aplicada margem de segurança por baixa confiança." if classification.confidence is Confidence.LOW else ""
        return f"Fase {classification.phase.value} classificada por: {core}. {model}/{effort.value} é a configuração disponível de menor custo que atende ao nível requerido.{safety}"
