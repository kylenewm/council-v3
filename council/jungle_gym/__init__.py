"""
Jungle Gym: E2E Adversarial Test Harness for Council-v3

Tests the enforcement system by running scenarios against
control (no enforcement) vs experimental (full enforcement) agents.
"""

from .config import JungleGymConfig, AgentConfig
from .scenarios import Scenario, TIER_1_SCENARIOS, TIER_2_SCENARIOS, TIER_3_SCENARIOS
from .collector import ResultCollector, AgentResult
from .reporter import Reporter
from .harness import JungleGymHarness

__all__ = [
    "JungleGymConfig",
    "AgentConfig",
    "Scenario",
    "TIER_1_SCENARIOS",
    "TIER_2_SCENARIOS",
    "TIER_3_SCENARIOS",
    "ResultCollector",
    "AgentResult",
    "Reporter",
    "JungleGymHarness",
]
