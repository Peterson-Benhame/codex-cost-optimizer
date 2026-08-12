from __future__ import annotations

import hashlib
import json

from .domain import MaterialityDecision


def phase_fingerprint(phase: str, key_signals: dict[str, object]) -> str:
    payload = json.dumps({"phase": phase, "signals": key_signals}, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


class MaterialityGate:
    def should_propose(self, *, current_cost_rank: int, target_cost_rank: int, estimated_work_units: int, context_replay_risk: str, high_rework_risk: bool = False) -> MaterialityDecision:
        duration_material = estimated_work_units >= 5
        cost_gap_material = abs(current_cost_rank - target_cost_rank) >= 2
        replay_risk_acceptable = context_replay_risk != "high"
        conditions = sum((duration_material, cost_gap_material, replay_risk_acceptable))
        propose = conditions >= 2 and not high_rework_risk and current_cost_rank != target_cost_rank
        reasons = (
            f"duration_material={duration_material}",
            f"cost_gap_material={cost_gap_material}",
            f"replay_risk_acceptable={replay_risk_acceptable}",
        )
        return MaterialityDecision(propose=propose, reasons=reasons)


class RejectionRegistry:
    def __init__(self) -> None:
        self._rejected: set[str] = set()

    def reject(self, fingerprint: str) -> None:
        self._rejected.add(fingerprint)

    def is_rejected(self, fingerprint: str) -> bool:
        return fingerprint in self._rejected
