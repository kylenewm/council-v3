"""
Result data models for Agent Eval system.

These capture the outcomes of scenario runs, including:
- Verification check results (commands, files)
- Watchdog (LLM) evaluation results
- Quantitative metrics
- Overall run results
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict, Any


class ResultStatus(Enum):
    """Overall status of a scenario run."""

    PASSED = "passed"  # All verification checks passed
    FAILED = "failed"  # One or more verification checks failed
    ERROR = "error"  # Execution error (not a test failure)
    TIMEOUT = "timeout"  # Agent execution timed out
    SKIPPED = "skipped"  # Scenario was skipped (e.g., filtered out)


@dataclass
class CommandResult:
    """Result of a command verification check.

    Captures what the command returned and whether it met expectations.
    """

    cmd: str
    exit_code: int
    expected_exit_code: int
    stdout: str
    stderr: str
    passed: bool
    duration_seconds: float
    error: Optional[str] = None

    def __str__(self) -> str:
        status = "PASS" if self.passed else "FAIL"
        return f"[{status}] {self.cmd} (exit={self.exit_code}, expected={self.expected_exit_code})"


@dataclass
class FileResult:
    """Result of a file verification check.

    Captures whether the file met expectations.
    """

    path: str
    exists: bool
    expected_exists: bool
    contains_check: Optional[str] = None
    contains_found: bool = True
    passed: bool = True
    error: Optional[str] = None

    def __str__(self) -> str:
        status = "PASS" if self.passed else "FAIL"
        return f"[{status}] {self.path} (exists={self.exists})"


@dataclass
class VerificationResult:
    """Combined result of all verification checks.

    Aggregates command and file check results.
    """

    command_results: List[CommandResult] = field(default_factory=list)
    file_results: List[FileResult] = field(default_factory=list)
    custom_result: Optional[Dict[str, Any]] = None
    passed: bool = False
    error: Optional[str] = None

    @property
    def all_checks(self) -> List:
        """Get all check results as a single list."""
        return self.command_results + self.file_results

    @property
    def passed_count(self) -> int:
        """Number of checks that passed."""
        return sum(1 for c in self.all_checks if c.passed)

    @property
    def failed_count(self) -> int:
        """Number of checks that failed."""
        return sum(1 for c in self.all_checks if not c.passed)

    @property
    def total_count(self) -> int:
        """Total number of checks."""
        return len(self.all_checks)

    def summary(self) -> str:
        """Human-readable summary of check results."""
        return f"{self.passed_count}/{self.total_count} checks passed"

    def failures(self) -> List[str]:
        """Get list of failure messages."""
        failures = []
        for r in self.command_results:
            if not r.passed:
                failures.append(f"Command failed: {r.cmd} (exit={r.exit_code})")
        for r in self.file_results:
            if not r.passed:
                if not r.exists and r.expected_exists:
                    failures.append(f"File missing: {r.path}")
                elif r.contains_check and not r.contains_found:
                    failures.append(f"File {r.path} missing content: {r.contains_check[:50]}...")
                else:
                    failures.append(f"File check failed: {r.path}")
        return failures


@dataclass
class WatchdogResult:
    """Result of LLM watchdog evaluation.

    The watchdog evaluates the quality of the agent's work,
    providing qualitative feedback beyond pass/fail.
    """

    # Quality assessments
    understanding: str  # "good", "partial", "poor", "error", "skipped"
    approach: str  # "appropriate", "over-engineered", "insufficient", "error"

    # Identified patterns
    shortcuts_taken: List[str] = field(default_factory=list)
    failure_patterns: List[str] = field(default_factory=list)
    success_patterns: List[str] = field(default_factory=list)

    # Feedback
    feedback_for_agent: str = ""
    suggested_scenarios: List[str] = field(default_factory=list)

    # Meta
    confidence: float = 0.0  # 0.0 to 1.0
    raw_response: str = ""
    error: Optional[str] = None

    @property
    def is_valid(self) -> bool:
        """Check if watchdog evaluation completed successfully."""
        return self.error is None and self.understanding not in ("error", "skipped")

    def summary(self) -> str:
        """Human-readable summary."""
        if self.error:
            return f"Watchdog error: {self.error}"
        return f"Understanding: {self.understanding}, Approach: {self.approach}"


@dataclass
class Metrics:
    """Quantitative metrics for a scenario run.

    These are hard numbers, as opposed to the qualitative
    assessments from the watchdog.
    """

    scenario_id: str
    start_time: datetime
    end_time: datetime
    duration_seconds: float
    status: ResultStatus
    verification_passed: bool
    checks_passed: int
    checks_total: int

    # Optional token/cost tracking
    agent_tokens_input: Optional[int] = None
    agent_tokens_output: Optional[int] = None
    agent_cost_usd: Optional[float] = None
    watchdog_tokens: Optional[int] = None

    # Execution metadata
    retries: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "scenario_id": self.scenario_id,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat(),
            "duration_seconds": self.duration_seconds,
            "status": self.status.value,
            "verification_passed": self.verification_passed,
            "checks_passed": self.checks_passed,
            "checks_total": self.checks_total,
            "agent_tokens_input": self.agent_tokens_input,
            "agent_tokens_output": self.agent_tokens_output,
            "agent_cost_usd": self.agent_cost_usd,
            "watchdog_tokens": self.watchdog_tokens,
            "retries": self.retries,
        }


@dataclass
class RunResult:
    """Complete result of a scenario run.

    This is the main output of running a scenario. It contains:
    - Basic info (scenario ID, run ID, timestamp)
    - Status (passed, failed, error, timeout)
    - Verification results (all the checks)
    - Metrics (timing, tokens, cost)
    - Watchdog evaluation (if enabled)
    - Agent output (what the agent produced)
    - Errors (if any)
    """

    # Identification
    scenario_id: str
    scenario_name: str
    run_id: str
    timestamp: datetime

    # Results
    status: ResultStatus
    verification: VerificationResult
    metrics: Metrics

    # Optional
    watchdog: Optional[WatchdogResult] = None
    agent_output: str = ""
    error: Optional[str] = None

    @property
    def passed(self) -> bool:
        """Check if the run passed (verification + no errors)."""
        return self.status == ResultStatus.PASSED and self.verification.passed

    def summary(self) -> str:
        """Human-readable summary."""
        status_emoji = {
            ResultStatus.PASSED: "✅",
            ResultStatus.FAILED: "❌",
            ResultStatus.ERROR: "💥",
            ResultStatus.TIMEOUT: "⏱️",
            ResultStatus.SKIPPED: "⏭️",
        }
        emoji = status_emoji.get(self.status, "❓")
        return (
            f"{emoji} [{self.scenario_id}] {self.scenario_name}: "
            f"{self.status.value} ({self.verification.summary()})"
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "scenario_id": self.scenario_id,
            "scenario_name": self.scenario_name,
            "run_id": self.run_id,
            "timestamp": self.timestamp.isoformat(),
            "status": self.status.value,
            "verification": {
                "passed": self.verification.passed,
                "summary": self.verification.summary(),
                "failures": self.verification.failures(),
            },
            "metrics": self.metrics.to_dict(),
            "watchdog": {
                "understanding": self.watchdog.understanding,
                "approach": self.watchdog.approach,
                "feedback": self.watchdog.feedback_for_agent,
                "failure_patterns": self.watchdog.failure_patterns,
            }
            if self.watchdog
            else None,
            "agent_output_length": len(self.agent_output),
            "error": self.error,
        }
