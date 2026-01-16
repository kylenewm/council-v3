"""
Tests for Brick 1 (Foundation) of the Agent Eval system.

Tests:
- Exception hierarchy
- Configuration loading and validation
- Scenario parsing and validation
- Result dataclasses
"""

import pytest
from pathlib import Path
from datetime import datetime
import tempfile
import yaml

from council.agent_eval import (
    # Exceptions
    AgentEvalError,
    ScenarioError,
    EnvironmentError,
    ExecutionError,
    TimeoutError,
    VerificationError,
    WatchdogError,
    PersistenceError,
    ConfigurationError,
    # Config
    Config,
    AgentConfig,
    WatchdogConfig,
    PersistenceConfig,
    ExecutionConfig,
    # Scenario models
    Difficulty,
    FileSpec,
    SetupSpec,
    CommandCheck,
    FileCheck,
    VerificationSpec,
    Scenario,
    # Result models
    ResultStatus,
    CommandResult,
    FileResult,
    VerificationResult,
    WatchdogResult,
    Metrics,
    RunResult,
)


# ============================================================================
# Exception Tests
# ============================================================================


class TestExceptions:
    """Test exception hierarchy."""

    def test_all_exceptions_inherit_from_base(self):
        """All custom exceptions should inherit from AgentEvalError."""
        exceptions = [
            ScenarioError,
            EnvironmentError,
            ExecutionError,
            TimeoutError,
            VerificationError,
            WatchdogError,
            PersistenceError,
            ConfigurationError,
        ]
        for exc_class in exceptions:
            assert issubclass(exc_class, AgentEvalError)
            # Can catch with base exception
            try:
                raise exc_class("test")
            except AgentEvalError as e:
                assert str(e) == "test"

    def test_exceptions_have_correct_names(self):
        """Verify exception names are correct."""
        assert ScenarioError.__name__ == "ScenarioError"
        assert TimeoutError.__name__ == "TimeoutError"

    def test_exceptions_can_be_raised_and_caught_specifically(self):
        """Each exception can be caught specifically."""
        with pytest.raises(ScenarioError):
            raise ScenarioError("bad scenario")

        with pytest.raises(TimeoutError):
            raise TimeoutError("timed out")


# ============================================================================
# Configuration Tests
# ============================================================================


class TestConfig:
    """Test configuration system."""

    def test_default_config(self):
        """Test default configuration values."""
        config = Config.default()

        # Agent defaults
        assert config.agent.type == "claude"
        assert config.agent.timeout_seconds == 300
        assert config.agent.max_retries == 3

        # Watchdog defaults
        assert config.watchdog.enabled is True
        assert config.watchdog.temperature == 0.0

        # Persistence defaults
        assert config.persistence.enabled is True
        assert config.persistence.keep_history_days == 90

        # Execution defaults
        assert config.execution.parallel_scenarios == 1
        assert config.execution.cleanup_on_success is True
        assert config.execution.cleanup_on_failure is False

    def test_config_from_yaml(self):
        """Test loading config from YAML file."""
        yaml_content = """
agent:
  type: openai
  timeout_seconds: 600
  max_retries: 5

watchdog:
  enabled: false

execution:
  parallel_scenarios: 4
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            f.flush()
            config = Config.from_yaml(Path(f.name))

        assert config.agent.type == "openai"
        assert config.agent.timeout_seconds == 600
        assert config.agent.max_retries == 5
        assert config.watchdog.enabled is False
        assert config.execution.parallel_scenarios == 4

    def test_config_from_yaml_missing_file(self):
        """Test error on missing config file."""
        with pytest.raises(ConfigurationError) as exc_info:
            Config.from_yaml(Path("/nonexistent/config.yaml"))
        assert "not found" in str(exc_info.value)

    def test_agent_config_validation(self):
        """Test agent config validation."""
        with pytest.raises(ConfigurationError) as exc_info:
            AgentConfig(timeout_seconds=0)
        assert "timeout_seconds must be positive" in str(exc_info.value)

        with pytest.raises(ConfigurationError) as exc_info:
            AgentConfig(max_retries=-1)
        assert "max_retries cannot be negative" in str(exc_info.value)

    def test_watchdog_config_validation(self):
        """Test watchdog config validation."""
        with pytest.raises(ConfigurationError) as exc_info:
            WatchdogConfig(temperature=1.5)
        assert "temperature must be between" in str(exc_info.value)

    def test_config_to_dict_and_yaml(self):
        """Test config serialization."""
        config = Config.default()
        d = config.to_dict()

        assert "agent" in d
        assert "watchdog" in d
        assert d["agent"]["timeout_seconds"] == 300

        yaml_str = config.to_yaml()
        assert "agent:" in yaml_str
        assert "timeout_seconds: 300" in yaml_str


# ============================================================================
# Scenario Tests
# ============================================================================


class TestScenario:
    """Test scenario parsing and validation."""

    @pytest.fixture
    def fixtures_dir(self):
        """Return path to test fixtures."""
        return Path(__file__).parent / "fixtures" / "sample_scenarios"

    def test_load_full_scenario_from_yaml(self, fixtures_dir):
        """Test loading a full scenario from YAML."""
        scenario = Scenario.from_yaml(fixtures_dir / "fix_type_error.yaml")

        assert scenario.id == "fix-type-error-001"
        assert scenario.name == "Fix TypeScript type error"
        assert "type error" in scenario.prompt.lower()
        assert scenario.difficulty == Difficulty.EASY
        assert "typescript" in scenario.tags

        # Setup
        assert len(scenario.setup.files) == 1
        assert scenario.setup.files[0].path == "src/broken.ts"
        assert "function add" in scenario.setup.files[0].content

        # Verification
        assert len(scenario.verification.commands) == 1
        assert "tsc" in scenario.verification.commands[0].cmd
        assert len(scenario.verification.files) == 1
        assert scenario.verification.files[0].contains == "b: number"

        # Watchdog
        assert len(scenario.watchdog_questions) == 3
        assert scenario.expected_behavior is not None

    def test_load_minimal_scenario_from_yaml(self, fixtures_dir):
        """Test loading a minimal scenario (only required fields)."""
        scenario = Scenario.from_yaml(fixtures_dir / "minimal.yaml")

        assert scenario.id == "minimal-001"
        assert scenario.name == "Minimal test scenario"
        assert scenario.prompt == "Do something"
        assert scenario.difficulty == Difficulty.MEDIUM  # default
        assert len(scenario.tags) == 0

    def test_scenario_from_dict(self):
        """Test creating scenario from dictionary."""
        data = {
            "scenario": {
                "id": "test-001",
                "name": "Test Scenario",
                "prompt": "Do the thing",
                "verification": {
                    "commands": [{"cmd": "echo test"}]
                },
            }
        }
        scenario = Scenario.from_dict(data)

        assert scenario.id == "test-001"
        assert scenario.name == "Test Scenario"
        assert scenario.prompt == "Do the thing"

    def test_scenario_missing_required_field(self):
        """Test error on missing required field."""
        data = {
            "scenario": {
                "name": "No ID Scenario",
                "prompt": "test",
            }
        }
        with pytest.raises(ScenarioError) as exc_info:
            Scenario.from_dict(data)
        assert "id" in str(exc_info.value).lower()

    def test_scenario_invalid_difficulty(self):
        """Test error on invalid difficulty value."""
        data = {
            "id": "test",
            "name": "test",
            "prompt": "test",
            "difficulty": "impossible",
            "verification": {},
        }
        with pytest.raises(ScenarioError) as exc_info:
            Scenario.from_dict(data)
        assert "difficulty" in str(exc_info.value).lower()

    def test_file_spec_validation(self):
        """Test FileSpec validation."""
        # Empty path
        with pytest.raises(ScenarioError):
            FileSpec(path="", content="test")

        # Absolute path
        with pytest.raises(ScenarioError):
            FileSpec(path="/absolute/path.txt", content="test")

    def test_command_check_validation(self):
        """Test CommandCheck validation."""
        # Empty command
        with pytest.raises(ScenarioError):
            CommandCheck(cmd="")

        # Invalid timeout
        with pytest.raises(ScenarioError):
            CommandCheck(cmd="echo test", timeout_seconds=0)

    def test_scenario_to_yaml(self, fixtures_dir):
        """Test scenario serialization to YAML."""
        scenario = Scenario.from_yaml(fixtures_dir / "fix_type_error.yaml")
        yaml_str = scenario.to_yaml()

        # Should be valid YAML
        parsed = yaml.safe_load(yaml_str)
        assert parsed["scenario"]["id"] == "fix-type-error-001"

    def test_scenario_file_not_found(self):
        """Test error on missing scenario file."""
        with pytest.raises(ScenarioError) as exc_info:
            Scenario.from_yaml(Path("/nonexistent/scenario.yaml"))
        assert "not found" in str(exc_info.value).lower()


# ============================================================================
# Result Tests
# ============================================================================


class TestResults:
    """Test result dataclasses."""

    def test_result_status_values(self):
        """Test ResultStatus enum values."""
        assert ResultStatus.PASSED.value == "passed"
        assert ResultStatus.FAILED.value == "failed"
        assert ResultStatus.ERROR.value == "error"
        assert ResultStatus.TIMEOUT.value == "timeout"
        assert ResultStatus.SKIPPED.value == "skipped"

    def test_command_result(self):
        """Test CommandResult dataclass."""
        result = CommandResult(
            cmd="echo test",
            exit_code=0,
            expected_exit_code=0,
            stdout="test\n",
            stderr="",
            passed=True,
            duration_seconds=0.1,
        )

        assert result.passed
        assert "PASS" in str(result)
        assert "echo test" in str(result)

    def test_file_result(self):
        """Test FileResult dataclass."""
        result = FileResult(
            path="src/main.ts",
            exists=True,
            expected_exists=True,
            contains_check="function main",
            contains_found=True,
            passed=True,
        )

        assert result.passed
        assert "PASS" in str(result)

    def test_verification_result_summary(self):
        """Test VerificationResult aggregation."""
        result = VerificationResult(
            command_results=[
                CommandResult(
                    cmd="test1", exit_code=0, expected_exit_code=0,
                    stdout="", stderr="", passed=True, duration_seconds=0.1
                ),
                CommandResult(
                    cmd="test2", exit_code=1, expected_exit_code=0,
                    stdout="", stderr="", passed=False, duration_seconds=0.2
                ),
            ],
            file_results=[
                FileResult(
                    path="a.txt", exists=True, expected_exists=True, passed=True
                ),
            ],
            passed=False,
        )

        assert result.passed_count == 2
        assert result.failed_count == 1
        assert result.total_count == 3
        assert "2/3" in result.summary()

        failures = result.failures()
        assert len(failures) == 1
        assert "test2" in failures[0]

    def test_watchdog_result(self):
        """Test WatchdogResult dataclass."""
        result = WatchdogResult(
            understanding="good",
            approach="appropriate",
            shortcuts_taken=["skipped edge case"],
            failure_patterns=[],
            success_patterns=["good variable naming"],
            feedback_for_agent="Consider adding error handling",
            confidence=0.85,
        )

        assert result.is_valid
        assert "good" in result.summary()

    def test_watchdog_result_with_error(self):
        """Test WatchdogResult with error."""
        result = WatchdogResult(
            understanding="error",
            approach="error",
            error="API rate limit exceeded",
        )

        assert not result.is_valid
        assert "error" in result.summary().lower()

    def test_metrics(self):
        """Test Metrics dataclass."""
        start = datetime.now()
        end = datetime.now()

        metrics = Metrics(
            scenario_id="test-001",
            start_time=start,
            end_time=end,
            duration_seconds=10.5,
            status=ResultStatus.PASSED,
            verification_passed=True,
            checks_passed=3,
            checks_total=3,
            agent_tokens_input=500,
            agent_tokens_output=200,
            agent_cost_usd=0.01,
        )

        d = metrics.to_dict()
        assert d["scenario_id"] == "test-001"
        assert d["duration_seconds"] == 10.5
        assert d["agent_cost_usd"] == 0.01

    def test_run_result(self):
        """Test RunResult dataclass."""
        now = datetime.now()

        verification = VerificationResult(
            command_results=[],
            file_results=[],
            passed=True,
        )

        metrics = Metrics(
            scenario_id="test-001",
            start_time=now,
            end_time=now,
            duration_seconds=5.0,
            status=ResultStatus.PASSED,
            verification_passed=True,
            checks_passed=0,
            checks_total=0,
        )

        result = RunResult(
            scenario_id="test-001",
            scenario_name="Test Scenario",
            run_id="abc123",
            timestamp=now,
            status=ResultStatus.PASSED,
            verification=verification,
            metrics=metrics,
            agent_output="Done!",
        )

        assert result.passed
        assert "PASSED" in result.summary().upper()

        d = result.to_dict()
        assert d["scenario_id"] == "test-001"
        assert d["status"] == "passed"


# ============================================================================
# Integration Tests
# ============================================================================


class TestFoundationIntegration:
    """Integration tests for Brick 1 components working together."""

    def test_scenario_to_result_flow(self):
        """Test creating a scenario and building results from it."""
        # Create a scenario
        scenario = Scenario(
            id="integration-001",
            name="Integration Test",
            description="Test the full flow",
            prompt="Fix the bug",
            verification=VerificationSpec(
                commands=[CommandCheck(cmd="npm test", expect_exit_code=0)],
                files=[FileCheck(path="src/main.js", contains="function main")],
            ),
            difficulty=Difficulty.MEDIUM,
            tags=["integration", "test"],
        )

        # Simulate running it and creating results
        now = datetime.now()

        verification_result = VerificationResult(
            command_results=[
                CommandResult(
                    cmd="npm test",
                    exit_code=0,
                    expected_exit_code=0,
                    stdout="All tests passed",
                    stderr="",
                    passed=True,
                    duration_seconds=5.0,
                )
            ],
            file_results=[
                FileResult(
                    path="src/main.js",
                    exists=True,
                    expected_exists=True,
                    contains_check="function main",
                    contains_found=True,
                    passed=True,
                )
            ],
            passed=True,
        )

        metrics = Metrics(
            scenario_id=scenario.id,
            start_time=now,
            end_time=now,
            duration_seconds=10.0,
            status=ResultStatus.PASSED,
            verification_passed=True,
            checks_passed=2,
            checks_total=2,
        )

        run_result = RunResult(
            scenario_id=scenario.id,
            scenario_name=scenario.name,
            run_id="test-run",
            timestamp=now,
            status=ResultStatus.PASSED,
            verification=verification_result,
            metrics=metrics,
        )

        # Verify everything connects
        assert run_result.passed
        assert run_result.scenario_id == scenario.id
        assert run_result.verification.passed
        assert run_result.metrics.verification_passed
        assert "2/2" in run_result.verification.summary()
