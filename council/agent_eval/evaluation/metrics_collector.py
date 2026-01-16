"""
Metrics collection for Agent Eval.

Collects quantitative metrics from scenario runs including
timing, token usage, costs, and verification results.
"""

from datetime import datetime
from typing import Optional
import logging

from ..models.scenario import Scenario
from ..models.result import Metrics, VerificationResult, ResultStatus
from ..execution.agent_adapter import AgentResponse

logger = logging.getLogger(__name__)


class MetricsCollector:
    """Collects quantitative metrics from scenario runs.

    Gathers timing, token usage, costs, and verification results
    into a Metrics object for analysis and persistence.

    Usage:
        collector = MetricsCollector()
        metrics = collector.collect(
            scenario=scenario,
            agent_response=response,
            verification_result=verification,
            start_time=start,
            end_time=end,
        )
        print(f"Duration: {metrics.duration_seconds}s")
        print(f"Cost: ${metrics.agent_cost_usd}")
    """

    def collect(
        self,
        scenario: Scenario,
        agent_response: AgentResponse,
        verification_result: VerificationResult,
        start_time: datetime,
        end_time: datetime,
        retries: int = 0,
    ) -> Metrics:
        """Collect metrics from a scenario run.

        Args:
            scenario: The scenario that was run
            agent_response: Response from the agent
            verification_result: Results of verification
            start_time: When the run started
            end_time: When the run ended
            retries: Number of retry attempts made

        Returns:
            Metrics object with all collected data
        """
        # Determine status
        status = self._determine_status(agent_response, verification_result)

        # Calculate duration
        duration = (end_time - start_time).total_seconds()

        return Metrics(
            scenario_id=scenario.id,
            start_time=start_time,
            end_time=end_time,
            duration_seconds=duration,
            status=status,
            verification_passed=verification_result.passed,
            checks_passed=verification_result.passed_count,
            checks_total=verification_result.total_count,
            agent_tokens_input=agent_response.tokens_input,
            agent_tokens_output=agent_response.tokens_output,
            agent_cost_usd=agent_response.cost_usd,
            retries=retries,
        )

    def _determine_status(
        self,
        agent_response: AgentResponse,
        verification_result: VerificationResult,
    ) -> ResultStatus:
        """Determine the overall status of a run.

        Args:
            agent_response: Response from agent
            verification_result: Verification results

        Returns:
            ResultStatus enum value
        """
        # Check for errors first
        if agent_response.error:
            # Check if it was a timeout
            if "timeout" in agent_response.error.lower():
                return ResultStatus.TIMEOUT
            return ResultStatus.ERROR

        # Check verification result
        if verification_result.passed:
            return ResultStatus.PASSED
        else:
            return ResultStatus.FAILED

    def collect_from_error(
        self,
        scenario: Scenario,
        start_time: datetime,
        error: str,
        status: ResultStatus = ResultStatus.ERROR,
    ) -> Metrics:
        """Collect metrics from an error case.

        Args:
            scenario: The scenario that was attempted
            start_time: When the run started
            error: Error message
            status: Status to assign (ERROR or TIMEOUT)

        Returns:
            Metrics object for the failed run
        """
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        return Metrics(
            scenario_id=scenario.id,
            start_time=start_time,
            end_time=end_time,
            duration_seconds=duration,
            status=status,
            verification_passed=False,
            checks_passed=0,
            checks_total=0,
        )


class MetricsAggregator:
    """Aggregates metrics across multiple runs.

    Useful for analyzing performance across a test suite.
    """

    def __init__(self):
        """Initialize aggregator."""
        self.metrics_list: list = []

    def add(self, metrics: Metrics) -> None:
        """Add metrics from a run.

        Args:
            metrics: Metrics to add
        """
        self.metrics_list.append(metrics)

    @property
    def total_runs(self) -> int:
        """Total number of runs."""
        return len(self.metrics_list)

    @property
    def passed_runs(self) -> int:
        """Number of passed runs."""
        return sum(1 for m in self.metrics_list if m.status == ResultStatus.PASSED)

    @property
    def failed_runs(self) -> int:
        """Number of failed runs."""
        return sum(1 for m in self.metrics_list if m.status == ResultStatus.FAILED)

    @property
    def error_runs(self) -> int:
        """Number of error runs."""
        return sum(1 for m in self.metrics_list if m.status == ResultStatus.ERROR)

    @property
    def timeout_runs(self) -> int:
        """Number of timeout runs."""
        return sum(1 for m in self.metrics_list if m.status == ResultStatus.TIMEOUT)

    @property
    def pass_rate(self) -> float:
        """Pass rate as percentage (0-100)."""
        if self.total_runs == 0:
            return 0.0
        return (self.passed_runs / self.total_runs) * 100

    @property
    def total_duration(self) -> float:
        """Total duration in seconds."""
        return sum(m.duration_seconds for m in self.metrics_list)

    @property
    def avg_duration(self) -> float:
        """Average duration per run in seconds."""
        if self.total_runs == 0:
            return 0.0
        return self.total_duration / self.total_runs

    @property
    def total_cost(self) -> float:
        """Total cost in USD."""
        return sum(m.agent_cost_usd or 0 for m in self.metrics_list)

    @property
    def total_tokens_input(self) -> int:
        """Total input tokens."""
        return sum(m.agent_tokens_input or 0 for m in self.metrics_list)

    @property
    def total_tokens_output(self) -> int:
        """Total output tokens."""
        return sum(m.agent_tokens_output or 0 for m in self.metrics_list)

    @property
    def total_retries(self) -> int:
        """Total retry attempts."""
        return sum(m.retries for m in self.metrics_list)

    def summary(self) -> dict:
        """Get summary statistics.

        Returns:
            Dict with aggregated statistics
        """
        return {
            "total_runs": self.total_runs,
            "passed": self.passed_runs,
            "failed": self.failed_runs,
            "errors": self.error_runs,
            "timeouts": self.timeout_runs,
            "pass_rate": f"{self.pass_rate:.1f}%",
            "total_duration_seconds": round(self.total_duration, 2),
            "avg_duration_seconds": round(self.avg_duration, 2),
            "total_cost_usd": round(self.total_cost, 4),
            "total_tokens_input": self.total_tokens_input,
            "total_tokens_output": self.total_tokens_output,
            "total_retries": self.total_retries,
        }

    def by_scenario(self) -> dict:
        """Get metrics grouped by scenario.

        Returns:
            Dict mapping scenario_id to list of metrics
        """
        result = {}
        for m in self.metrics_list:
            if m.scenario_id not in result:
                result[m.scenario_id] = []
            result[m.scenario_id].append(m)
        return result

    def scenario_summary(self, scenario_id: str) -> Optional[dict]:
        """Get summary for a specific scenario.

        Args:
            scenario_id: ID of scenario

        Returns:
            Summary dict or None if no runs for scenario
        """
        scenario_metrics = [m for m in self.metrics_list if m.scenario_id == scenario_id]
        if not scenario_metrics:
            return None

        passed = sum(1 for m in scenario_metrics if m.status == ResultStatus.PASSED)
        total = len(scenario_metrics)

        return {
            "scenario_id": scenario_id,
            "runs": total,
            "passed": passed,
            "pass_rate": f"{(passed/total)*100:.1f}%" if total > 0 else "0%",
            "avg_duration": round(
                sum(m.duration_seconds for m in scenario_metrics) / total, 2
            ),
        }
