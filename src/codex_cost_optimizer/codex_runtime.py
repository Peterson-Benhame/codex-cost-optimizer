from __future__ import annotations

from typing import Any

from .catalog import CatalogProvider, CatalogSnapshot
from .domain import ReasoningEffort, TokenUsage


class UnsupportedConfiguration(ValueError):
    pass


class ConfigurationApplyError(RuntimeError):
    pass


class RuntimeStateUnavailable(RuntimeError):
    pass


class CodexRuntime:
    """Thin adapter over the official OpenAI Codex Python SDK."""

    def __init__(self, codex: Any, catalog_snapshot: CatalogSnapshot | None = None):
        self.codex = codex
        self._catalog = catalog_snapshot

    def list_models(self, *, refresh: bool = False) -> CatalogSnapshot:
        if self._catalog is None or refresh:
            if self.codex is None:
                raise RuntimeError("Codex SDK instance is required to load the runtime catalog")
            self._catalog = CatalogProvider(self.codex).load(refresh=refresh)
        return self._catalog

    def start_thread(self, **kwargs: Any) -> Any:
        if self.codex is None:
            raise RuntimeError("Codex SDK instance is required to start a thread")
        return self.codex.thread_start(**kwargs)

    def run_turn(self, thread: Any, prompt: str, *, model: str, effort: ReasoningEffort) -> Any:
        descriptor = self.list_models().find(model)
        if descriptor is None:
            raise UnsupportedConfiguration(f"model {model!r} is not available in the runtime catalog")
        if not descriptor.supports(effort):
            raise UnsupportedConfiguration(f"{model!r} does not advertise reasoning effort {effort.value!r}")
        try:
            return thread.run(prompt, model=model, effort=self._to_sdk_effort(effort))
        except Exception as exc:
            if exc.__class__.__name__ in {"InvalidParamsError", "MethodNotFoundError"}:
                raise ConfigurationApplyError(str(exc)) from exc
            raise

    @staticmethod
    def run_current_turn(thread: Any, prompt: str) -> Any:
        return thread.run(prompt)

    @staticmethod
    def read_state(thread: Any) -> tuple[str, ReasoningEffort]:
        response = thread.read(include_turns=False)
        root = getattr(response, "thread", response)
        model = getattr(response, "model", None) or getattr(root, "model", None)
        effort = getattr(response, "reasoning_effort", None) or getattr(root, "reasoning_effort", None)
        if model is None or effort is None:
            raise RuntimeStateUnavailable("current model/reasoning are not exposed by this thread read response")
        value = getattr(effort, "value", effort)
        return str(model), ReasoningEffort(str(value))

    @staticmethod
    def _to_sdk_effort(effort: ReasoningEffort) -> Any:
        try:
            from openai_codex.types import ReasoningEffort as SDKReasoningEffort
            return SDKReasoningEffort(effort.value)
        except (ImportError, ValueError, TypeError):
            return effort.value

    @staticmethod
    def read_usage(result: Any) -> TokenUsage:
        usage = getattr(result, "usage", None)
        if usage is None:
            return TokenUsage.empty()
        input_tokens = getattr(usage, "input_tokens", None)
        cached = getattr(usage, "cached_input_tokens", None)
        output = getattr(usage, "output_tokens", None)
        reasoning = getattr(usage, "reasoning_output_tokens", None)
        total = getattr(usage, "total_tokens", None)
        if total is None and input_tokens is not None and output is not None:
            total = input_tokens + output
        return TokenUsage(
            input_tokens=input_tokens,
            cached_input_tokens=cached,
            output_tokens=output,
            reasoning_tokens=reasoning,
            total_tokens=total,
        )
