"""
Report generation for Agent Eval.

Generates human-readable and machine-readable reports
from evaluation results.
"""

from dataclasses import dataclass, asdict
from datetime import datetime
from typing import List, Optional
import json
from statistics import mean

from ..models.result import RunResult, ResultStatus


@dataclass
class Report:
    """Summary report of evaluation runs.

    Contains aggregate statistics and individual results.
    """

    timestamp: datetime
    total_scenarios: int
    passed: int
    failed: int
    errors: int
    timeouts: int
    pass_rate: float
    avg_duration_seconds: float
    total_duration_seconds: float
    results: List[RunResult]
    patterns_identified: List[str]

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "total_scenarios": self.total_scenarios,
            "passed": self.passed,
            "failed": self.failed,
            "errors": self.errors,
            "timeouts": self.timeouts,
            "pass_rate": round(self.pass_rate, 2),
            "avg_duration_seconds": round(self.avg_duration_seconds, 2),
            "total_duration_seconds": round(self.total_duration_seconds, 2),
            "patterns_identified": self.patterns_identified,
            "results": [r.to_dict() for r in self.results],
        }


class Reporter:
    """Generates reports from evaluation results.

    Supports multiple output formats:
    - JSON (for programmatic consumption)
    - Markdown (for human reading)
    - Summary (brief console output)

    Usage:
        reporter = Reporter()
        report = reporter.generate(results)
        print(reporter.to_markdown(report))
    """

    def generate(self, results: List[RunResult]) -> Report:
        """Generate a summary report from results.

        Args:
            results: List of run results

        Returns:
            Report with aggregate statistics
        """
        if not results:
            return Report(
                timestamp=datetime.now(),
                total_scenarios=0,
                passed=0,
                failed=0,
                errors=0,
                timeouts=0,
                pass_rate=0.0,
                avg_duration_seconds=0.0,
                total_duration_seconds=0.0,
                results=[],
                patterns_identified=[],
            )

        # Count by status
        passed = sum(1 for r in results if r.status == ResultStatus.PASSED)
        failed = sum(1 for r in results if r.status == ResultStatus.FAILED)
        errors = sum(1 for r in results if r.status == ResultStatus.ERROR)
        timeouts = sum(1 for r in results if r.status == ResultStatus.TIMEOUT)
        total = len(results)

        # Calculate durations
        durations = [r.metrics.duration_seconds for r in results]
        total_duration = sum(durations)
        avg_duration = mean(durations) if durations else 0.0

        # Aggregate patterns from watchdog
        patterns = []
        for r in results:
            if r.watchdog:
                patterns.extend(r.watchdog.failure_patterns)

        # Deduplicate patterns
        unique_patterns = list(set(patterns))

        return Report(
            timestamp=datetime.now(),
            total_scenarios=total,
            passed=passed,
            failed=failed,
            errors=errors,
            timeouts=timeouts,
            pass_rate=(passed / total * 100) if total > 0 else 0,
            avg_duration_seconds=avg_duration,
            total_duration_seconds=total_duration,
            results=results,
            patterns_identified=unique_patterns,
        )

    def to_json(self, report: Report, indent: int = 2) -> str:
        """Export report as JSON.

        Args:
            report: Report to export
            indent: JSON indentation

        Returns:
            JSON string
        """
        return json.dumps(report.to_dict(), indent=indent, default=str)

    def to_markdown(self, report: Report) -> str:
        """Export report as Markdown.

        Args:
            report: Report to export

        Returns:
            Markdown string
        """
        md = f"""# Agent Eval Report

**Generated:** {report.timestamp.strftime("%Y-%m-%d %H:%M:%S")}

## Summary

| Metric | Value |
|--------|-------|
| Total Scenarios | {report.total_scenarios} |
| Passed | {report.passed} |
| Failed | {report.failed} |
| Errors | {report.errors} |
| Timeouts | {report.timeouts} |
| **Pass Rate** | **{report.pass_rate:.1f}%** |
| Avg Duration | {report.avg_duration_seconds:.1f}s |
| Total Duration | {report.total_duration_seconds:.1f}s |

## Results by Scenario

| ID | Name | Status | Duration | Checks |
|----|------|--------|----------|--------|
"""
        for r in report.results:
            status_emoji = {
                ResultStatus.PASSED: "✅",
                ResultStatus.FAILED: "❌",
                ResultStatus.ERROR: "💥",
                ResultStatus.TIMEOUT: "⏱️",
                ResultStatus.SKIPPED: "⏭️",
            }.get(r.status, "❓")

            md += (
                f"| {r.scenario_id} | {r.scenario_name} | "
                f"{status_emoji} {r.status.value} | "
                f"{r.metrics.duration_seconds:.1f}s | "
                f"{r.verification.summary()} |\n"
            )

        # Add failure details for failed scenarios
        failures = [r for r in report.results if not r.passed]
        if failures:
            md += """
## Failure Details

"""
            for r in failures:
                md += f"### {r.scenario_id}: {r.scenario_name}\n\n"
                if r.error:
                    md += f"**Error:** {r.error}\n\n"
                if r.verification.failures():
                    md += "**Failed checks:**\n"
                    for failure in r.verification.failures():
                        md += f"- {failure}\n"
                    md += "\n"
                if r.watchdog and r.watchdog.feedback_for_agent:
                    md += f"**Watchdog feedback:** {r.watchdog.feedback_for_agent}\n\n"

        # Add identified patterns
        if report.patterns_identified:
            md += """
## Failure Patterns Identified

"""
            for pattern in report.patterns_identified:
                md += f"- {pattern}\n"

        md += """
---
*Generated by Agent Eval System*
"""
        return md

    def to_summary(self, report: Report) -> str:
        """Generate brief summary for console output.

        Args:
            report: Report to summarize

        Returns:
            Brief summary string
        """
        status_emoji = "✅" if report.passed == report.total_scenarios else "❌"

        lines = [
            f"\n{status_emoji} Agent Eval Results",
            f"   Passed: {report.passed}/{report.total_scenarios} ({report.pass_rate:.1f}%)",
        ]

        if report.failed > 0:
            lines.append(f"   Failed: {report.failed}")
        if report.errors > 0:
            lines.append(f"   Errors: {report.errors}")
        if report.timeouts > 0:
            lines.append(f"   Timeouts: {report.timeouts}")

        lines.append(f"   Duration: {report.total_duration_seconds:.1f}s")

        if report.patterns_identified:
            lines.append(f"\n   Patterns identified: {len(report.patterns_identified)}")
            for pattern in report.patterns_identified[:3]:
                lines.append(f"   - {pattern[:60]}...")

        return "\n".join(lines)


class ComparisonReporter:
    """Generate comparison reports between two runs.

    Useful for tracking improvements/regressions over time.
    """

    def compare(self, baseline: Report, current: Report) -> dict:
        """Compare two reports.

        Args:
            baseline: Previous/baseline report
            current: Current report to compare

        Returns:
            Dict with comparison data
        """
        pass_rate_delta = current.pass_rate - baseline.pass_rate
        duration_delta = current.avg_duration_seconds - baseline.avg_duration_seconds

        # Find regressions (passed -> failed)
        baseline_passed = {r.scenario_id for r in baseline.results if r.passed}
        current_passed = {r.scenario_id for r in current.results if r.passed}

        regressions = baseline_passed - current_passed
        improvements = current_passed - baseline_passed

        return {
            "baseline_pass_rate": baseline.pass_rate,
            "current_pass_rate": current.pass_rate,
            "pass_rate_delta": round(pass_rate_delta, 2),
            "improved": pass_rate_delta > 0,
            "baseline_avg_duration": baseline.avg_duration_seconds,
            "current_avg_duration": current.avg_duration_seconds,
            "duration_delta": round(duration_delta, 2),
            "faster": duration_delta < 0,
            "regressions": list(regressions),
            "improvements": list(improvements),
            "new_patterns": [
                p for p in current.patterns_identified
                if p not in baseline.patterns_identified
            ],
        }

    def to_markdown(self, comparison: dict) -> str:
        """Generate comparison report as Markdown.

        Args:
            comparison: Comparison dict from compare()

        Returns:
            Markdown string
        """
        trend = "📈" if comparison["improved"] else "📉"
        speed = "🚀" if comparison["faster"] else "🐌"

        md = f"""# Agent Eval Comparison Report

## Pass Rate
{trend} **{comparison['current_pass_rate']:.1f}%** (was {comparison['baseline_pass_rate']:.1f}%, delta: {comparison['pass_rate_delta']:+.1f}%)

## Duration
{speed} **{comparison['current_avg_duration']:.1f}s** avg (was {comparison['baseline_avg_duration']:.1f}s, delta: {comparison['duration_delta']:+.1f}s)
"""

        if comparison["regressions"]:
            md += f"""
## ⚠️ Regressions ({len(comparison['regressions'])})
"""
            for scenario_id in comparison["regressions"]:
                md += f"- {scenario_id}\n"

        if comparison["improvements"]:
            md += f"""
## ✅ Improvements ({len(comparison['improvements'])})
"""
            for scenario_id in comparison["improvements"]:
                md += f"- {scenario_id}\n"

        if comparison["new_patterns"]:
            md += f"""
## 🔍 New Patterns Identified
"""
            for pattern in comparison["new_patterns"]:
                md += f"- {pattern}\n"

        return md
