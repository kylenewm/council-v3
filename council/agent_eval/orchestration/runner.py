"""
Main runner for Agent Eval.

The AgentEvalRunner orchestrates the entire evaluation process:
1. Set up environment
2. Execute agent
3. Run verification
4. Collect metrics
5. Run watchdog evaluation
6. Return results
"""

from datetime import datetime
from pathlib import Path
from typing import Optional, List
import uuid
import logging

from ..config import Config
from ..models.scenario import Scenario
from ..models.result import RunResult, ResultStatus, VerificationResult, Metrics
from ..execution.environment import Environment
from ..execution.claude_adapter import ClaudeAdapter
from ..execution.agent_adapter import AgentAdapter, MockAdapter
from ..execution.retry_manager import RetryManager
from ..evaluation.verifier import Verifier
from ..evaluation.watchdog import Watchdog, MockWatchdog
from ..evaluation.metrics_collector import MetricsCollector
from ..exceptions import AgentEvalError, TimeoutError

logger = logging.getLogger(__name__)


class AgentEvalRunner:
    """Main runner for agent evaluation.

    Orchestrates the full evaluation pipeline for scenarios.

    Usage:
        runner = AgentEvalRunner()
        result = runner.run_scenario(scenario)
        print(result.summary())

        # Or run multiple scenarios
        results = runner.run_scenarios(scenarios)
        for r in results:
            print(r.summary())

    Attributes:
        config: Configuration for the runner
        agent: Agent adapter (Claude by default)
        verifier: Verification runner
        watchdog: LLM watchdog evaluator
        metrics: Metrics collector
    """

    def __init__(
        self,
        config: Optional[Config] = None,
        agent: Optional[AgentAdapter] = None,
        watchdog: Optional[Watchdog] = None,
    ):
        """Initialize runner.

        Args:
            config: Configuration (uses defaults if not provided)
            agent: Agent adapter (uses ClaudeAdapter if not provided)
            watchdog: Watchdog evaluator (uses Watchdog if not provided)
        """
        self.config = config or Config.default()

        # Set up agent adapter
        if agent is not None:
            self.agent = agent
        else:
            self.agent = ClaudeAdapter(self.config.agent)

        # Set up other components
        self.verifier = Verifier()
        self.watchdog = watchdog or Watchdog(self.config.watchdog)
        self.metrics = MetricsCollector()
        self.retry_manager = RetryManager(self.config.agent)

    def run_scenario(self, scenario: Scenario) -> RunResult:
        """Run a single scenario.

        Args:
            scenario: The scenario to run

        Returns:
            RunResult with all results and metrics
        """
        run_id = str(uuid.uuid4())[:8]
        start_time = datetime.now()

        logger.info(f"[{run_id}] Running scenario: {scenario.id} - {scenario.name}")

        # Create environment
        env = Environment(scenario, self.config.execution)
        verification_result: Optional[VerificationResult] = None

        try:
            # Setup environment
            workdir = env.setup()
            logger.debug(f"[{run_id}] Environment setup complete: {workdir}")

            # Determine timeout
            timeout = scenario.timeout_override or self.config.agent.timeout_seconds

            # Execute agent with retry (only retry transient errors, not timeouts/explicit errors)
            def execute():
                return self.agent.execute(scenario.prompt, workdir, timeout)

            agent_response = self.retry_manager.execute_with_retry(
                execute,
                operation_name=f"scenario {scenario.id}",
                retryable_exceptions=(ConnectionError, OSError),  # Transient only
            )
            logger.debug(f"[{run_id}] Agent execution complete")

            # Run verification
            verification_result = self.verifier.verify(scenario.verification, workdir)
            logger.debug(
                f"[{run_id}] Verification: {'PASSED' if verification_result.passed else 'FAILED'}"
            )

            # Collect metrics
            end_time = datetime.now()
            metrics = self.metrics.collect(
                scenario=scenario,
                agent_response=agent_response,
                verification_result=verification_result,
                start_time=start_time,
                end_time=end_time,
            )

            # Run watchdog evaluation
            watchdog_result = None
            if self.config.watchdog.enabled:
                try:
                    watchdog_result = self.watchdog.evaluate(
                        scenario=scenario,
                        agent_output=agent_response.output,
                        verification_result=verification_result,
                    )
                    logger.debug(f"[{run_id}] Watchdog evaluation complete")
                except Exception as e:
                    logger.warning(f"[{run_id}] Watchdog evaluation failed: {e}")

            # Determine final status
            status = ResultStatus.PASSED if verification_result.passed else ResultStatus.FAILED

            result = RunResult(
                scenario_id=scenario.id,
                scenario_name=scenario.name,
                run_id=run_id,
                timestamp=start_time,
                status=status,
                verification=verification_result,
                metrics=metrics,
                watchdog=watchdog_result,
                agent_output=agent_response.output,
            )

            logger.info(f"[{run_id}] {result.summary()}")
            return result

        except TimeoutError as e:
            logger.error(f"[{run_id}] Timeout: {e}")
            return self._error_result(
                scenario, run_id, start_time, ResultStatus.TIMEOUT, str(e)
            )

        except AgentEvalError as e:
            logger.error(f"[{run_id}] Error: {e}")
            return self._error_result(
                scenario, run_id, start_time, ResultStatus.ERROR, str(e)
            )

        except Exception as e:
            logger.exception(f"[{run_id}] Unexpected error: {e}")
            return self._error_result(
                scenario, run_id, start_time, ResultStatus.ERROR, str(e)
            )

        finally:
            # Cleanup based on result
            should_cleanup = False
            if verification_result is not None:
                if verification_result.passed:
                    should_cleanup = self.config.execution.cleanup_on_success
                else:
                    should_cleanup = self.config.execution.cleanup_on_failure
            else:
                # Error case - use cleanup_on_failure
                should_cleanup = self.config.execution.cleanup_on_failure

            if should_cleanup:
                env.cleanup()
            elif env._workdir:
                logger.info(f"[{run_id}] Keeping environment: {env._workdir}")

    def run_scenarios(self, scenarios: List[Scenario]) -> List[RunResult]:
        """Run multiple scenarios sequentially.

        Args:
            scenarios: List of scenarios to run

        Returns:
            List of RunResult objects
        """
        results = []
        total = len(scenarios)

        for i, scenario in enumerate(scenarios, 1):
            logger.info(f"Running scenario {i}/{total}: {scenario.name}")
            result = self.run_scenario(scenario)
            results.append(result)

            # Log progress
            passed = sum(1 for r in results if r.passed)
            logger.info(f"Progress: {passed}/{i} passed ({len(results)}/{total} complete)")

        return results

    def _error_result(
        self,
        scenario: Scenario,
        run_id: str,
        start_time: datetime,
        status: ResultStatus,
        error: str,
    ) -> RunResult:
        """Create an error result.

        Args:
            scenario: The scenario that failed
            run_id: Run identifier
            start_time: When the run started
            status: Error status
            error: Error message

        Returns:
            RunResult representing the error
        """
        end_time = datetime.now()

        return RunResult(
            scenario_id=scenario.id,
            scenario_name=scenario.name,
            run_id=run_id,
            timestamp=start_time,
            status=status,
            verification=VerificationResult(passed=False, error=error),
            metrics=Metrics(
                scenario_id=scenario.id,
                start_time=start_time,
                end_time=end_time,
                duration_seconds=(end_time - start_time).total_seconds(),
                status=status,
                verification_passed=False,
                checks_passed=0,
                checks_total=0,
            ),
            error=error,
        )


class DryRunner:
    """Dry run mode - validates scenarios without executing.

    Useful for validating scenario files before running actual tests.
    """

    def validate_scenario(self, scenario: Scenario) -> dict:
        """Validate a scenario without running it.

        Args:
            scenario: Scenario to validate

        Returns:
            Dict with validation results
        """
        issues = []

        # Check required fields
        if not scenario.prompt.strip():
            issues.append("Empty prompt")

        # Check verification has at least one check
        if scenario.verification.total_checks == 0:
            issues.append("No verification checks defined")

        # Check for potential issues
        for cmd in scenario.verification.commands:
            if not cmd.cmd.strip():
                issues.append("Empty verification command")

        for file_check in scenario.verification.files:
            if not file_check.path.strip():
                issues.append("Empty file path in verification")

        return {
            "scenario_id": scenario.id,
            "scenario_name": scenario.name,
            "valid": len(issues) == 0,
            "issues": issues,
            "setup_files": len(scenario.setup.files),
            "setup_commands": len(scenario.setup.commands),
            "verification_checks": scenario.verification.total_checks,
        }

    def validate_scenarios(self, scenarios: List[Scenario]) -> dict:
        """Validate multiple scenarios.

        Args:
            scenarios: List of scenarios to validate

        Returns:
            Dict with overall validation results
        """
        results = [self.validate_scenario(s) for s in scenarios]
        valid_count = sum(1 for r in results if r["valid"])

        return {
            "total": len(scenarios),
            "valid": valid_count,
            "invalid": len(scenarios) - valid_count,
            "results": results,
        }
