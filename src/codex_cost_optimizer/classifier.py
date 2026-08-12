from __future__ import annotations

from .domain import Classification, Confidence, TaskPhase, TaskSignals

RISK_HIGH = 3
ROOT_CAUSE_UNKNOWN = 3
CROSS_MODULE = 2
MANY_FILES = 2
SPEC_AVAILABLE = -1
ROOT_CAUSE_KNOWN = -2
MECHANICAL_ACTION = -3
UNEXPECTED_ERROR = 2
INVESTIGATION_HINT = 1
IMPLEMENTATION_HINT = -1


class DeterministicClassifier:
    def classify(self, signals: TaskSignals) -> Classification:
        score = 0
        reasons: list[str] = []
        contradictions = 0
        if signals.risk == "high":
            score += RISK_HIGH; reasons.append("high technical risk")
        elif signals.risk == "low":
            score -= 1; reasons.append("low technical risk")
        if signals.root_cause_known is False:
            score += ROOT_CAUSE_UNKNOWN; reasons.append("root cause unknown")
        elif signals.root_cause_known is True:
            score += ROOT_CAUSE_KNOWN; reasons.append("root cause known")
        if signals.cross_module:
            score += CROSS_MODULE; reasons.append("cross-module work")
        if signals.estimated_files >= 6:
            score += MANY_FILES; reasons.append("many files expected")
        elif signals.estimated_files <= 2:
            score -= 1
        if signals.spec_available:
            score += SPEC_AVAILABLE; reasons.append("approved/spec context available")
        if signals.mechanical_hint:
            score += MECHANICAL_ACTION; reasons.append("mechanical task hint")
        if signals.unexpected_error:
            score += UNEXPECTED_ERROR; reasons.append("unexpected error")
        if signals.investigation_hint:
            score += INVESTIGATION_HINT; reasons.append("investigation hint")
        if signals.implementation_hint:
            score += IMPLEMENTATION_HINT; reasons.append("implementation hint")
        if signals.mechanical_hint and (signals.investigation_hint or signals.cross_module or signals.risk == "high"):
            contradictions += 1
        if signals.root_cause_known is True and signals.investigation_hint:
            contradictions += 1

        if score <= -5:
            phase = TaskPhase.MECHANICAL
        elif score <= 0:
            phase = TaskPhase.DEFINED_IMPLEMENTATION
        elif score <= 6:
            phase = TaskPhase.COMPLEX_ENGINEERING
        else:
            phase = TaskPhase.INVESTIGATION

        if signals.root_cause_known is True and signals.spec_available and phase is TaskPhase.INVESTIGATION:
            phase = TaskPhase.COMPLEX_ENGINEERING
            contradictions += 1

        distance = min(abs(score - boundary) for boundary in (-5, 0, 6))
        if contradictions >= 1:
            confidence = Confidence.LOW
        elif distance >= 2:
            confidence = Confidence.HIGH
        else:
            confidence = Confidence.MEDIUM
        return Classification(phase=phase, confidence=confidence, reasons=tuple(reasons), score=score)
