"""
Abstract agent adapter for Agent Eval.

Defines the interface for agent adapters, allowing different
AI coding agents to be tested with the same framework.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Dict, Any
from enum import Enum


class AgentType(Enum):
    """Supported agent types."""

    CLAUDE = "claude"
    OPENAI = "openai"
    CUSTOM = "custom"
    MOCK = "mock"  # For testing


@dataclass
class AgentResponse:
    """Response from an agent execution.

    Contains the agent's output, exit code, and optional metadata
    about token usage and cost.

    Attributes:
        output: The agent's text output
        exit_code: Process exit code (0 = success)
        tokens_input: Input tokens used (if tracked)
        tokens_output: Output tokens generated (if tracked)
        cost_usd: Cost in USD (if tracked)
        duration_seconds: How long the execution took
        error: Error message if execution failed
        metadata: Additional adapter-specific data
    """

    output: str
    exit_code: int
    tokens_input: Optional[int] = None
    tokens_output: Optional[int] = None
    cost_usd: Optional[float] = None
    duration_seconds: float = 0.0
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def success(self) -> bool:
        """Check if execution was successful."""
        return self.exit_code == 0 and self.error is None

    def __str__(self) -> str:
        status = "OK" if self.success else f"FAIL (exit={self.exit_code})"
        duration = f"{self.duration_seconds:.1f}s"
        return f"AgentResponse({status}, {duration}, {len(self.output)} chars)"


class AgentAdapter(ABC):
    """Abstract base class for agent adapters.

    Implement this interface to support different AI coding agents.
    The adapter handles:
    - Executing prompts in a working directory
    - Handling timeouts
    - Collecting output and metrics

    Concrete implementations:
    - ClaudeAdapter: For Claude Code CLI
    - OpenAIAdapter: For GPT-based agents (future)
    - MockAdapter: For testing

    Example implementation:
        class MyAdapter(AgentAdapter):
            def execute(self, prompt, workdir, timeout):
                result = my_agent.run(prompt, cwd=workdir)
                return AgentResponse(
                    output=result.text,
                    exit_code=result.code,
                    duration_seconds=result.time,
                )
    """

    @abstractmethod
    def execute(
        self,
        prompt: str,
        workdir: Path,
        timeout: int,
    ) -> AgentResponse:
        """Execute a prompt and return the response.

        Args:
            prompt: The task/prompt to give the agent
            workdir: Working directory for the agent
            timeout: Maximum time in seconds

        Returns:
            AgentResponse with output and metadata

        Raises:
            ExecutionError: If execution fails
            TimeoutError: If execution times out
        """
        pass

    @property
    def agent_type(self) -> AgentType:
        """Return the type of agent this adapter supports."""
        return AgentType.CUSTOM

    def validate_environment(self) -> bool:
        """Check if the agent's prerequisites are met.

        Override to add checks like:
        - Is the CLI installed?
        - Are API keys configured?
        - Are dependencies available?

        Returns:
            True if environment is valid
        """
        return True


class MockAdapter(AgentAdapter):
    """Mock adapter for testing.

    Returns configurable responses without actually running an agent.
    """

    def __init__(
        self,
        response_output: str = "Mock response",
        response_exit_code: int = 0,
        response_duration: float = 1.0,
        should_timeout: bool = False,
        should_error: bool = False,
        error_message: str = "Mock error",
    ):
        """Initialize mock adapter.

        Args:
            response_output: Output to return
            response_exit_code: Exit code to return
            response_duration: Duration to report
            should_timeout: If True, raise TimeoutError
            should_error: If True, raise ExecutionError
            error_message: Error message to use
        """
        self.response_output = response_output
        self.response_exit_code = response_exit_code
        self.response_duration = response_duration
        self.should_timeout = should_timeout
        self.should_error = should_error
        self.error_message = error_message

        # Track calls for assertions
        self.calls: list = []

    def execute(
        self,
        prompt: str,
        workdir: Path,
        timeout: int,
    ) -> AgentResponse:
        """Execute mock request."""
        from ..exceptions import TimeoutError, ExecutionError

        # Record the call
        self.calls.append({
            "prompt": prompt,
            "workdir": str(workdir),
            "timeout": timeout,
        })

        if self.should_timeout:
            raise TimeoutError(f"Mock timeout after {timeout}s")

        if self.should_error:
            raise ExecutionError(self.error_message)

        return AgentResponse(
            output=self.response_output,
            exit_code=self.response_exit_code,
            duration_seconds=self.response_duration,
        )

    @property
    def agent_type(self) -> AgentType:
        return AgentType.MOCK

    @property
    def call_count(self) -> int:
        """Number of times execute was called."""
        return len(self.calls)

    @property
    def last_call(self) -> Optional[Dict[str, Any]]:
        """Get the last call arguments."""
        return self.calls[-1] if self.calls else None
