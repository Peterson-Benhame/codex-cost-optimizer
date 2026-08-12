import pytest

from codex_cost_optimizer.classifier import DeterministicClassifier
from codex_cost_optimizer.domain import Confidence, TaskPhase, TaskSignals


def s(**overrides):
    base = dict(spec_available=False, root_cause_known=None, estimated_files=1, cross_module=False, unexpected_error=False, risk="medium", expected_work_units=5, context_replay_risk="low", mechanical_hint=False, investigation_hint=False, implementation_hint=False, review_hint=False)
    base.update(overrides)
    return TaskSignals(**base)


@pytest.mark.parametrize(("signals", "phase"), [
    (s(risk="low", mechanical_hint=True, estimated_files=1), TaskPhase.MECHANICAL),
    (s(spec_available=True, root_cause_known=True, implementation_hint=True, estimated_files=3), TaskPhase.DEFINED_IMPLEMENTATION),
    (s(cross_module=True, estimated_files=8, risk="high", root_cause_known=True), TaskPhase.COMPLEX_ENGINEERING),
    (s(root_cause_known=False, unexpected_error=True, cross_module=True, investigation_hint=True, risk="high"), TaskPhase.INVESTIGATION),
])
def test_classifies_four_design_levels(signals, phase):
    assert DeterministicClassifier().classify(signals).phase is phase


def test_contradictory_signals_produce_low_confidence_without_forcing_investigation():
    result = DeterministicClassifier().classify(s(spec_available=True, root_cause_known=True, mechanical_hint=True, investigation_hint=True, cross_module=True, risk="high", estimated_files=4))
    assert result.confidence is Confidence.LOW
    assert result.phase is not TaskPhase.INVESTIGATION
