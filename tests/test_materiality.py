from codex_cost_optimizer.materiality import MaterialityGate, RejectionRegistry, phase_fingerprint


def test_short_phase_does_not_interrupt_for_small_saving():
    result = MaterialityGate().should_propose(current_cost_rank=3, target_cost_rank=2, estimated_work_units=1, context_replay_risk="medium")
    assert result.propose is False


def test_long_phase_with_material_gap_is_proposed():
    result = MaterialityGate().should_propose(current_cost_rank=4, target_cost_rank=2, estimated_work_units=20, context_replay_risk="low")
    assert result.propose is True


def test_rejected_recommendation_is_suppressed_until_phase_fingerprint_changes():
    registry = RejectionRegistry(); fp = phase_fingerprint("mechanical", {"files": 2, "risk": "low"})
    registry.reject(fp)
    assert registry.is_rejected(fp)
    assert not registry.is_rejected(phase_fingerprint("defined_implementation", {"files": 2, "risk": "low"}))
