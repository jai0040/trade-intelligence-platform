"""Signal engine exports."""

from signal_engine.confidence import CONFIDENCE_LABEL, compute_composite_confidence
from signal_engine.outcome_tracker import (
    METHODOLOGY_VERSION,
    compute_signal_outcome,
    summarize_performance,
)

__all__ = [
    "CONFIDENCE_LABEL",
    "METHODOLOGY_VERSION",
    "compute_composite_confidence",
    "compute_signal_outcome",
    "summarize_performance",
]
