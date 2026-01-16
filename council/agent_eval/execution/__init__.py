"""
Execution layer for Agent Eval.

Handles:
- Environment setup (isolated temp directories)
- Agent execution (via adapters)
- Timeout management
- Retry logic
"""

from .environment import Environment, EnvironmentFactory
from .timeout_manager import TimeoutManager
from .retry_manager import RetryManager, RetryContext
from .agent_adapter import AgentAdapter, AgentResponse, AgentType, MockAdapter
from .claude_adapter import ClaudeAdapter, ClaudeAdapterWithMCP

__all__ = [
    # Environment
    "Environment",
    "EnvironmentFactory",
    # Timeout
    "TimeoutManager",
    # Retry
    "RetryManager",
    "RetryContext",
    # Adapters
    "AgentAdapter",
    "AgentResponse",
    "AgentType",
    "MockAdapter",
    "ClaudeAdapter",
    "ClaudeAdapterWithMCP",
]
