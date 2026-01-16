"""
Evaluation layer for Agent Eval.

Handles:
- Deterministic verification (command + file checks)
- LLM watchdog evaluation (qualitative feedback)
- Metrics collection
"""

from .verifier import Verifier, QuickVerifier
from .watchdog import Watchdog, MockWatchdog
from .metrics_collector import MetricsCollector, MetricsAggregator

__all__ = [
    # Verifier
    "Verifier",
    "QuickVerifier",
    # Watchdog
    "Watchdog",
    "MockWatchdog",
    # Metrics
    "MetricsCollector",
    "MetricsAggregator",
]
