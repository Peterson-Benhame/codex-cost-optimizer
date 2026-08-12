from codex_cost_optimizer.domain import Confidence, ModelDescriptor, ReasoningEffort, TaskPhase


def test_model_supports_only_advertised_effort():
    model = ModelDescriptor(
        id="gpt-example",
        display_name="GPT Example",
        description="example",
        supported_efforts=(ReasoningEffort.LOW, ReasoningEffort.MEDIUM),
        default_effort=ReasoningEffort.MEDIUM,
    )
    assert model.supports(ReasoningEffort.LOW)
    assert not model.supports(ReasoningEffort.HIGH)


def test_task_phases_are_explicit():
    assert {p.value for p in TaskPhase} == {
        "mechanical",
        "defined_implementation",
        "complex_engineering",
        "investigation",
    }


def test_confidence_order_is_explicit():
    assert Confidence.HIGH.score > Confidence.MEDIUM.score > Confidence.LOW.score
