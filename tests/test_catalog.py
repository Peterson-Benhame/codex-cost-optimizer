from codex_cost_optimizer.catalog import CatalogProvider


class Obj:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class FakeCodex:
    def __init__(self, model_ids=("gpt-5.3-codex-spark",)):
        self.model_ids = model_ids
        self.calls = []

    def models(self, include_hidden=False):
        self.calls.append(include_hidden)
        data = []
        for model_id in self.model_ids:
            data.append(Obj(
                id=model_id,
                display_name=model_id,
                description="Fast coding model",
                supported_reasoning_efforts=[Obj(reasoning_effort="low"), Obj(reasoning_effort="medium")],
                default_reasoning_effort="low",
            ))
        return Obj(data=data)


def test_catalog_uses_only_models_returned_by_runtime():
    snapshot = CatalogProvider(FakeCodex()).load()
    assert snapshot.find("gpt-5.3-codex-spark") is not None
    assert snapshot.find("gpt-not-available") is None


def test_catalog_calls_runtime_without_hidden_models():
    fake = FakeCodex()
    CatalogProvider(fake).load()
    assert fake.calls == [False]


def test_spark_appears_only_when_runtime_returns_it():
    assert CatalogProvider(FakeCodex(("gpt-5.3-codex-spark",))).load().find("gpt-5.3-codex-spark")
    assert CatalogProvider(FakeCodex(("gpt-5.6-luna",))).load().find("gpt-5.3-codex-spark") is None


def test_catalog_accepts_official_effort_field_shape():
    class OfficialFake:
        def models(self, include_hidden=False):
            return Obj(data=[Obj(
                id="gpt-x",
                display_name="GPT X",
                description="x",
                supported_reasoning_efforts=[Obj(effort="low"), Obj(effort="high")],
                default_reasoning_effort="high",
            )])
    model = CatalogProvider(OfficialFake()).load().find("gpt-x")
    assert [effort.value for effort in model.supported_efforts] == ["low", "high"]
