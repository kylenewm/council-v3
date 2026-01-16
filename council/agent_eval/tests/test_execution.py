"""
Tests for Brick 2 (Execution Layer) of the Agent Eval system.

Tests:
- Environment setup and cleanup
- Timeout management
- Retry logic
- Agent adapters (mock)
"""

import pytest
import tempfile
import time
from pathlib import Path
from unittest.mock import patch, MagicMock

from council.agent_eval import (
    Config,
    ExecutionConfig,
    AgentConfig,
    Scenario,
    VerificationSpec,
    CommandCheck,
    FileSpec,
    SetupSpec,
)
from council.agent_eval.execution import (
    Environment,
    EnvironmentFactory,
    TimeoutManager,
    RetryManager,
    RetryContext,
    AgentAdapter,
    AgentResponse,
    AgentType,
    MockAdapter,
    ClaudeAdapter,
)
from council.agent_eval.exceptions import (
    EnvironmentError,
    TimeoutError,
    ExecutionError,
)


# ============================================================================
# Environment Tests
# ============================================================================


class TestEnvironment:
    """Test environment setup and cleanup."""

    @pytest.fixture
    def basic_scenario(self):
        """Create a basic scenario for testing."""
        return Scenario(
            id="test-env-001",
            name="Environment Test",
            description="Test environment setup",
            prompt="Do something",
            verification=VerificationSpec(),
            setup=SetupSpec(
                files=[
                    FileSpec(path="src/main.py", content="print('hello')"),
                    FileSpec(path="tests/test_main.py", content="# tests"),
                ],
            ),
        )

    @pytest.fixture
    def exec_config(self):
        """Create execution config."""
        return ExecutionConfig(
            cleanup_on_success=True,
            cleanup_on_failure=False,
        )

    def test_environment_creates_files(self, basic_scenario, exec_config):
        """Test that environment creates specified files."""
        env = Environment(basic_scenario, exec_config)

        try:
            workdir = env.setup()

            # Check files were created
            assert (workdir / "src/main.py").exists()
            assert (workdir / "tests/test_main.py").exists()

            # Check content
            content = (workdir / "src/main.py").read_text()
            assert "print('hello')" in content

        finally:
            env.cleanup()

    def test_environment_as_context_manager(self, basic_scenario, exec_config):
        """Test environment as context manager."""
        workdir_path = None

        with Environment(basic_scenario, exec_config) as env:
            workdir_path = env.workdir
            assert workdir_path.exists()
            assert (workdir_path / "src/main.py").exists()

        # Should be cleaned up after exiting context
        assert not workdir_path.exists()

    def test_environment_keeps_on_failure(self, basic_scenario, exec_config):
        """Test environment keeps workdir on failure when configured."""
        exec_config.cleanup_on_failure = False
        workdir_path = None

        try:
            with Environment(basic_scenario, exec_config) as env:
                workdir_path = env.workdir
                raise ValueError("Simulated failure")
        except ValueError:
            pass

        # Should NOT be cleaned up due to failure
        assert workdir_path.exists()

        # Manual cleanup
        import shutil
        shutil.rmtree(workdir_path)

    def test_environment_workdir_not_available_before_setup(self, basic_scenario, exec_config):
        """Test workdir property raises before setup."""
        env = Environment(basic_scenario, exec_config)

        with pytest.raises(EnvironmentError) as exc_info:
            _ = env.workdir

        assert "not initialized" in str(exc_info.value).lower()

    def test_environment_with_git_init(self, exec_config):
        """Test environment with git initialization."""
        scenario = Scenario(
            id="test-git-001",
            name="Git Test",
            description="Test git init",
            prompt="Do something",
            verification=VerificationSpec(),
            setup=SetupSpec(
                files=[FileSpec(path="README.md", content="# Test")],
                git_init=True,
            ),
        )

        with Environment(scenario, exec_config) as env:
            # Check .git directory exists
            assert (env.workdir / ".git").exists()

            # Check we have an initial commit
            import subprocess
            result = subprocess.run(
                ["git", "log", "--oneline"],
                cwd=env.workdir,
                capture_output=True,
                text=True,
            )
            assert "Initial commit" in result.stdout

    def test_environment_with_setup_commands(self, exec_config):
        """Test environment with custom setup commands."""
        scenario = Scenario(
            id="test-cmd-001",
            name="Command Test",
            description="Test setup commands",
            prompt="Do something",
            verification=VerificationSpec(),
            setup=SetupSpec(
                commands=["echo 'setup' > setup.txt"],
            ),
        )

        with Environment(scenario, exec_config) as env:
            assert (env.workdir / "setup.txt").exists()
            content = (env.workdir / "setup.txt").read_text()
            assert "setup" in content

    def test_environment_factory(self, basic_scenario, exec_config):
        """Test environment factory creates environments."""
        factory = EnvironmentFactory(exec_config)
        env = factory.create(basic_scenario)

        assert env.config == exec_config
        assert env.scenario == basic_scenario


# ============================================================================
# Timeout Manager Tests
# ============================================================================


class TestTimeoutManager:
    """Test timeout management."""

    def test_timeout_context_manager_allows_fast_operation(self):
        """Test that fast operations complete within timeout."""
        result = None
        with TimeoutManager.timeout(5, "Should not timeout"):
            result = 1 + 1
        assert result == 2

    def test_timeout_context_manager_raises_on_slow_operation(self):
        """Test that slow operations trigger timeout."""
        with pytest.raises(TimeoutError) as exc_info:
            with TimeoutManager.timeout(1, "Test timeout"):
                time.sleep(5)  # Will be interrupted

        assert "Test timeout" in str(exc_info.value)

    @pytest.mark.skip(reason="Requires pytest-asyncio")
    async def test_async_timeout(self):
        """Test async timeout."""
        import asyncio

        # Fast operation should work
        async def fast():
            return 42

        result = await TimeoutManager.with_timeout(fast(), 5, "Should not timeout")
        assert result == 42

        # Slow operation should timeout
        async def slow():
            await asyncio.sleep(5)

        with pytest.raises(TimeoutError):
            await TimeoutManager.with_timeout(slow(), 1, "Async timeout")


# ============================================================================
# Retry Manager Tests
# ============================================================================


class TestRetryManager:
    """Test retry management."""

    @pytest.fixture
    def retry_manager(self):
        """Create a retry manager."""
        config = AgentConfig(max_retries=3, retry_delay_seconds=0.01)
        return RetryManager(config)

    def test_successful_operation_no_retry(self, retry_manager):
        """Test that successful operations don't retry."""
        call_count = 0

        def operation():
            nonlocal call_count
            call_count += 1
            return "success"

        result = retry_manager.execute_with_retry(operation, "test op")
        assert result == "success"
        assert call_count == 1

    def test_retry_on_failure_then_success(self, retry_manager):
        """Test retry recovers from transient failures."""
        call_count = 0

        def operation():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("Transient error")
            return "success"

        result = retry_manager.execute_with_retry(operation, "test op")
        assert result == "success"
        assert call_count == 3

    def test_retry_exhausted_raises_execution_error(self, retry_manager):
        """Test exhausted retries raise ExecutionError."""
        call_count = 0

        def operation():
            nonlocal call_count
            call_count += 1
            raise ValueError("Always fails")

        with pytest.raises(ExecutionError) as exc_info:
            retry_manager.execute_with_retry(operation, "failing op")

        assert "failed after" in str(exc_info.value).lower()
        assert call_count == 4  # 1 initial + 3 retries

    def test_retry_selective_exceptions(self, retry_manager):
        """Test retry only catches specified exceptions."""
        call_count = 0

        def operation():
            nonlocal call_count
            call_count += 1
            raise TypeError("Not retryable")

        # TypeError not in retryable_exceptions, should propagate immediately
        with pytest.raises(TypeError) as exc_info:
            retry_manager.execute_with_retry(
                operation,
                "test",
                retryable_exceptions=(ValueError,)
            )

        assert "Not retryable" in str(exc_info.value)
        assert call_count == 1  # No retries

    def test_retry_decorator(self):
        """Test retry decorator."""
        call_count = 0

        @RetryManager.retry_decorator(max_retries=2, base_delay=0.01)
        def flaky_function():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ValueError("Transient")
            return "success"

        result = flaky_function()
        assert result == "success"
        assert call_count == 2


class TestRetryContext:
    """Test retry context for tracking."""

    def test_retry_context_tracking(self):
        """Test retry context tracks retries."""
        ctx = RetryContext(max_total_retries=5)

        assert ctx.can_retry()
        assert ctx.total_retries == 0

        ctx.record_retry("op1", ValueError("err1"))
        ctx.record_retry("op2", ValueError("err2"))

        assert ctx.total_retries == 2
        assert "2 retries" in ctx.retry_summary

    def test_retry_context_limit(self):
        """Test retry context respects limit."""
        ctx = RetryContext(max_total_retries=2)

        ctx.record_retry("op1", ValueError("err"))
        assert ctx.can_retry()

        ctx.record_retry("op2", ValueError("err"))
        assert not ctx.can_retry()


# ============================================================================
# Agent Adapter Tests
# ============================================================================


class TestAgentResponse:
    """Test AgentResponse dataclass."""

    def test_successful_response(self):
        """Test successful response properties."""
        response = AgentResponse(
            output="Done!",
            exit_code=0,
            duration_seconds=5.0,
        )

        assert response.success
        assert "OK" in str(response)

    def test_failed_response(self):
        """Test failed response properties."""
        response = AgentResponse(
            output="",
            exit_code=1,
            duration_seconds=2.0,
            error="Something went wrong",
        )

        assert not response.success
        assert "FAIL" in str(response)


class TestMockAdapter:
    """Test mock adapter for testing."""

    def test_mock_adapter_returns_configured_response(self):
        """Test mock adapter returns configured values."""
        adapter = MockAdapter(
            response_output="Test output",
            response_exit_code=0,
            response_duration=2.5,
        )

        response = adapter.execute("do thing", Path("/tmp"), 60)

        assert response.output == "Test output"
        assert response.exit_code == 0
        assert response.duration_seconds == 2.5

    def test_mock_adapter_tracks_calls(self):
        """Test mock adapter tracks calls."""
        adapter = MockAdapter()

        adapter.execute("prompt 1", Path("/tmp/a"), 30)
        adapter.execute("prompt 2", Path("/tmp/b"), 60)

        assert adapter.call_count == 2
        assert adapter.last_call["prompt"] == "prompt 2"
        assert adapter.last_call["timeout"] == 60

    def test_mock_adapter_simulates_timeout(self):
        """Test mock adapter can simulate timeout."""
        adapter = MockAdapter(should_timeout=True)

        with pytest.raises(TimeoutError):
            adapter.execute("do thing", Path("/tmp"), 60)

    def test_mock_adapter_simulates_error(self):
        """Test mock adapter can simulate error."""
        adapter = MockAdapter(
            should_error=True,
            error_message="Simulated failure",
        )

        with pytest.raises(ExecutionError) as exc_info:
            adapter.execute("do thing", Path("/tmp"), 60)

        assert "Simulated failure" in str(exc_info.value)

    def test_mock_adapter_type(self):
        """Test mock adapter reports correct type."""
        adapter = MockAdapter()
        assert adapter.agent_type == AgentType.MOCK


class TestClaudeAdapter:
    """Test Claude adapter (without actually running claude)."""

    def test_claude_adapter_type(self):
        """Test Claude adapter reports correct type."""
        config = AgentConfig()
        adapter = ClaudeAdapter(config)
        assert adapter.agent_type == AgentType.CLAUDE

    def test_claude_adapter_validates_environment(self):
        """Test Claude adapter environment validation."""
        config = AgentConfig()
        adapter = ClaudeAdapter(config)

        # This will return True if claude is installed, False otherwise
        # We don't fail the test either way
        result = adapter.validate_environment()
        assert isinstance(result, bool)

    @patch("subprocess.run")
    @patch("shutil.which")
    def test_claude_adapter_execute_success(self, mock_which, mock_run):
        """Test Claude adapter execution (mocked)."""
        mock_which.return_value = "/usr/local/bin/claude"
        mock_run.return_value = MagicMock(
            stdout="Task completed",
            stderr="",
            returncode=0,
        )

        config = AgentConfig()
        adapter = ClaudeAdapter(config)

        with tempfile.TemporaryDirectory() as tmpdir:
            response = adapter.execute("Fix the bug", Path(tmpdir), 60)

        assert response.output == "Task completed"
        assert response.exit_code == 0
        assert response.success

    @patch("shutil.which")
    def test_claude_adapter_not_installed(self, mock_which):
        """Test Claude adapter when CLI not installed."""
        mock_which.return_value = None

        config = AgentConfig()
        adapter = ClaudeAdapter(config)

        with pytest.raises(ExecutionError) as exc_info:
            adapter.execute("Fix bug", Path("/tmp"), 60)

        assert "not found" in str(exc_info.value).lower()


# ============================================================================
# Integration Tests
# ============================================================================


class TestExecutionIntegration:
    """Integration tests for execution layer."""

    def test_environment_with_mock_adapter(self):
        """Test running mock adapter in environment."""
        scenario = Scenario(
            id="integration-001",
            name="Integration Test",
            description="Test full flow",
            prompt="Fix the code",
            verification=VerificationSpec(),
            setup=SetupSpec(
                files=[FileSpec(path="main.py", content="print('bug')")],
            ),
        )

        config = ExecutionConfig(cleanup_on_success=True)
        adapter = MockAdapter(response_output="Fixed!")

        with Environment(scenario, config) as env:
            # Verify environment is set up
            assert (env.workdir / "main.py").exists()

            # Run mock adapter
            response = adapter.execute(
                scenario.prompt,
                env.workdir,
                timeout=60,
            )

            assert response.success
            assert adapter.last_call["prompt"] == "Fix the code"

    def test_retry_with_environment(self):
        """Test retry logic with environment."""
        scenario = Scenario(
            id="retry-001",
            name="Retry Test",
            description="Test retries",
            prompt="Fix it",
            verification=VerificationSpec(),
        )

        exec_config = ExecutionConfig(cleanup_on_success=True)
        agent_config = AgentConfig(max_retries=2, retry_delay_seconds=0.01)
        retry_manager = RetryManager(agent_config)

        call_count = 0
        adapter = MockAdapter()

        def run_with_retry():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ValueError("Transient failure")
            return adapter.execute("prompt", Path("/tmp"), 60)

        with Environment(scenario, exec_config):
            response = retry_manager.execute_with_retry(run_with_retry, "agent run")

        assert response.success
        assert call_count == 2
