"""
Results collector for Jungle Gym.

Collects and structures data from agent runs for comparison.
"""

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class DoneReport:
    """Parsed DONE_REPORT from agent output."""
    raw: str
    changed_files: List[str] = field(default_factory=list)
    commands_run: List[Dict[str, Any]] = field(default_factory=list)
    test_output: str = ""
    invariants: str = ""
    next_actions: List[str] = field(default_factory=list)
    present: bool = False


@dataclass
class AuditResult:
    """Result from audit_done.py."""
    status: str  # VERIFIED, DISCREPANCY, NO_DONE_REPORT
    issues: List[str] = field(default_factory=list)
    raw_output: str = ""


@dataclass
class AgentResult:
    """Complete result from a single agent run."""
    agent_name: str
    scenario_id: str
    start_time: datetime
    end_time: Optional[datetime] = None
    duration_seconds: float = 0.0

    # State
    final_state: str = "unknown"  # ready, working, circuit_open, requires_human
    circuit_state: str = "closed"
    audit_fail_streak: int = 0

    # Outputs
    done_report: Optional[DoneReport] = None
    audit_result: Optional[AuditResult] = None

    # Logs
    log_events: List[Dict[str, Any]] = field(default_factory=list)
    transcript_tail: str = ""  # Last N lines of transcript

    # Metrics
    tool_calls: int = 0
    git_changes_made: bool = False
    tests_run: bool = False
    tests_passed: Optional[bool] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "agent_name": self.agent_name,
            "scenario_id": self.scenario_id,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_seconds": self.duration_seconds,
            "final_state": self.final_state,
            "circuit_state": self.circuit_state,
            "audit_fail_streak": self.audit_fail_streak,
            "done_report": {
                "present": self.done_report.present if self.done_report else False,
                "changed_files": self.done_report.changed_files if self.done_report else [],
                "test_output": self.done_report.test_output if self.done_report else "",
            } if self.done_report else None,
            "audit_result": {
                "status": self.audit_result.status,
                "issues": self.audit_result.issues,
            } if self.audit_result else None,
            "metrics": {
                "tool_calls": self.tool_calls,
                "git_changes_made": self.git_changes_made,
                "tests_run": self.tests_run,
                "tests_passed": self.tests_passed,
            },
        }


class ResultCollector:
    """Collects results from agent runs."""

    def __init__(self, state_path: Path, logs_dir: Path):
        self.state_path = state_path
        self.logs_dir = logs_dir

    def collect(
        self,
        agent_id: str,
        agent_name: str,
        scenario_id: str,
        start_time: datetime,
        transcript_path: Optional[Path] = None,
    ) -> AgentResult:
        """Collect all relevant data from an agent's run."""
        result = AgentResult(
            agent_name=agent_name,
            scenario_id=scenario_id,
            start_time=start_time,
        )

        # Get current time
        result.end_time = datetime.now()
        result.duration_seconds = (result.end_time - start_time).total_seconds()

        # Load state
        state = self._load_state()
        agent_state = state.get("agents", {}).get(agent_id, {})

        result.circuit_state = agent_state.get("circuit_state", "closed")
        result.audit_fail_streak = agent_state.get("audit_fail_streak", 0)

        # Determine final state
        if agent_state.get("circuit_state") == "open":
            result.final_state = "circuit_open"
        elif agent_state.get("audit_fail_streak", 0) >= 2:
            result.final_state = "requires_human"
        elif agent_state.get("awaiting_done_report"):
            result.final_state = "awaiting_done_report"
        else:
            result.final_state = "ready"

        # Parse transcript if available
        if transcript_path and transcript_path.exists():
            result.done_report = self._extract_done_report(transcript_path)
            result.transcript_tail = self._get_transcript_tail(transcript_path)
            result.tool_calls = self._count_tool_calls(transcript_path)
            result.tests_run, result.tests_passed = self._check_test_results(transcript_path)

        # Get log events
        result.log_events = self._get_log_events(agent_id, start_time)

        # Check git changes
        result.git_changes_made = self._check_git_changes(agent_state)

        return result

    def _load_state(self) -> Dict[str, Any]:
        """Load dispatcher state."""
        if not self.state_path.exists():
            return {}
        try:
            with open(self.state_path) as f:
                return json.load(f)
        except json.JSONDecodeError:
            return {}

    def _extract_done_report(self, transcript_path: Path) -> DoneReport:
        """Extract DONE_REPORT from transcript."""
        report = DoneReport(raw="", present=False)

        try:
            # Read last 500KB of transcript (tail-bytes approach)
            file_size = transcript_path.stat().st_size
            read_size = min(500_000, file_size)

            with open(transcript_path, "rb") as f:
                if file_size > read_size:
                    f.seek(file_size - read_size)
                content = f.read().decode("utf-8", errors="ignore")

            # Find DONE_REPORT
            match = re.search(r"DONE_REPORT:(.*?)(?=\n\n|\Z)", content, re.DOTALL)
            if match:
                report.raw = match.group(0)
                report.present = True

                # Parse fields
                report.changed_files = re.findall(r"changed_files:\s*\[(.*?)\]", report.raw)
                test_match = re.search(r"test_output:\s*[\"']?(.*?)[\"']?\s*$", report.raw, re.MULTILINE)
                if test_match:
                    report.test_output = test_match.group(1)

                inv_match = re.search(r"invariants:\s*[\"']?(.*?)[\"']?\s*$", report.raw, re.MULTILINE)
                if inv_match:
                    report.invariants = inv_match.group(1)

        except Exception:
            pass

        return report

    def _get_transcript_tail(self, transcript_path: Path, lines: int = 50) -> str:
        """Get last N lines of transcript."""
        try:
            with open(transcript_path) as f:
                all_lines = f.readlines()
                return "".join(all_lines[-lines:])
        except Exception:
            return ""

    def _count_tool_calls(self, transcript_path: Path) -> int:
        """Count tool calls in transcript."""
        count = 0
        try:
            with open(transcript_path) as f:
                for line in f:
                    try:
                        entry = json.loads(line)
                        if entry.get("type") == "tool_use":
                            count += 1
                    except json.JSONDecodeError:
                        continue
        except Exception:
            pass
        return count

    def _check_test_results(self, transcript_path: Path) -> tuple[bool, Optional[bool]]:
        """Check if tests were run and if they passed."""
        tests_run = False
        tests_passed = None

        try:
            with open(transcript_path) as f:
                content = f.read()

            # Look for pytest output
            if "pytest" in content.lower() or "test" in content.lower():
                tests_run = True

                # Check for pass/fail indicators
                if re.search(r"\d+ passed", content):
                    if not re.search(r"\d+ failed", content):
                        tests_passed = True
                    else:
                        tests_passed = False
                elif re.search(r"FAILED|ERROR", content):
                    tests_passed = False

        except Exception:
            pass

        return tests_run, tests_passed

    def _get_log_events(self, agent_id: str, start_time: datetime) -> List[Dict[str, Any]]:
        """Get log events for this agent since start_time."""
        events = []

        # Find today's log file
        today = datetime.now().strftime("%Y-%m-%d")
        log_file = self.logs_dir / f"{today}.jsonl"

        if not log_file.exists():
            return events

        try:
            with open(log_file) as f:
                for line in f:
                    try:
                        entry = json.loads(line)
                        if entry.get("agent_id") == int(agent_id):
                            event_time = datetime.fromisoformat(entry.get("ts", ""))
                            if event_time >= start_time:
                                events.append(entry)
                    except (json.JSONDecodeError, ValueError):
                        continue
        except Exception:
            pass

        return events

    def _check_git_changes(self, agent_state: Dict[str, Any]) -> bool:
        """Check if agent made git changes."""
        # This is a simplification - in practice we'd check the actual worktree
        return agent_state.get("no_progress_streak", 0) == 0


def run_audit(transcript_path: Path, scripts_dir: Path) -> AuditResult:
    """Run audit_done.py on a transcript."""
    import subprocess
    import sys

    result = AuditResult(status="ERROR", issues=[], raw_output="")

    audit_script = scripts_dir / "audit_done.py"
    if not audit_script.exists():
        result.issues.append("audit_done.py not found")
        return result

    try:
        proc = subprocess.run(
            [sys.executable, str(audit_script), "--transcript", str(transcript_path), "--json"],
            capture_output=True,
            text=True,
            timeout=30,
        )

        result.raw_output = proc.stdout

        if proc.returncode == 0:
            try:
                data = json.loads(proc.stdout)
                result.status = data.get("status", "UNKNOWN")
                result.issues = data.get("issues", [])
            except json.JSONDecodeError:
                result.status = "VERIFIED" if "verified" in proc.stdout.lower() else "ERROR"
        else:
            result.status = "DISCREPANCY"
            result.issues = [proc.stderr] if proc.stderr else ["Unknown error"]

    except subprocess.TimeoutExpired:
        result.status = "TIMEOUT"
        result.issues = ["Audit timed out after 30 seconds"]
    except Exception as e:
        result.status = "ERROR"
        result.issues = [str(e)]

    return result
