"""
Claude Code CLI adapter for Agent Eval.

Executes prompts using the Claude Code CLI tool.
"""

import subprocess
import time
import shutil
from pathlib import Path
from typing import Optional, List
import logging

from .agent_adapter import AgentAdapter, AgentResponse, AgentType
from ..config import AgentConfig
from ..exceptions import ExecutionError, TimeoutError

logger = logging.getLogger(__name__)


class ClaudeAdapter(AgentAdapter):
    """Adapter for Claude Code CLI.

    Executes prompts using the `claude` command line tool.
    Supports both interactive and print modes.

    Prerequisites:
    - Claude Code CLI must be installed (`claude` in PATH)
    - Valid authentication configured

    Usage:
        adapter = ClaudeAdapter(config)
        response = adapter.execute(
            "Fix the type error in main.ts",
            Path("/path/to/project"),
            timeout=300
        )
    """

    def __init__(self, config: AgentConfig):
        """Initialize Claude adapter.

        Args:
            config: Agent configuration with timeout and retry settings
        """
        self.config = config
        self._claude_path: Optional[str] = None

    def execute(
        self,
        prompt: str,
        workdir: Path,
        timeout: int,
    ) -> AgentResponse:
        """Execute prompt using Claude Code CLI.

        Args:
            prompt: The task/prompt for Claude
            workdir: Working directory for execution
            timeout: Maximum time in seconds

        Returns:
            AgentResponse with Claude's output

        Raises:
            ExecutionError: If Claude CLI fails
            TimeoutError: If execution exceeds timeout
        """
        start_time = time.time()

        try:
            # Build command
            # --print flag outputs result without interactive mode
            # -p passes the prompt
            cmd = [
                self._get_claude_path(),
                "--print",
                "-p",
                prompt,
            ]

            logger.debug(f"Executing Claude in {workdir}: {prompt[:100]}...")

            result = subprocess.run(
                cmd,
                cwd=workdir,
                capture_output=True,
                text=True,
                timeout=timeout,
            )

            duration = time.time() - start_time

            # Parse output
            output = result.stdout
            error = result.stderr if result.returncode != 0 else None

            logger.debug(
                f"Claude execution complete: exit={result.returncode}, "
                f"output={len(output)} chars, duration={duration:.1f}s"
            )

            return AgentResponse(
                output=output,
                exit_code=result.returncode,
                duration_seconds=duration,
                error=error,
                metadata={
                    "stderr": result.stderr,
                    "workdir": str(workdir),
                },
            )

        except subprocess.TimeoutExpired:
            duration = time.time() - start_time
            logger.error(f"Claude execution timed out after {timeout}s")
            raise TimeoutError(f"Agent execution timed out after {timeout}s")

        except FileNotFoundError:
            raise ExecutionError(
                "Claude CLI not found. Is it installed? "
                "Install with: npm install -g @anthropic-ai/claude-code"
            )

        except Exception as e:
            logger.exception(f"Claude execution failed: {e}")
            raise ExecutionError(f"Agent execution failed: {e}")

    def _get_claude_path(self) -> str:
        """Get path to Claude CLI.

        Returns:
            Path to claude executable

        Raises:
            ExecutionError: If Claude CLI not found
        """
        if self._claude_path is None:
            self._claude_path = shutil.which("claude")
            if not self._claude_path:
                raise ExecutionError(
                    "Claude CLI not found in PATH. "
                    "Install with: npm install -g @anthropic-ai/claude-code"
                )
        return self._claude_path

    @property
    def agent_type(self) -> AgentType:
        return AgentType.CLAUDE

    def validate_environment(self) -> bool:
        """Check if Claude CLI is available.

        Returns:
            True if claude command is found
        """
        try:
            self._get_claude_path()
            return True
        except ExecutionError:
            return False


class ClaudeAdapterWithMCP(ClaudeAdapter):
    """Claude adapter with MCP server configuration.

    Extends ClaudeAdapter to support Model Context Protocol servers
    for enhanced capabilities.
    """

    def __init__(
        self,
        config: AgentConfig,
        mcp_servers: Optional[List] = None,
    ):
        """Initialize with optional MCP servers.

        Args:
            config: Agent configuration
            mcp_servers: List of MCP server configurations
        """
        super().__init__(config)
        self.mcp_servers = mcp_servers or []

    def execute(
        self,
        prompt: str,
        workdir: Path,
        timeout: int,
    ) -> AgentResponse:
        """Execute with MCP server support.

        Note: MCP configuration is typically done via config files,
        not command line args. This is a placeholder for future
        MCP-specific execution logic.
        """
        # For now, delegate to parent
        # Future: Add MCP-specific handling
        return super().execute(prompt, workdir, timeout)
