from __future__ import annotations

from dataclasses import replace
from typing import Any

from .approval import ApprovalProvider
from .classifier import DeterministicClassifier
from .codex_runtime import ConfigurationApplyError
from .domain import ApprovalResult, PreparedTurn, RuntimeState, TaskMetadata
from .fallback_classifier import FallbackClassifier, RoutingSummary
from .materiality import MaterialityGate, RejectionRegistry
from .pricing import PricingRegistry
from .routing import ModelPolicy, Router
from .signals import SignalExtractor
from .telemetry import RoutingEvent, TelemetryStore, usage_fields


class CostOptimizerService:
    def __init__(self, *, extractor: SignalExtractor, classifier: DeterministicClassifier, router: Router, policy: ModelPolicy, materiality: MaterialityGate, rejection_registry: RejectionRegistry, approval_provider: ApprovalProvider, runtime: Any, fallback: FallbackClassifier | None = None, telemetry: TelemetryStore | None = None, pricing: PricingRegistry | None = None, enabled: bool = True):
        self.extractor=extractor; self.classifier=classifier; self.router=router; self.policy=policy
        self.materiality=materiality; self.rejections=rejection_registry; self.approval_provider=approval_provider
        self.runtime=runtime; self.fallback=fallback; self.telemetry=telemetry; self.pricing=pricing; self.enabled=enabled

    def prepare_turn(self, task_text: str, metadata: TaskMetadata, runtime_state: RuntimeState) -> PreparedTurn:
        if not self.enabled:
            signals=self.extractor.extract(task_text,metadata)
            classification=self.classifier.classify(signals)
            return PreparedTurn(task_text,metadata,runtime_state,signals,classification,None)
        try:
            catalog=self.runtime.list_models()
            signals=self.extractor.extract(task_text,metadata)
            classification=self.classifier.classify(signals)
            provisional=self.router.recommend(classification,catalog,runtime_state)
            material=self._is_material(provisional,metadata)
            if self.fallback is not None and classification.confidence.name == "LOW":
                summary=RoutingSummary(estimated_files=metadata.estimated_files,cross_module=metadata.cross_module,risk=metadata.risk,spec_available=metadata.spec_available,root_cause_known=metadata.root_cause_known,unexpected_error=metadata.unexpected_error,expected_work_units=metadata.expected_work_units)
                classification=self.fallback.classify(summary,classification,material_benefit=material,session_id=runtime_state.session_id)
                provisional=self.router.recommend(classification,catalog,runtime_state)
                material=self._is_material(provisional,metadata)
            rec=provisional if material else None
            if rec is not None and self.rejections.is_rejected(rec.phase_fingerprint):
                rec=None
            return PreparedTurn(task_text,metadata,runtime_state,signals,classification,rec)
        except Exception as exc:
            signals=self.extractor.extract(task_text,metadata)
            classification=self.classifier.classify(signals)
            if self.telemetry:
                self.telemetry.append(RoutingEvent(event_type="optimizer_fail_safe",session_id=runtime_state.session_id or "unknown",thread_id=runtime_state.thread_id,reason_code=exc.__class__.__name__))
            return PreparedTurn(task_text,metadata,runtime_state,signals,classification,None)

    def _is_material(self, rec, metadata: TaskMetadata) -> bool:
        if rec is None: return False
        current=self.policy.profile(rec.current_model); target=self.policy.profile(rec.target_model)
        if current is None or target is None: return True
        return self.materiality.should_propose(current_cost_rank=current.cost_rank,target_cost_rank=target.cost_rank,estimated_work_units=metadata.expected_work_units,context_replay_risk=metadata.context_replay_risk,high_rework_risk=False).propose

    def execute_turn(self, prepared: PreparedTurn, *, thread: Any) -> Any:
        rec=prepared.recommendation
        approval=prepared.approval
        if rec is not None and approval is None:
            approval=self.approval_provider.request(rec)
            prepared=prepared.with_approval(approval)
        if rec is not None and approval is not None and not approval.approved:
            self.rejections.reject(rec.phase_fingerprint)
            self._log_decision(prepared,approval,switch_confirmed=False)
            result=self.runtime.run_current_turn(thread,prepared.task_text)
            self._log_usage(prepared,result,prepared.runtime_state.current_model,prepared.runtime_state.current_effort.value)
            return result
        if rec is not None and approval is not None and approval.approved:
            try:
                result=self.runtime.run_turn(thread,prepared.task_text,model=rec.target_model,effort=rec.target_effort)
                self._log_decision(prepared,approval,switch_confirmed=True)
                self._log_usage(prepared,result,rec.target_model,rec.target_effort.value)
                return result
            except ConfigurationApplyError:
                self._log_decision(prepared,approval,switch_confirmed=False,reason_code="configuration_apply_failed")
                result=self.runtime.run_current_turn(thread,prepared.task_text)
                self._log_usage(prepared,result,prepared.runtime_state.current_model,prepared.runtime_state.current_effort.value)
                return result
        result=self.runtime.run_current_turn(thread,prepared.task_text)
        self._log_usage(prepared,result,prepared.runtime_state.current_model,prepared.runtime_state.current_effort.value)
        return result

    def _log_decision(self, prepared: PreparedTurn, approval: ApprovalResult, *, switch_confirmed: bool, reason_code: str | None=None) -> None:
        if not self.telemetry or not prepared.recommendation: return
        rec=prepared.recommendation; m=prepared.metadata; state=prepared.runtime_state
        self.telemetry.append(RoutingEvent(event_type="routing",session_id=state.session_id or "unknown",thread_id=state.thread_id,phase=prepared.classification.phase.value,confidence=prepared.classification.confidence.name.lower(),decision_source=("ai_fallback" if "ai fallback metadata classification" in prepared.classification.reasons else "local"),source_type=m.source_type,source_name=m.source_name,source_capability=m.source_capability,agent_name=m.agent_name,parent_agent_id=m.parent_agent_id,current_model=rec.current_model,current_effort=rec.current_effort.value,target_model=rec.target_model,target_effort=rec.target_effort.value,parent_model=m.parent_model,parent_effort=m.parent_effort.value if m.parent_effort else None,authorized=approval.approved,switch_confirmed=switch_confirmed,reason_code=reason_code,phase_fingerprint=rec.phase_fingerprint))

    def _log_usage(self, prepared: PreparedTurn, result: Any, actual_model: str, actual_effort: str) -> None:
        if not self.telemetry: return
        usage=self.runtime.read_usage(result); m=prepared.metadata; state=prepared.runtime_state
        cost_estimated=None; unit=None; parent_cost=None; savings=None; savings_pct=None; stale=None
        if self.pricing is not None:
            quote=self.pricing.quote(usage,actual_model); cost_estimated=quote.amount; unit=quote.unit; stale=quote.pricing_stale
            if m.parent_model and m.parent_model != actual_model:
                parent=self.pricing.estimate_parent_counterfactual(usage,m.parent_model); parent_cost=parent.amount
                if cost_estimated is not None and parent_cost is not None:
                    savings=parent_cost-cost_estimated
                    savings_pct=(savings/parent_cost*100) if parent_cost else None
                    stale=bool(stale or parent.pricing_stale)
        self.telemetry.append(RoutingEvent(event_type="turn_usage",session_id=state.session_id or "unknown",thread_id=state.thread_id,phase=prepared.classification.phase.value,source_type=m.source_type,source_name=m.source_name,source_capability=m.source_capability,agent_name=m.agent_name,parent_agent_id=m.parent_agent_id,parent_model=m.parent_model,parent_effort=m.parent_effort.value if m.parent_effort else None,actual_model=actual_model,actual_effort=actual_effort,cost_estimated=cost_estimated,cost_estimated_unit=unit,cost_if_parent_estimated=parent_cost,savings_estimated=savings,savings_percent_estimated=savings_pct,pricing_stale=stale,**usage_fields(usage)))
