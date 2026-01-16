"""
Tests for Brick 4 (Orchestration) of the Agent Eval system.

Tests:
- AgentEvalRunner
- DryRunner
- Reporter
- CLI (basic validation)
"""

import pytest
import tempfile
from pathlib import Path
from datetime import datetime, timedelta

from council.agent_eval import (
    Config,
    Scenario,
    VerificationSpec,
    CommandCheck,
    FileCheck,
    FileSpec,
    SetupSpec,
    ResultStatus,
    RunResult,
    VerificationResult,
    Metrics,
    AgentEvalRunner,
    DryRunner,
    Report,
    Reporter,
    ComparisonReporter,
)
from council.agent_eval.execution import MockAdapter
from council.agent_eval.evaluation import MockWatchdog


# ============================================================================
# Runner Tests
# ============================================================================


class TestAgentEvalRunner:
    """Test main runner."""

    @pytest.fixture
    def mock_config(self):
        """Create config for testing."""
        config = Config.default()
        config.watchdog.enabled = False  # Disable watchdog for speed
        config.execution.cleanup_on_success = True
        config.execution.cleanup_on_failure = True
        return config

    @pytest.fixture
    def simple_scenario(self):
        """Create simple scenario that should pass."""
        return Scenario(
            id="simple-001",
            name="Simple Test",
            description="A simple test",
            prompt="Create a file called output.txt with 'done'",
            setup=SetupSpec(),
            verification=VerificationSpec(
                commands=[CommandCheck(cmd="echo done", expect_exit_code=0)],
            ),
        )

    def test_runner_with_mock_adapter(self, mock_config, simple_scenario):
        """Test runner with mock adapter."""
        mock_adapter = MockAdapter(
            response_output="Created output.txt with 'done'",
            response_exit_code=0,
        )

        runner = AgentEvalRunner(
            config=mock_config,
            agent=mock_adapter,
        )

        result = runner.run_scenario(simple_scenario)

        assert result.scenario_id == "simple-001"
        assert result.status == ResultStatus.PASSED
        assert result.verification.passed
        assert mock_adapter.call_count == 1

    def test_runner_verification_failure(self, mock_config):
        """Test runner when verification fails."""
        scenario = Scenario(
            id="fail-001",
            name="Failing Test",
            description="Test that should fail verification",
            prompt="Do nothing",
            verification=VerificationSpec(
                commands=[CommandCheck(cmd="exit 1", expect_exit_code=0)],
            ),
        )

        mock_adapter = MockAdapter(
            response_output="Did nothing",
            response_exit_code=0,
        )

        runner = AgentEvalRunner(
            config=mock_config,
            agent=mock_adapter,
        )

        result = runner.run_scenario(scenario)

        assert result.status == ResultStatus.FAILED
        assert not result.verification.passed

    def test_runner_timeout(self, mock_config, simple_scenario):
        """Test runner handles timeout."""
        mock_adapter = MockAdapter(should_timeout=True)

        runner = AgentEvalRunner(
            config=mock_config,
            agent=mock_adapter,
        )

        result = runner.run_scenario(simple_scenario)

        assert result.status == ResultStatus.TIMEOUT
        assert result.error is not None

    def test_runner_error(self, mock_config, simple_scenario):
        """Test runner handles errors."""
        mock_adapter = MockAdapter(
            should_error=True,
            error_message="Connection refused",
        )

        runner = AgentEvalRunner(
            config=mock_config,
            agent=mock_adapter,
        )

        result = runner.run_scenario(simple_scenario)

        assert result.status == ResultStatus.ERROR
        assert "Connection refused" in result.error

    def test_runner_multiple_scenarios(self, mock_config):
        """Test running multiple scenarios."""
        scenarios = [
            Scenario(
                id=f"multi-{i}",
                name=f"Multi Test {i}",
                description="Test",
                prompt="Do something",
                verification=VerificationSpec(
                    commands=[CommandCheck(cmd="echo done", expect_exit_code=0)],
                ),
            )
            for i in range(3)
        ]

        mock_adapter = MockAdapter()

        runner = AgentEvalRunner(
            config=mock_config,
            agent=mock_adapter,
        )

        results = runner.run_scenarios(scenarios)

        assert len(results) == 3
        assert mock_adapter.call_count == 3
        assert all(r.status == ResultStatus.PASSED for r in results)

    def test_runner_with_watchdog(self, mock_config, simple_scenario):
        """Test runner with mock watchdog."""
        mock_config.watchdog.enabled = True

        mock_adapter = MockAdapter()
        mock_watchdog = MockWatchdog(
            understanding="good",
            approach="appropriate",
            feedback="Well done",
        )

        runner = AgentEvalRunner(
            config=mock_config,
            agent=mock_adapter,
            watchdog=mock_watchdog,
        )

        result = runner.run_scenario(simple_scenario)

        assert result.watchdog is not None
        assert result.watchdog.understanding == "good"
        assert mock_watchdog.call_count == 1


class TestDryRunner:
    """Test dry runner for validation."""

    def test_validate_valid_scenario(self):
        """Test validating a valid scenario."""
        scenario = Scenario(
            id="valid-001",
            name="Valid Scenario",
            description="Test",
            prompt="Do something",
            verification=VerificationSpec(
                commands=[CommandCheck(cmd="echo test", expect_exit_code=0)],
            ),
        )

        dry = DryRunner()
        result = dry.validate_scenario(scenario)

        assert result["valid"]
        assert len(result["issues"]) == 0

    def test_validate_empty_prompt(self):
        """Test validating scenario with empty prompt."""
        scenario = Scenario(
            id="invalid-001",
            name="Invalid Scenario",
            description="Test",
            prompt="   ",  # Whitespace only
            verification=VerificationSpec(),
        )

        dry = DryRunner()
        result = dry.validate_scenario(scenario)

        assert not result["valid"]
        assert "Empty prompt" in result["issues"]

    def test_validate_no_verification(self):
        """Test validating scenario with no verification."""
        scenario = Scenario(
            id="no-verify-001",
            name="No Verification",
            description="Test",
            prompt="Do something",
            verification=VerificationSpec(),
        )

        dry = DryRunner()
        result = dry.validate_scenario(scenario)

        assert not result["valid"]
        assert any("No verification" in issue for issue in result["issues"])

    def test_validate_multiple_scenarios(self):
        """Test validating multiple scenarios."""
        scenarios = [
            Scenario(
                id="valid-1",
                name="Valid 1",
                description="Test",
                prompt="Do it",
                verification=VerificationSpec(
                    commands=[CommandCheck(cmd="echo 1")],
                ),
            ),
            Scenario(
                id="invalid-1",
                name="Invalid 1",
                description="Test",
                prompt="   ",  # Whitespace only - passes __post_init__ but fails DryRunner
                verification=VerificationSpec(),
            ),
        ]

        dry = DryRunner()
        result = dry.validate_scenarios(scenarios)

        assert result["total"] == 2
        assert result["valid"] == 1
        assert result["invalid"] == 1


# ============================================================================
# Reporter Tests
# ============================================================================


class TestReporter:
    """Test report generation."""

    def _make_result(
        self,
        scenario_id: str,
        status: ResultStatus,
        passed: bool = True,
    ) -> RunResult:
        """Helper to create run results."""
        now = datetime.now()
        return RunResult(
            scenario_id=scenario_id,
            scenario_name=f"Test {scenario_id}",
            run_id="test-run",
            timestamp=now,
            status=status,
            verification=VerificationResult(passed=passed),
            metrics=Metrics(
                scenario_id=scenario_id,
                start_time=now,
                end_time=now + timedelta(seconds=10),
                duration_seconds=10.0,
                status=status,
                verification_passed=passed,
                checks_passed=1 if passed else 0,
                checks_total=1,
            ),
        )

    def test_generate_report(self):
        """Test generating a report."""
        results = [
            self._make_result("s1", ResultStatus.PASSED, True),
            self._make_result("s2", ResultStatus.PASSED, True),
            self._make_result("s3", ResultStatus.FAILED, False),
        ]

        reporter = Reporter()
        report = reporter.generate(results)

        assert report.total_scenarios == 3
        assert report.passed == 2
        assert report.failed == 1
        assert report.pass_rate == pytest.approx(66.67, rel=0.1)

    def test_generate_report_empty(self):
        """Test generating report with no results."""
        reporter = Reporter()
        report = reporter.generate([])

        assert report.total_scenarios == 0
        assert report.pass_rate == 0.0

    def test_report_to_json(self):
        """Test JSON export."""
        results = [self._make_result("s1", ResultStatus.PASSED)]

        reporter = Reporter()
        report = reporter.generate(results)
        json_output = reporter.to_json(report)

        assert '"total_scenarios": 1' in json_output
        assert '"passed": 1' in json_output

    def test_report_to_markdown(self):
        """Test Markdown export."""
        results = [
            self._make_result("s1", ResultStatus.PASSED),
            self._make_result("s2", ResultStatus.FAILED, False),
        ]

        reporter = Reporter()
        report = reporter.generate(results)
        md = reporter.to_markdown(report)

        assert "# Agent Eval Report" in md
        assert "| s1 |" in md
        assert "| s2 |" in md
        assert "Failure Details" in md

    def test_report_to_summary(self):
        """Test summary export."""
        results = [
            self._make_result("s1", ResultStatus.PASSED),
            self._make_result("s2", ResultStatus.PASSED),
        ]

        reporter = Reporter()
        report = reporter.generate(results)
        summary = reporter.to_summary(report)

        assert "2/2" in summary
        assert "100.0%" in summary


class TestComparisonReporter:
    """Test comparison reporting."""

    def _make_report(
        self,
        passed: int,
        failed: int,
        avg_duration: float,
        patterns: list = None,
    ) -> Report:
        """Helper to create reports."""
        results = []
        for i in range(passed):
            results.append(
                RunResult(
                    scenario_id=f"pass-{i}",
                    scenario_name=f"Pass {i}",
                    run_id="test",
                    timestamp=datetime.now(),
                    status=ResultStatus.PASSED,
                    verification=VerificationResult(passed=True),
                    metrics=Metrics(
                        scenario_id=f"pass-{i}",
                        start_time=datetime.now(),
                        end_time=datetime.now(),
                        duration_seconds=avg_duration,
                        status=ResultStatus.PASSED,
                        verification_passed=True,
                        checks_passed=1,
                        checks_total=1,
                    ),
                )
            )
        for i in range(failed):
            results.append(
                RunResult(
                    scenario_id=f"fail-{i}",
                    scenario_name=f"Fail {i}",
                    run_id="test",
                    timestamp=datetime.now(),
                    status=ResultStatus.FAILED,
                    verification=VerificationResult(passed=False),
                    metrics=Metrics(
                        scenario_id=f"fail-{i}",
                        start_time=datetime.now(),
                        end_time=datetime.now(),
                        duration_seconds=avg_duration,
                        status=ResultStatus.FAILED,
                        verification_passed=False,
                        checks_passed=0,
                        checks_total=1,
                    ),
                )
            )

        total = passed + failed
        return Report(
            timestamp=datetime.now(),
            total_scenarios=total,
            passed=passed,
            failed=failed,
            errors=0,
            timeouts=0,
            pass_rate=(passed / total * 100) if total > 0 else 0,
            avg_duration_seconds=avg_duration,
            total_duration_seconds=avg_duration * total,
            results=results,
            patterns_identified=patterns or [],
        )

    def test_compare_improvement(self):
        """Test comparison showing improvement."""
        baseline = self._make_report(passed=5, failed=5, avg_duration=20.0)
        current = self._make_report(passed=8, failed=2, avg_duration=15.0)

        comp = ComparisonReporter()
        result = comp.compare(baseline, current)

        assert result["improved"]
        assert result["pass_rate_delta"] > 0
        assert result["faster"]

    def test_compare_regression(self):
        """Test comparison showing regression."""
        baseline = self._make_report(passed=8, failed=2, avg_duration=10.0)
        current = self._make_report(passed=5, failed=5, avg_duration=15.0)

        comp = ComparisonReporter()
        result = comp.compare(baseline, current)

        assert not result["improved"]
        assert result["pass_rate_delta"] < 0
        assert not result["faster"]

    def test_compare_to_markdown(self):
        """Test comparison markdown output."""
        baseline = self._make_report(passed=5, failed=5, avg_duration=20.0)
        current = self._make_report(passed=8, failed=2, avg_duration=15.0)

        comp = ComparisonReporter()
        comparison = comp.compare(baseline, current)
        md = comp.to_markdown(comparison)

        assert "Comparison Report" in md
        assert "Pass Rate" in md


# ============================================================================
# Integration Tests
# ============================================================================


class TestOrchestrationIntegration:
    """Integration tests for orchestration layer."""

    def test_full_pipeline_with_mocks(self):
        """Test full pipeline with all components mocked."""
        scenario = Scenario(
            id="pipeline-001",
            name="Pipeline Test",
            description="Test full pipeline",
            prompt="Create result.txt",
            setup=SetupSpec(
                files=[FileSpec(path="input.txt", content="input data")],
            ),
            verification=VerificationSpec(
                commands=[CommandCheck(cmd="echo done", expect_exit_code=0)],
            ),
        )

        config = Config.default()
        config.watchdog.enabled = True
        config.execution.cleanup_on_success = True

        mock_adapter = MockAdapter(response_output="Created result.txt")
        mock_watchdog = MockWatchdog()

        runner = AgentEvalRunner(
            config=config,
            agent=mock_adapter,
            watchdog=mock_watchdog,
        )

        result = runner.run_scenario(scenario)

        # Generate report
        reporter = Reporter()
        report = reporter.generate([result])

        # Verify full flow worked
        assert result.passed
        assert mock_adapter.call_count == 1
        assert mock_watchdog.call_count == 1
        assert report.passed == 1
        assert report.pass_rate == 100.0

    def test_multiple_scenarios_with_mixed_results(self):
        """Test running multiple scenarios with mixed results."""
        scenarios = [
            Scenario(
                id="pass-001",
                name="Passing",
                description="Test",
                prompt="Do something",
                verification=VerificationSpec(
                    commands=[CommandCheck(cmd="echo pass", expect_exit_code=0)],
                ),
            ),
            Scenario(
                id="fail-001",
                name="Failing",
                description="Test",
                prompt="Do something",
                verification=VerificationSpec(
                    commands=[CommandCheck(cmd="exit 1", expect_exit_code=0)],
                ),
            ),
        ]

        config = Config.default()
        config.watchdog.enabled = False

        runner = AgentEvalRunner(
            config=config,
            agent=MockAdapter(),
        )

        results = runner.run_scenarios(scenarios)

        # Generate reports
        reporter = Reporter()
        report = reporter.generate(results)

        assert report.total_scenarios == 2
        assert report.passed == 1
        assert report.failed == 1
        assert report.pass_rate == 50.0

        # Test markdown output
        md = reporter.to_markdown(report)
        assert "pass-001" in md
        assert "fail-001" in md
