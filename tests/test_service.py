from pathlib import Path

from codex_cost_optimizer.catalog import CatalogSnapshot
from codex_cost_optimizer.classifier import DeterministicClassifier
from codex_cost_optimizer.codex_runtime import ConfigurationApplyError
from codex_cost_optimizer.domain import ModelDescriptor, ReasoningEffort, RuntimeState, TaskMetadata
from codex_cost_optimizer.fallback_classifier import FallbackClassifier
from codex_cost_optimizer.materiality import MaterialityGate, RejectionRegistry
from codex_cost_optimizer.routing import ModelPolicy, Router
from codex_cost_optimizer.service import CostOptimizerService
from codex_cost_optimizer.signals import SignalExtractor


POLICY = Path(__file__).parents[1] / "references" / "model-policy.json"


def md(mid, efforts=(ReasoningEffort.LOW, ReasoningEffort.MEDIUM, ReasoningEffort.HIGH)):
    return ModelDescriptor(mid, mid, "", efforts, ReasoningEffort.MEDIUM if ReasoningEffort.MEDIUM in efforts else efforts[0])


def catalog(*ids):
    return CatalogSnapshot(tuple(md(i) for i in ids))


class FakeResult:
    id="turn-1"
    usage=type("U",(),{"input_tokens":100,"cached_input_tokens":20,"output_tokens":10})()
    final_response="ok"


class FakeRuntime:
    def __init__(self, snapshot, fail_switch=False):
        self.snapshot=snapshot; self.fail_switch=fail_switch; self.calls=[]
    def list_models(self, refresh=False): return self.snapshot
    def run_turn(self, thread, prompt, *, model, effort):
        self.calls.append(("override",model,effort.value))
        if self.fail_switch: raise ConfigurationApplyError("cannot apply")
        return FakeResult()
    def run_current_turn(self, thread, prompt):
        self.calls.append(("current",None,None)); return FakeResult()
    def read_usage(self, result):
        from codex_cost_optimizer.codex_runtime import CodexRuntime
        return CodexRuntime.read_usage(result)


class Approval:
    def __init__(self, yes): self.yes=yes; self.calls=0
    def request(self, rec):
        from codex_cost_optimizer.domain import ApprovalResult
        self.calls += 1
        return ApprovalResult(self.yes, "sim" if self.yes else "não")


class Estimator:
    def estimate(self,payload): return 100
class FallbackClient:
    def __init__(self): self.calls=[]
    def classify(self, **kwargs):
        self.calls.append(kwargs)
        return {"phase":"defined_implementation","confidence":"high"},{"input_tokens":50,"output_tokens":4}


def make_service(runtime, approval, fallback=None):
    policy=ModelPolicy.from_file(POLICY)
    return CostOptimizerService(
        extractor=SignalExtractor(), classifier=DeterministicClassifier(), router=Router(policy), policy=policy,
        materiality=MaterialityGate(), rejection_registry=RejectionRegistry(), approval_provider=approval,
        runtime=runtime, fallback=fallback,
    )


def test_scenario_a_trivial_task_on_sol_recommends_economic_model_and_requires_approval():
    rt=FakeRuntime(catalog("gpt-5.6-sol","gpt-5.3-codex-spark","gpt-5.4-mini")); ap=Approval(True); svc=make_service(rt,ap)
    state=RuntimeState("gpt-5.6-sol",ReasoningEffort.HIGH,"s","t")
    prepared=svc.prepare_turn("Adicione comentários XML",TaskMetadata(risk="low",estimated_files=1,expected_work_units=2),state)
    assert prepared.recommendation.target_model == "gpt-5.3-codex-spark"
    svc.execute_turn(prepared,thread=object())
    assert ap.calls == 1
    assert rt.calls[0] == ("override","gpt-5.3-codex-spark","low")


def test_scenario_b_unknown_root_high_risk_escalates_from_economic_model():
    rt=FakeRuntime(catalog("gpt-5.4-mini","gpt-5.6-sol")); svc=make_service(rt,Approval(True))
    p=svc.prepare_turn("Descubra por que o fluxo quebra",TaskMetadata(root_cause_known=False,cross_module=True,unexpected_error=True,risk="high",estimated_files=10,expected_work_units=20),RuntimeState("gpt-5.4-mini",ReasoningEffort.LOW))
    assert p.recommendation.target_model == "gpt-5.6-sol"
    assert "Aumento esperado" in p.recommendation.cost_impact


def test_scenario_c_denial_keeps_current_and_suppresses_same_phase():
    rt=FakeRuntime(catalog("gpt-5.6-sol","gpt-5.4-mini")); ap=Approval(False); svc=make_service(rt,ap)
    state=RuntimeState("gpt-5.6-sol",ReasoningEffort.HIGH)
    meta=TaskMetadata(risk="low",estimated_files=1,expected_work_units=2)
    p=svc.prepare_turn("Adicione XML comments",meta,state); assert p.recommendation
    svc.execute_turn(p,thread=object())
    assert rt.calls[-1][0] == "current"
    assert svc.prepare_turn("Adicione XML comments",meta,state).recommendation is None


def test_scenario_d_authorized_but_unconfirmed_switch_falls_back_to_current_without_global_change():
    rt=FakeRuntime(catalog("gpt-5.6-sol","gpt-5.4-mini"),fail_switch=True); svc=make_service(rt,Approval(True))
    p=svc.prepare_turn("Adicione XML comments",TaskMetadata(risk="low",estimated_files=1,expected_work_units=2),RuntimeState("gpt-5.6-sol",ReasoningEffort.HIGH))
    svc.execute_turn(p,thread=object())
    assert [c[0] for c in rt.calls] == ["override","current"]


def test_scenario_e_spark_participates_only_when_available():
    rt=FakeRuntime(catalog("gpt-5.6-sol","gpt-5.3-codex-spark","gpt-5.4-mini")); svc=make_service(rt,Approval(True))
    p=svc.prepare_turn("Formate documentação",TaskMetadata(risk="low",expected_work_units=10),RuntimeState("gpt-5.6-sol",ReasoningEffort.HIGH))
    assert p.recommendation.target_model == "gpt-5.3-codex-spark"


def test_scenario_f_without_spark_recalculates_one_recommendation_from_real_catalog():
    rt=FakeRuntime(catalog("gpt-5.6-sol","gpt-5.4-mini")); svc=make_service(rt,Approval(True))
    p=svc.prepare_turn("Formate documentação",TaskMetadata(risk="low",expected_work_units=10),RuntimeState("gpt-5.6-sol",ReasoningEffort.HIGH))
    assert p.recommendation.target_model == "gpt-5.4-mini"


def test_scenario_j_ambiguous_material_work_calls_bounded_fallback():
    client=FallbackClient(); fb=FallbackClassifier(client=client,estimator=Estimator(),model_id="gpt-5.4-mini")
    rt=FakeRuntime(catalog("gpt-5.4","gpt-5.3-codex","gpt-5.4-mini","gpt-5.6-sol")); svc=make_service(rt,Approval(True),fb)
    meta=TaskMetadata(spec_available=True,root_cause_known=True,cross_module=True,risk="high",estimated_files=4,expected_work_units=20)
    p=svc.prepare_turn("Investigue e implemente a SPEC",meta,RuntimeState("gpt-5.4",ReasoningEffort.HIGH))
    assert len(client.calls) == 1
    assert p.classification.confidence.name == "HIGH"


def test_scenario_k_ambiguous_short_work_does_not_call_ai():
    client=FallbackClient(); fb=FallbackClassifier(client=client,estimator=Estimator(),model_id="gpt-5.4-mini")
    rt=FakeRuntime(catalog("gpt-5.4","gpt-5.3-codex","gpt-5.4-mini","gpt-5.6-sol")); svc=make_service(rt,Approval(True),fb)
    meta=TaskMetadata(spec_available=True,root_cause_known=True,cross_module=True,risk="high",estimated_files=4,expected_work_units=1,context_replay_risk="medium")
    svc.prepare_turn("Investigue e implemente a SPEC",meta,RuntimeState("gpt-5.4",ReasoningEffort.HIGH))
    assert client.calls == []


def test_optimizer_can_be_disabled_without_changing_current_execution():
    rt=FakeRuntime(catalog("gpt-5.6-sol","gpt-5.4-mini")); ap=Approval(True)
    policy=ModelPolicy.from_file(POLICY)
    svc=CostOptimizerService(extractor=SignalExtractor(),classifier=DeterministicClassifier(),router=Router(policy),policy=policy,materiality=MaterialityGate(),rejection_registry=RejectionRegistry(),approval_provider=ap,runtime=rt,enabled=False)
    p=svc.prepare_turn("Adicione XML comments",TaskMetadata(risk="low",expected_work_units=20),RuntimeState("gpt-5.6-sol",ReasoningEffort.HIGH))
    assert p.recommendation is None
    svc.execute_turn(p,thread=object())
    assert ap.calls == 0
    assert rt.calls == [("current",None,None)]
