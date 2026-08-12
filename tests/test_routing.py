import json
from pathlib import Path

from codex_cost_optimizer.catalog import CatalogSnapshot
from codex_cost_optimizer.domain import Classification, Confidence, ModelDescriptor, ReasoningEffort, RuntimeState, TaskPhase
from codex_cost_optimizer.routing import ModelPolicy, Router


def model(mid, efforts=(ReasoningEffort.LOW, ReasoningEffort.MEDIUM, ReasoningEffort.HIGH)):
    return ModelDescriptor(mid, mid, "", efforts, efforts[min(1, len(efforts)-1)])


def policy(tmp_path: Path):
    data = {"profiles": {
        "cheap": {"capability_rank": 2, "cost_rank": 1, "preferred_for": ["mechanical", "defined_implementation"]},
        "strong": {"capability_rank": 4, "cost_rank": 4, "preferred_for": ["complex_engineering", "investigation"]}
    }}
    p = tmp_path / "policy.json"; p.write_text(json.dumps(data))
    return ModelPolicy.from_file(p)


def c(phase, confidence=Confidence.HIGH):
    return Classification(phase=phase, confidence=confidence, reasons=("test",))


def test_recommendation_is_always_from_runtime_catalog(tmp_path):
    router = Router(policy(tmp_path))
    rec = router.recommend(c(TaskPhase.MECHANICAL), CatalogSnapshot((model("cheap"),)), RuntimeState("strong", ReasoningEffort.HIGH))
    assert rec.target_model == "cheap"


def test_low_confidence_prefers_stronger_model_when_economic_model_has_no_margin(tmp_path):
    router = Router(policy(tmp_path))
    catalog = CatalogSnapshot((model("cheap"), model("strong")))
    rec = router.recommend(c(TaskPhase.DEFINED_IMPLEMENTATION, Confidence.LOW), catalog, RuntimeState("cheap", ReasoningEffort.LOW))
    assert rec.target_model == "strong"


def test_unknown_catalog_model_is_not_selected_without_profile(tmp_path):
    router = Router(policy(tmp_path))
    catalog = CatalogSnapshot((model("mystery"), model("strong")))
    rec = router.recommend(c(TaskPhase.COMPLEX_ENGINEERING), catalog, RuntimeState("strong", ReasoningEffort.HIGH))
    assert rec is not None
    assert rec.target_model == "strong"


def test_unsupported_preferred_effort_uses_nearest_lower_supported_effort(tmp_path):
    router = Router(policy(tmp_path))
    cheap = model("cheap", (ReasoningEffort.NONE, ReasoningEffort.LOW))
    rec = router.recommend(c(TaskPhase.DEFINED_IMPLEMENTATION), CatalogSnapshot((cheap,)), RuntimeState("strong", ReasoningEffort.HIGH))
    assert rec.target_effort is ReasoningEffort.LOW


def test_no_recommendation_when_current_pair_is_already_optimal(tmp_path):
    router = Router(policy(tmp_path))
    cheap = model("cheap")
    rec = router.recommend(c(TaskPhase.MECHANICAL), CatalogSnapshot((cheap,)), RuntimeState("cheap", ReasoningEffort.LOW))
    assert rec is None
