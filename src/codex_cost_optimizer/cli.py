from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

import typer

from .approval import TerminalApprovalProvider
from .classifier import DeterministicClassifier
from .codex_runtime import CodexRuntime, RuntimeStateUnavailable
from .domain import ManualSwitchRequired, ReasoningEffort, RuntimeState, TaskMetadata
from .fallback_classifier import CodexClassifierClient, FallbackClassifier, select_fallback_model
from .materiality import MaterialityGate, RejectionRegistry
from .pricing import PricingRegistry
from .routing import ModelPolicy, Router
from .service import CostOptimizerService
from .signals import SignalExtractor
from .telemetry import TelemetryStore, default_telemetry_path

app = typer.Typer(help="Codex Cost Optimizer — local, approval-gated model routing.", no_args_is_help=True)


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def policy_path() -> Path:
    return project_root() / "references" / "model-policy.json"


def _sdk():
    try:
        from openai_codex import Codex
    except ImportError as exc:
        raise typer.BadParameter("openai-codex não está instalado. Execute: pip install -e '.[codex]'") from exc
    return Codex


def _service(codex, telemetry: TelemetryStore, *, enabled: bool = True) -> tuple[CostOptimizerService, CodexRuntime]:
    policy=ModelPolicy.from_file(policy_path())
    pricing=PricingRegistry.from_file(policy_path())
    runtime=CodexRuntime(codex)
    fallback=None
    selected=select_fallback_model(runtime.list_models(),policy)
    if selected is not None:
        fallback_model,fallback_effort=selected
        fallback=FallbackClassifier(client=CodexClassifierClient(codex=codex,runtime=runtime,effort=fallback_effort),model_id=fallback_model,telemetry=telemetry,pricing=pricing)
    service=CostOptimizerService(
        extractor=SignalExtractor(), classifier=DeterministicClassifier(), router=Router(policy), policy=policy,
        materiality=MaterialityGate(), rejection_registry=RejectionRegistry(), approval_provider=TerminalApprovalProvider(),
        runtime=runtime, telemetry=telemetry, pricing=pricing, fallback=fallback, enabled=enabled,
    )
    return service,runtime


@app.command()
def inspect(thread_id: Optional[str] = typer.Option(None, help="Thread existente para consultar model/reasoning atuais.")) -> None:
    """Mostra catálogo real, estado da thread quando disponível e telemetria local."""
    Codex=_sdk()
    with Codex() as codex:
        runtime=CodexRuntime(codex)
        snapshot=runtime.list_models()
        typer.echo(f"telemetry={default_telemetry_path()}")
        if thread_id:
            thread=codex.thread_resume(thread_id)
            try:
                model,effort=runtime.read_state(thread)
                typer.echo(f"current_model={model}")
                typer.echo(f"current_effort={effort.value}")
            except RuntimeStateUnavailable:
                typer.echo("current_model=unavailable")
                typer.echo("current_effort=unavailable")
        else:
            typer.echo("current_model=unavailable (informe --thread-id para introspecção)")
            typer.echo("current_effort=unavailable")
        for model in snapshot.models:
            typer.echo(f"{model.id}: {','.join(e.value for e in model.supported_efforts)}")


@app.command()
def run(
    prompt: str = typer.Argument("-", help="Prompt ou '-' para stdin; nunca é persistido na telemetria."),
    model: Optional[str] = typer.Option(None, help="Modelo atual/inicial quando uma nova thread for criada."),
    effort: Optional[ReasoningEffort] = typer.Option(None, help="Reasoning atual/inicial."),
    thread_id: Optional[str] = typer.Option(None, help="Thread Codex existente."),
    spec: bool = typer.Option(False, help="Há SPEC aprovada."),
    root_cause_known: Optional[bool] = typer.Option(None, "--root-cause-known/--root-cause-unknown"),
    files: int = typer.Option(1, min=0),
    cross_module: bool = typer.Option(False),
    unexpected_error: bool = typer.Option(False),
    risk: str = typer.Option("medium"),
    work_units: int = typer.Option(5, min=0),
    disable_optimizer: bool = typer.Option(False, "--disable-optimizer", help="Executa com a configuração atual, sem recomendações/trocas."),
) -> None:
    """Executa um turno usando roteamento local e autorização explícita."""
    text=sys.stdin.read() if prompt == "-" else prompt
    if not text.strip():
        raise typer.BadParameter("prompt vazio")
    Codex=_sdk(); telemetry=TelemetryStore()
    with Codex() as codex:
        service,runtime=_service(codex,telemetry,enabled=not disable_optimizer)
        if thread_id:
            thread=codex.thread_resume(thread_id)
            try:
                current_model,current_effort=runtime.read_state(thread)
            except RuntimeStateUnavailable as exc:
                raise typer.BadParameter("a thread não expõe model/reasoning; forneça uma nova thread com --model e --effort") from exc
        else:
            if model is None or effort is None:
                raise typer.BadParameter("na V1 Core, uma nova thread exige --model e --effort")
            current_model,current_effort=model,effort
            thread=codex.thread_start(model=model, config={"model_reasoning_effort": effort.value})
        state=RuntimeState(current_model,current_effort,session_id=getattr(thread,"id","session"),thread_id=getattr(thread,"id",None))
        meta=TaskMetadata(spec_available=spec,root_cause_known=root_cause_known,estimated_files=files,cross_module=cross_module,unexpected_error=unexpected_error,risk=risk,expected_work_units=work_units)
        prepared=service.prepare_turn(text,meta,state)
        result=service.execute_turn(prepared,thread=thread)
        if isinstance(result, ManualSwitchRequired):
            typer.echo("manual_switch_required=true")
            typer.echo(f"target_model={result.target_model}")
            typer.echo(f"target_effort={result.target_effort.value}")
            typer.echo(f"reason={result.reason}")
            typer.echo(f"cost_impact={result.cost_impact}")
            typer.echo("action=altere model/reasoning no seletor nativo do Codex e confirme o estado antes de continuar")
            return
        if getattr(result,"final_response",None): typer.echo(result.final_response)


@app.command()
def report(session_id: str = typer.Argument(..., help="ID da sessão/thread usado na telemetria.")) -> None:
    """Resume consumo medido e economia contrafactual explicitamente estimada."""
    summary=TelemetryStore().session_summary(session_id)
    measured_cost=summary["actual_cost"]
    estimated_cost=summary["cost_estimated"]
    overhead_measured=summary["router_actual_cost"]
    overhead_estimated=summary["router_cost_estimated"]
    if measured_cost and overhead_measured:
        ratio=overhead_measured/measured_cost*100
        ratio_label="measured"
    elif estimated_cost and overhead_estimated:
        ratio=overhead_estimated/estimated_cost*100
        ratio_label="estimated"
    else:
        ratio=None; ratio_label="unavailable"
    typer.echo(f"events={summary['events']}")
    typer.echo(f"input_tokens={summary['input_tokens']}")
    typer.echo(f"cached_input_tokens={summary['cached_input_tokens']}")
    typer.echo(f"output_tokens={summary['output_tokens']}")
    typer.echo(f"local_decisions={summary['local_decisions']}")
    typer.echo(f"ai_decisions={summary['ai_decisions']}")
    typer.echo(f"actual_cost={summary['actual_cost']:.6f} credits (somente se reportado pelo runtime)")
    typer.echo(f"estimated_cost={summary['cost_estimated']:.6f} credits (calculado por usage × rate card)")
    typer.echo(f"estimated_savings={summary['savings_estimated']:.6f} credits (contrafactual estimado)")
    typer.echo("router_overhead_ratio=unavailable" if ratio is None else f"router_overhead_ratio={ratio:.3f}% ({ratio_label})")


if __name__ == "__main__":
    app()
