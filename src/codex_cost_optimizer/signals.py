from __future__ import annotations

import re

from .domain import TaskMetadata, TaskSignals


class SignalExtractor:
    """Extracts zero-token signals. Metadata is authoritative; text adds weak hints only."""

    _mechanical = re.compile(r"\b(coment|format|rename|renome|xml|document|busc|localiz|teste[s]? trivial|boilerplate)\w*\b", re.I)
    _investigation = re.compile(r"\b(investig|descubr|causa raiz|root cause|por que|debug|diagnostic)\w*\b", re.I)
    _implementation = re.compile(r"\b(implement|corrij|corre[cç][aã]o|spec|crud|adicion)\w*\b", re.I)
    _review = re.compile(r"\b(review|revis|valid|audit)\w*\b", re.I)

    def extract(self, task_text: str, metadata: TaskMetadata) -> TaskSignals:
        text = task_text or ""
        return TaskSignals(
            spec_available=metadata.spec_available,
            root_cause_known=metadata.root_cause_known,
            estimated_files=metadata.estimated_files,
            cross_module=metadata.cross_module,
            unexpected_error=metadata.unexpected_error,
            risk=metadata.risk,
            expected_work_units=metadata.expected_work_units,
            context_replay_risk=metadata.context_replay_risk,
            mechanical_hint=bool(self._mechanical.search(text)),
            investigation_hint=bool(self._investigation.search(text)),
            implementation_hint=bool(self._implementation.search(text)),
            review_hint=bool(self._review.search(text)),
        )
