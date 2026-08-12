from codex_cost_optimizer.domain import Classification, Confidence, TaskPhase
from codex_cost_optimizer.fallback_classifier import FallbackClassifier, RoutingSummary


class Estimator:
    def __init__(self, value): self.value=value
    def estimate(self, payload): return self.value


class Client:
    def __init__(self): self.calls=[]
    def classify(self, *, payload, model, max_output_tokens, output_schema):
        self.calls.append((payload,model,max_output_tokens,output_schema))
        return {"phase":"complex_engineering","confidence":"high"}, {"input_tokens":200,"output_tokens":10}


def local_low():
    return Classification(TaskPhase.DEFINED_IMPLEMENTATION, Confidence.LOW, ("ambiguous",), 0)


def test_payload_over_budget_does_not_call_model():
    client=Client()
    fallback=FallbackClassifier(client=client, estimator=Estimator(1001), model_id="cheap")
    result=fallback.classify(RoutingSummary(estimated_files=4,cross_module=True,risk="high",spec_available=True,root_cause_known=True), local_low(), material_benefit=True)
    assert client.calls == []
    assert result == local_low()


def test_fallback_only_runs_for_low_confidence_and_material_benefit():
    client=Client(); fb=FallbackClassifier(client=client,estimator=Estimator(100),model_id="cheap")
    high=Classification(TaskPhase.DEFINED_IMPLEMENTATION,Confidence.HIGH,("clear",),0)
    assert fb.classify(RoutingSummary(), high, material_benefit=True) == high
    assert fb.classify(RoutingSummary(), local_low(), material_benefit=False) == local_low()
    assert client.calls == []


def test_output_schema_is_strict_and_output_budget_is_80():
    client=Client(); fb=FallbackClassifier(client=client,estimator=Estimator(100),model_id="cheap")
    result=fb.classify(RoutingSummary(estimated_files=8,cross_module=True,risk="high"), local_low(), material_benefit=True)
    _,_,max_output,schema=client.calls[0]
    assert max_output == 80
    assert schema["additionalProperties"] is False
    assert result.phase is TaskPhase.COMPLEX_ENGINEERING
    assert result.confidence is Confidence.HIGH


def test_select_fallback_model_prefers_known_priced_cheapest_available(tmp_path):
    import json
    from codex_cost_optimizer.catalog import CatalogSnapshot
    from codex_cost_optimizer.domain import ModelDescriptor, ReasoningEffort
    from codex_cost_optimizer.routing import ModelPolicy
    from codex_cost_optimizer.fallback_classifier import select_fallback_model
    p=tmp_path/"p.json"
    p.write_text(json.dumps({"profiles":{
        "spark":{"capability_rank":2,"cost_rank":1,"preferred_for":[],"pricing_status":"research_preview"},
        "mini":{"capability_rank":2,"cost_rank":1,"preferred_for":[]}
    }}))
    policy=ModelPolicy.from_file(p)
    models=(
        ModelDescriptor("spark","spark","",(ReasoningEffort.LOW,),ReasoningEffort.LOW),
        ModelDescriptor("mini","mini","",(ReasoningEffort.LOW,),ReasoningEffort.LOW),
    )
    assert select_fallback_model(CatalogSnapshot(models),policy) == ("mini",ReasoningEffort.LOW)


def test_codex_classifier_client_uses_ephemeral_structured_turn():
    from codex_cost_optimizer.catalog import CatalogSnapshot
    from codex_cost_optimizer.codex_runtime import CodexRuntime
    from codex_cost_optimizer.domain import ModelDescriptor, ReasoningEffort
    from codex_cost_optimizer.fallback_classifier import CodexClassifierClient, OUTPUT_SCHEMA
    class Result:
        final_response='{"phase":"mechanical","confidence":"high"}'
        usage=type("U",(),{"input_tokens":40,"cached_input_tokens":0,"output_tokens":8})()
    class Thread:
        def __init__(self): self.calls=[]
        def run(self,text,**kwargs): self.calls.append((text,kwargs)); return Result()
    class Codex:
        def __init__(self): self.starts=[]; self.thread=Thread()
        def thread_start(self,**kwargs): self.starts.append(kwargs); return self.thread
    descriptor=ModelDescriptor("mini","mini","",(ReasoningEffort.LOW,),ReasoningEffort.LOW)
    codex=Codex(); runtime=CodexRuntime(codex=None,catalog_snapshot=CatalogSnapshot((descriptor,)))
    client=CodexClassifierClient(codex=codex,runtime=runtime,effort=ReasoningEffort.LOW)
    raw,usage=client.classify(payload='{"risk":"low"}',model="mini",max_output_tokens=80,output_schema=OUTPUT_SCHEMA)
    assert codex.starts[0]["ephemeral"] is True
    assert codex.thread.calls[0][1]["model"] == "mini"
    assert codex.thread.calls[0][1]["output_schema"] == OUTPUT_SCHEMA
    assert raw["phase"] == "mechanical"
    assert usage["output_tokens"] == 8
