from codex_cost_optimizer.domain import TaskMetadata
from codex_cost_optimizer.signals import SignalExtractor


extractor = SignalExtractor()


def test_spec_and_known_root_cause_signal_defined_implementation():
    signals = extractor.extract(
        "Implemente a SPEC-008 já aprovada",
        TaskMetadata(spec_available=True, root_cause_known=True, estimated_files=3, cross_module=False, unexpected_error=False),
    )
    assert signals.spec_available is True
    assert signals.root_cause_known is True
    assert signals.estimated_files == 3
    assert signals.implementation_hint is True


def test_single_investigation_word_cannot_override_strong_metadata():
    signals = extractor.extract(
        "Investigue este método e implemente a correção conhecida",
        TaskMetadata(spec_available=True, root_cause_known=True, estimated_files=1, cross_module=False, unexpected_error=False),
    )
    assert signals.investigation_hint is True
    assert signals.root_cause_known is True
    assert signals.estimated_files == 1


def test_mechanical_hints_are_weak_text_evidence():
    signals = extractor.extract("Adicione comentários XML em seis métodos", TaskMetadata(risk="low", estimated_files=1))
    assert signals.mechanical_hint is True
