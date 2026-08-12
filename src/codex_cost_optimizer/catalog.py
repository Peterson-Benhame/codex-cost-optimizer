from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from .domain import ModelDescriptor, ReasoningEffort


@dataclass(frozen=True)
class CatalogSnapshot:
    models: tuple[ModelDescriptor, ...]

    def find(self, model_id: str) -> ModelDescriptor | None:
        return next((model for model in self.models if model.id == model_id), None)

    def ids(self) -> tuple[str, ...]:
        return tuple(model.id for model in self.models)


class CatalogProvider:
    """Loads the real model catalog exposed by the current Codex runtime."""

    def __init__(self, codex: Any):
        self._codex = codex
        self._cached: CatalogSnapshot | None = None

    def load(self, *, refresh: bool = False) -> CatalogSnapshot:
        if self._cached is not None and not refresh:
            return self._cached
        response = self._codex.models(include_hidden=False)
        raw_models = getattr(response, "data", None)
        if raw_models is None:
            raw_models = getattr(response, "models", response)
        mapped = tuple(self._map_model(item) for item in raw_models)
        self._cached = CatalogSnapshot(mapped)
        return self._cached

    @staticmethod
    def _map_model(raw: Any) -> ModelDescriptor:
        model_id = str(getattr(raw, "id", "")).strip()
        if not model_id:
            raise ValueError("Codex runtime returned a model with empty id")
        raw_efforts: Iterable[Any] = getattr(raw, "supported_reasoning_efforts", ())
        efforts: list[ReasoningEffort] = []
        for item in raw_efforts:
            value = getattr(item, "reasoning_effort", None) or getattr(item, "effort", None) or item
            efforts.append(ReasoningEffort(str(value)))
        if not efforts:
            default_raw = getattr(raw, "default_reasoning_effort", "medium")
            efforts = [ReasoningEffort(str(default_raw))]
        default = ReasoningEffort(str(getattr(raw, "default_reasoning_effort", efforts[0].value)))
        if default not in efforts:
            efforts.append(default)
        return ModelDescriptor(
            id=model_id,
            display_name=str(getattr(raw, "display_name", model_id)),
            description=str(getattr(raw, "description", "")),
            supported_efforts=tuple(efforts),
            default_effort=default,
        )
