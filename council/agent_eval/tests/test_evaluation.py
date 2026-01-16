"""
Tests for Brick 3 (Evaluation Layer) of the Agent Eval system.

Tests:
- Verifier (command and file checks)
- Watchdog (LLM evaluation - mocked)
- Metrics collector
"""

import pytest
import tempfile
from pathlib import Path
from datetime import datetime, timedelta

from council.agent_eval import (
    Scenario,
    VerificationSpec,
    CommandCheck,
    FileCheck,
    VerificationResult,
    ResultStatus,
)
from council.agent_eval.evaluation import (
    Verifier,
    QuickVerifier,
    Watchdog,
    MockWatchdog,
    MetricsCollector,
    MetricsAggregator,
)
from council.agent_eval.execution import AgentResponse
from council.agent_eval.config import WatchdogConfig
from council.agent_eval.exceptions import WatchdogError


# ============================================================================
# Verifier Tests
# ============================================================================


class TestVerifier:
    """Test deterministic verification."""

    @pytest.fixture
    def verifier(self):
        """Create verifier instance."""
        return Verifier()

    @pytest.fixture
    def workdir(self):
        """Create temporary working directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_command_check_success(self, verifier, workdir):
        """Test command check that succeeds."""
        spec = VerificationSpec(
            commands=[
                CommandCheck(cmd="echo hello", expect_exit_code=0),
            ]
        )

        result = verifier.verify(spec, workdir)

        assert result.passed
        assert len(result.command_results) == 1
        assert result.command_results[0].passed
        assert "hello" in result.command_results[0].stdout

    def test_command_check_failure_exit_code(self, verifier, workdir):
        """Test command check with wrong exit code."""
        spec = VerificationSpec(
            commands=[
                CommandCheck(cmd="exit 1", expect_exit_code=0),
            ]
        )

        result = verifier.verify(spec, workdir)

        assert not result.passed
        assert not result.command_results[0].passed
        assert result.command_results[0].exit_code == 1

    def test_command_check_stdout_contains(self, verifier, workdir):
        """Test command check for stdout content."""
        spec = VerificationSpec(
            commands=[
                CommandCheck(
                    cmd="echo 'test output here'",
                    expect_exit_code=0,
                    expect_stdout_contains="output here",
                ),
            ]
        )

        result = verifier.verify(spec, workdir)
        assert result.passed

    def test_command_check_stdout_contains_missing(self, verifier, workdir):
        """Test command check when expected content is missing."""
        spec = VerificationSpec(
            commands=[
                CommandCheck(
                    cmd="echo hello",
                    expect_exit_code=0,
                    expect_stdout_contains="goodbye",
                ),
            ]
        )

        result = verifier.verify(spec, workdir)
        assert not result.passed

    def test_command_check_stdout_not_contains(self, verifier, workdir):
        """Test command check for forbidden content."""
        spec = VerificationSpec(
            commands=[
                CommandCheck(
                    cmd="echo 'error: something bad'",
                    expect_exit_code=0,
                    expect_stdout_not_contains="error",
                ),
            ]
        )

        result = verifier.verify(spec, workdir)
        assert not result.passed

    def test_file_check_exists(self, verifier, workdir):
        """Test file existence check."""
        # Create file
        (workdir / "test.txt").write_text("content")

        spec = VerificationSpec(
            files=[
                FileCheck(path="test.txt", exists=True),
            ]
        )

        result = verifier.verify(spec, workdir)
        assert result.passed

    def test_file_check_not_exists(self, verifier, workdir):
        """Test file non-existence check."""
        spec = VerificationSpec(
            files=[
                FileCheck(path="nonexistent.txt", exists=False),
            ]
        )

        result = verifier.verify(spec, workdir)
        assert result.passed

    def test_file_check_missing_when_expected(self, verifier, workdir):
        """Test failure when expected file is missing."""
        spec = VerificationSpec(
            files=[
                FileCheck(path="should_exist.txt", exists=True),
            ]
        )

        result = verifier.verify(spec, workdir)
        assert not result.passed
        assert "does not exist" in result.file_results[0].error.lower()

    def test_file_check_contains(self, verifier, workdir):
        """Test file content check."""
        (workdir / "code.py").write_text("def main():\n    print('hello')")

        spec = VerificationSpec(
            files=[
                FileCheck(path="code.py", exists=True, contains="def main"),
            ]
        )

        result = verifier.verify(spec, workdir)
        assert result.passed

    def test_file_check_contains_missing(self, verifier, workdir):
        """Test file content check when content missing."""
        (workdir / "code.py").write_text("print('hello')")

        spec = VerificationSpec(
            files=[
                FileCheck(path="code.py", exists=True, contains="def main"),
            ]
        )

        result = verifier.verify(spec, workdir)
        assert not result.passed

    def test_file_check_not_contains(self, verifier, workdir):
        """Test file forbidden content check."""
        (workdir / "code.py").write_text("# TODO: fix this hack")

        spec = VerificationSpec(
            files=[
                FileCheck(path="code.py", exists=True, not_contains="TODO"),
            ]
        )

        result = verifier.verify(spec, workdir)
        assert not result.passed

    def test_file_check_regex(self, verifier, workdir):
        """Test file regex check."""
        (workdir / "version.txt").write_text("version: 1.2.3")

        spec = VerificationSpec(
            files=[
                FileCheck(
                    path="version.txt",
                    exists=True,
                    matches_regex=r"version: \d+\.\d+\.\d+",
                ),
            ]
        )

        result = verifier.verify(spec, workdir)
        assert result.passed

    def test_multiple_checks_all_pass(self, verifier, workdir):
        """Test multiple checks all passing."""
        (workdir / "output.txt").write_text("success")

        spec = VerificationSpec(
            commands=[
                CommandCheck(cmd="echo done", expect_exit_code=0),
            ],
            files=[
                FileCheck(path="output.txt", exists=True, contains="success"),
            ],
        )

        result = verifier.verify(spec, workdir)
        assert result.passed
        assert result.passed_count == 2
        assert result.total_count == 2

    def test_multiple_checks_partial_failure(self, verifier, workdir):
        """Test multiple checks with partial failure."""
        spec = VerificationSpec(
            commands=[
                CommandCheck(cmd="echo done", expect_exit_code=0),
                CommandCheck(cmd="exit 1", expect_exit_code=0),  # Will fail
            ],
        )

        result = verifier.verify(spec, workdir)
        assert not result.passed
        assert result.passed_count == 1
        assert result.failed_count == 1

    def test_verification_result_summary(self, verifier, workdir):
        """Test verification result summary."""
        (workdir / "a.txt").write_text("a")

        spec = VerificationSpec(
            commands=[CommandCheck(cmd="echo test", expect_exit_code=0)],
            files=[FileCheck(path="a.txt", exists=True)],
        )

        result = verifier.verify(spec, workdir)
        assert "2/2" in result.summary()

    def test_verification_result_failures_list(self, verifier, workdir):
        """Test getting list of failures."""
        spec = VerificationSpec(
            commands=[CommandCheck(cmd="exit 1", expect_exit_code=0)],
            files=[FileCheck(path="missing.txt", exists=True)],
        )

        result = verifier.verify(spec, workdir)
        failures = result.failures()

        assert len(failures) == 2
        assert any("exit" in f.lower() for f in failures)
        assert any("missing" in f.lower() for f in failures)


class TestQuickVerifier:
    """Test QuickVerifier convenience methods."""

    @pytest.fixture
    def workdir(self):
        """Create temporary working directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_command_succeeds(self, workdir):
        """Test quick command success check."""
        qv = QuickVerifier(workdir)
        assert qv.command_succeeds("echo hello")
        assert not qv.command_succeeds("exit 1")

    def test_command_output_contains(self, workdir):
        """Test quick command output check."""
        qv = QuickVerifier(workdir)
        assert qv.command_output_contains("echo 'hello world'", "world")
        assert not qv.command_output_contains("echo hello", "goodbye")

    def test_file_exists(self, workdir):
        """Test quick file existence check."""
        (workdir / "exists.txt").write_text("content")
        qv = QuickVerifier(workdir)

        assert qv.file_exists("exists.txt")
        assert not qv.file_exists("missing.txt")

    def test_file_contains(self, workdir):
        """Test quick file content check."""
        (workdir / "code.py").write_text("def main(): pass")
        qv = QuickVerifier(workdir)

        assert qv.file_contains("code.py", "def main")
        assert not qv.file_contains("code.py", "class Main")


# ============================================================================
# Watchdog Tests
# ============================================================================


class TestMockWatchdog:
    """Test mock watchdog for testing purposes."""

    @pytest.fixture
    def scenario(self):
        """Create test scenario."""
        return Scenario(
            id="test-001",
            name="Test Scenario",
            description="Test",
            prompt="Fix the bug",
            verification=VerificationSpec(),
        )

    @pytest.fixture
    def verification_result(self):
        """Create test verification result."""
        return VerificationResult(passed=True)

    def test_mock_watchdog_returns_configured_values(self, scenario, verification_result):
        """Test mock watchdog returns configured values."""
        watchdog = MockWatchdog(
            understanding="good",
            approach="appropriate",
            feedback="Test feedback",
        )

        result = watchdog.evaluate(scenario, "agent output", verification_result)

        assert result.understanding == "good"
        assert result.approach == "appropriate"
        assert result.feedback_for_agent == "Test feedback"

    def test_mock_watchdog_tracks_calls(self, scenario, verification_result):
        """Test mock watchdog tracks calls."""
        watchdog = MockWatchdog()

        watchdog.evaluate(scenario, "output 1", verification_result)
        watchdog.evaluate(scenario, "output 2", verification_result)

        assert watchdog.call_count == 2

    def test_mock_watchdog_simulates_error(self, scenario, verification_result):
        """Test mock watchdog error simulation."""
        watchdog = MockWatchdog(
            should_error=True,
            error_message="API rate limit",
        )

        with pytest.raises(WatchdogError) as exc_info:
            watchdog.evaluate(scenario, "output", verification_result)

        assert "API rate limit" in str(exc_info.value)


class TestWatchdog:
    """Test watchdog (without making real API calls)."""

    def test_watchdog_disabled(self):
        """Test watchdog when disabled."""
        config = WatchdogConfig(enabled=False)
        watchdog = Watchdog(config)

        scenario = Scenario(
            id="test",
            name="Test",
            description="Test",
            prompt="Do something",
            verification=VerificationSpec(),
        )

        result = watchdog.evaluate(
            scenario,
            "agent output",
            VerificationResult(passed=True),
        )

        assert result.understanding == "skipped"
        assert result.approach == "skipped"

    def test_watchdog_parse_valid_json(self):
        """Test watchdog JSON parsing."""
        config = WatchdogConfig(enabled=True)
        watchdog = Watchdog(config)

        json_response = """{
            "understanding": "good",
            "approach": "appropriate",
            "shortcuts_taken": ["skipped error handling"],
            "failure_patterns": [],
            "success_patterns": ["good naming"],
            "feedback_for_agent": "Consider adding tests",
            "suggested_scenarios": ["edge case test"],
            "confidence": 0.85
        }"""

        result = watchdog._parse_response(json_response)

        assert result.understanding == "good"
        assert result.approach == "appropriate"
        assert "skipped error handling" in result.shortcuts_taken
        assert result.confidence == 0.85

    def test_watchdog_parse_json_with_surrounding_text(self):
        """Test watchdog parses JSON even with surrounding text."""
        config = WatchdogConfig(enabled=True)
        watchdog = Watchdog(config)

        response = """Here is my evaluation:
        {"understanding": "partial", "approach": "over-engineered", "feedback_for_agent": "simplify"}
        That's my assessment."""

        result = watchdog._parse_response(response)

        assert result.understanding == "partial"
        assert result.approach == "over-engineered"

    def test_watchdog_parse_invalid_json_fallback(self):
        """Test watchdog handles invalid JSON gracefully."""
        config = WatchdogConfig(enabled=True)
        watchdog = Watchdog(config)

        result = watchdog._parse_response("This is not JSON at all")

        assert result.understanding == "parse_error"
        assert result.error is not None


# ============================================================================
# Metrics Tests
# ============================================================================


class TestMetricsCollector:
    """Test metrics collection."""

    @pytest.fixture
    def collector(self):
        """Create metrics collector."""
        return MetricsCollector()

    @pytest.fixture
    def scenario(self):
        """Create test scenario."""
        return Scenario(
            id="metrics-test-001",
            name="Metrics Test",
            description="Test",
            prompt="Do something",
            verification=VerificationSpec(),
        )

    def test_collect_successful_run(self, collector, scenario):
        """Test collecting metrics from successful run."""
        start = datetime.now()
        end = start + timedelta(seconds=10)

        response = AgentResponse(
            output="Done!",
            exit_code=0,
            tokens_input=100,
            tokens_output=50,
            cost_usd=0.01,
            duration_seconds=10.0,
        )

        verification = VerificationResult(passed=True)

        metrics = collector.collect(
            scenario=scenario,
            agent_response=response,
            verification_result=verification,
            start_time=start,
            end_time=end,
        )

        assert metrics.scenario_id == "metrics-test-001"
        assert metrics.status == ResultStatus.PASSED
        assert metrics.verification_passed
        assert metrics.agent_tokens_input == 100
        assert metrics.agent_cost_usd == 0.01

    def test_collect_failed_run(self, collector, scenario):
        """Test collecting metrics from failed run."""
        start = datetime.now()
        end = start + timedelta(seconds=5)

        response = AgentResponse(output="", exit_code=0, duration_seconds=5.0)
        verification = VerificationResult(passed=False)

        metrics = collector.collect(
            scenario=scenario,
            agent_response=response,
            verification_result=verification,
            start_time=start,
            end_time=end,
        )

        assert metrics.status == ResultStatus.FAILED
        assert not metrics.verification_passed

    def test_collect_error_run(self, collector, scenario):
        """Test collecting metrics from error run."""
        start = datetime.now()
        end = start + timedelta(seconds=2)

        response = AgentResponse(
            output="",
            exit_code=1,
            error="Something went wrong",
            duration_seconds=2.0,
        )
        verification = VerificationResult(passed=False)

        metrics = collector.collect(
            scenario=scenario,
            agent_response=response,
            verification_result=verification,
            start_time=start,
            end_time=end,
        )

        assert metrics.status == ResultStatus.ERROR

    def test_collect_timeout_run(self, collector, scenario):
        """Test collecting metrics from timeout run."""
        start = datetime.now()
        end = start + timedelta(seconds=300)

        response = AgentResponse(
            output="",
            exit_code=1,
            error="timeout exceeded",
            duration_seconds=300.0,
        )
        verification = VerificationResult(passed=False)

        metrics = collector.collect(
            scenario=scenario,
            agent_response=response,
            verification_result=verification,
            start_time=start,
            end_time=end,
        )

        assert metrics.status == ResultStatus.TIMEOUT

    def test_collect_from_error(self, collector, scenario):
        """Test collecting metrics from error case."""
        start = datetime.now()

        metrics = collector.collect_from_error(
            scenario=scenario,
            start_time=start,
            error="Connection refused",
        )

        assert metrics.status == ResultStatus.ERROR
        assert not metrics.verification_passed


class TestMetricsAggregator:
    """Test metrics aggregation."""

    @pytest.fixture
    def aggregator(self):
        """Create metrics aggregator."""
        return MetricsAggregator()

    def _make_metrics(
        self,
        scenario_id: str,
        status: ResultStatus,
        duration: float = 10.0,
        cost: float = 0.01,
    ) -> "Metrics":
        """Helper to create metrics."""
        from council.agent_eval import Metrics

        now = datetime.now()
        return Metrics(
            scenario_id=scenario_id,
            start_time=now,
            end_time=now + timedelta(seconds=duration),
            duration_seconds=duration,
            status=status,
            verification_passed=(status == ResultStatus.PASSED),
            checks_passed=1 if status == ResultStatus.PASSED else 0,
            checks_total=1,
            agent_cost_usd=cost,
        )

    def test_aggregator_counts(self, aggregator):
        """Test aggregator counting."""
        aggregator.add(self._make_metrics("s1", ResultStatus.PASSED))
        aggregator.add(self._make_metrics("s2", ResultStatus.PASSED))
        aggregator.add(self._make_metrics("s3", ResultStatus.FAILED))
        aggregator.add(self._make_metrics("s4", ResultStatus.ERROR))
        aggregator.add(self._make_metrics("s5", ResultStatus.TIMEOUT))

        assert aggregator.total_runs == 5
        assert aggregator.passed_runs == 2
        assert aggregator.failed_runs == 1
        assert aggregator.error_runs == 1
        assert aggregator.timeout_runs == 1

    def test_aggregator_pass_rate(self, aggregator):
        """Test pass rate calculation."""
        aggregator.add(self._make_metrics("s1", ResultStatus.PASSED))
        aggregator.add(self._make_metrics("s2", ResultStatus.PASSED))
        aggregator.add(self._make_metrics("s3", ResultStatus.FAILED))
        aggregator.add(self._make_metrics("s4", ResultStatus.FAILED))

        assert aggregator.pass_rate == 50.0

    def test_aggregator_totals(self, aggregator):
        """Test total calculations."""
        aggregator.add(self._make_metrics("s1", ResultStatus.PASSED, duration=10, cost=0.01))
        aggregator.add(self._make_metrics("s2", ResultStatus.PASSED, duration=20, cost=0.02))

        assert aggregator.total_duration == 30.0
        assert aggregator.total_cost == 0.03
        assert aggregator.avg_duration == 15.0

    def test_aggregator_summary(self, aggregator):
        """Test summary generation."""
        aggregator.add(self._make_metrics("s1", ResultStatus.PASSED))
        aggregator.add(self._make_metrics("s2", ResultStatus.FAILED))

        summary = aggregator.summary()

        assert summary["total_runs"] == 2
        assert summary["passed"] == 1
        assert summary["failed"] == 1
        assert "50.0%" in summary["pass_rate"]

    def test_aggregator_by_scenario(self, aggregator):
        """Test grouping by scenario."""
        aggregator.add(self._make_metrics("s1", ResultStatus.PASSED))
        aggregator.add(self._make_metrics("s1", ResultStatus.FAILED))
        aggregator.add(self._make_metrics("s2", ResultStatus.PASSED))

        by_scenario = aggregator.by_scenario()

        assert len(by_scenario["s1"]) == 2
        assert len(by_scenario["s2"]) == 1

    def test_aggregator_scenario_summary(self, aggregator):
        """Test scenario-specific summary."""
        aggregator.add(self._make_metrics("s1", ResultStatus.PASSED))
        aggregator.add(self._make_metrics("s1", ResultStatus.PASSED))
        aggregator.add(self._make_metrics("s1", ResultStatus.FAILED))

        summary = aggregator.scenario_summary("s1")

        assert summary["runs"] == 3
        assert summary["passed"] == 2
        assert "66" in summary["pass_rate"]  # 66.7%

    def test_aggregator_empty(self, aggregator):
        """Test aggregator with no data."""
        assert aggregator.total_runs == 0
        assert aggregator.pass_rate == 0.0
        assert aggregator.avg_duration == 0.0


# ============================================================================
# Integration Tests
# ============================================================================


class TestEvaluationIntegration:
    """Integration tests for evaluation layer."""

    def test_verify_and_collect_metrics(self):
        """Test verification followed by metrics collection."""
        with tempfile.TemporaryDirectory() as tmpdir:
            workdir = Path(tmpdir)
            (workdir / "result.txt").write_text("success")

            # Create scenario
            scenario = Scenario(
                id="integration-001",
                name="Integration Test",
                description="Test full evaluation",
                prompt="Create result.txt with 'success'",
                verification=VerificationSpec(
                    files=[FileCheck(path="result.txt", contains="success")],
                ),
            )

            # Run verification
            verifier = Verifier()
            verification_result = verifier.verify(scenario.verification, workdir)

            # Simulate agent response
            response = AgentResponse(
                output="Created file",
                exit_code=0,
                duration_seconds=5.0,
            )

            # Collect metrics
            collector = MetricsCollector()
            start = datetime.now()
            end = start + timedelta(seconds=5)

            metrics = collector.collect(
                scenario=scenario,
                agent_response=response,
                verification_result=verification_result,
                start_time=start,
                end_time=end,
            )

            # Verify everything connected
            assert verification_result.passed
            assert metrics.status == ResultStatus.PASSED
            assert metrics.scenario_id == scenario.id

    def test_full_evaluation_flow_with_mock_watchdog(self):
        """Test full evaluation flow with mock watchdog."""
        with tempfile.TemporaryDirectory() as tmpdir:
            workdir = Path(tmpdir)
            (workdir / "main.py").write_text("def main(): pass")

            scenario = Scenario(
                id="flow-001",
                name="Flow Test",
                description="Test full flow",
                prompt="Create main.py",
                verification=VerificationSpec(
                    commands=[CommandCheck(cmd="echo done", expect_exit_code=0)],
                    files=[FileCheck(path="main.py", contains="def main")],
                ),
            )

            # Verification
            verifier = Verifier()
            verification_result = verifier.verify(scenario.verification, workdir)

            # Watchdog (mocked)
            watchdog = MockWatchdog(
                understanding="good",
                approach="appropriate",
                feedback="Well done",
            )
            watchdog_result = watchdog.evaluate(
                scenario,
                "agent output",
                verification_result,
            )

            # Metrics
            collector = MetricsCollector()
            response = AgentResponse(output="Done", exit_code=0, duration_seconds=3.0)
            start = datetime.now()
            metrics = collector.collect(
                scenario=scenario,
                agent_response=response,
                verification_result=verification_result,
                start_time=start,
                end_time=datetime.now(),
            )

            # Aggregate
            aggregator = MetricsAggregator()
            aggregator.add(metrics)

            # Assertions
            assert verification_result.passed
            assert watchdog_result.understanding == "good"
            assert metrics.status == ResultStatus.PASSED
            assert aggregator.pass_rate == 100.0
