"""
Report generator for Jungle Gym.

Generates JSON (parseable) and Markdown (readable) reports.
"""

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

from .collector import AgentResult
from .scenarios import ExpectedOutcome, Scenario


@dataclass
class ScenarioResult:
    """Result of running a single scenario on both agents."""
    scenario: Scenario
    control_result: AgentResult
    experimental_result: AgentResult
    enforcement_caught: bool  # Did experimental catch something control didn't?
    expected_outcome_matched: bool  # Did results match expected?
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON."""
        return {
            "scenario_id": self.scenario.id,
            "scenario_name": self.scenario.name,
            "tier": self.scenario.tier.value,
            "expected_outcome": self.scenario.expected_outcome.value,
            "enforcement_caught": self.enforcement_caught,
            "expected_outcome_matched": self.expected_outcome_matched,
            "control": self.control_result.to_dict(),
            "experimental": self.experimental_result.to_dict(),
            "notes": self.notes,
        }


class Reporter:
    """Generates reports from test results."""

    def generate(
        self,
        results: List[ScenarioResult],
        config_summary: Dict[str, Any],
    ) -> Tuple[Dict[str, Any], str]:
        """Generate JSON and Markdown reports."""
        json_report = self._generate_json(results, config_summary)
        md_report = self._generate_markdown(results, config_summary)
        return json_report, md_report

    def _generate_json(
        self,
        results: List[ScenarioResult],
        config_summary: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Generate JSON report."""
        # Calculate metrics
        total = len(results)
        enforcement_caught = sum(1 for r in results if r.enforcement_caught)
        enforcement_missed = sum(1 for r in results if not r.enforcement_caught and r.scenario.expected_outcome == ExpectedOutcome.CONTROL_PASSES_EXPERIMENTAL_CATCHES)
        expected_matched = sum(1 for r in results if r.expected_outcome_matched)

        # Calculate per-agent metrics
        control_success = sum(1 for r in results if r.control_result.final_state == "ready")
        experimental_success = sum(1 for r in results if r.experimental_result.final_state == "ready")

        avg_control_time = sum(r.control_result.duration_seconds for r in results) / total if total else 0
        avg_experimental_time = sum(r.experimental_result.duration_seconds for r in results) / total if total else 0

        return {
            "metadata": {
                "timestamp": datetime.now().isoformat(),
                "total_scenarios": total,
                "config": config_summary,
            },
            "summary": {
                "enforcement_caught": enforcement_caught,
                "enforcement_missed": enforcement_missed,
                "expected_outcome_matched": expected_matched,
                "expected_outcome_rate": expected_matched / total if total else 0,
            },
            "comparison": {
                "control": {
                    "success_rate": control_success / total if total else 0,
                    "avg_duration_seconds": avg_control_time,
                },
                "experimental": {
                    "success_rate": experimental_success / total if total else 0,
                    "avg_duration_seconds": avg_experimental_time,
                },
                "experimental_worse_than_control": self._check_regressions(results),
            },
            "scenarios": [r.to_dict() for r in results],
        }

    def _generate_markdown(
        self,
        results: List[ScenarioResult],
        config_summary: Dict[str, Any],
    ) -> str:
        """Generate Markdown report."""
        lines = []

        # Header
        lines.append("# Jungle Gym Test Report")
        lines.append("")
        lines.append(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"**Scenarios Run:** {len(results)}")
        lines.append("")

        # Summary
        lines.append("## Summary")
        lines.append("")

        total = len(results)
        caught = sum(1 for r in results if r.enforcement_caught)
        matched = sum(1 for r in results if r.expected_outcome_matched)

        lines.append(f"| Metric | Value |")
        lines.append(f"|--------|-------|")
        lines.append(f"| Enforcement Caught | {caught}/{total} |")
        lines.append(f"| Expected Outcomes Matched | {matched}/{total} |")
        lines.append("")

        # Regressions (experimental worse than control)
        regressions = self._check_regressions(results)
        if regressions:
            lines.append("## REGRESSIONS (Experimental Worse Than Control)")
            lines.append("")
            lines.append("**These need fixing:**")
            lines.append("")
            for reg in regressions:
                lines.append(f"- {reg}")
            lines.append("")
        else:
            lines.append("## Regressions")
            lines.append("")
            lines.append("None - experimental never performed worse than control.")
            lines.append("")

        # Per-Tier Results
        for tier_name, tier_num in [("Tier 1: Core", 1), ("Tier 2: Important", 2), ("Tier 3: Full Coverage", 3)]:
            tier_results = [r for r in results if r.scenario.tier.value == tier_num]
            if not tier_results:
                continue

            lines.append(f"## {tier_name}")
            lines.append("")
            lines.append("| # | Scenario | Expected | Control | Experimental | Caught? |")
            lines.append("|---|----------|----------|---------|--------------|---------|")

            for r in tier_results:
                caught_str = "YES" if r.enforcement_caught else "no"
                control_state = r.control_result.final_state
                exp_state = r.experimental_result.final_state

                lines.append(
                    f"| {r.scenario.id} | {r.scenario.name} | {r.scenario.expected_outcome.value} | {control_state} | {exp_state} | {caught_str} |"
                )

            lines.append("")

        # Detailed Results
        lines.append("## Detailed Results")
        lines.append("")

        for r in results:
            lines.append(f"### {r.scenario.id}: {r.scenario.name}")
            lines.append("")
            lines.append(f"**Description:** {r.scenario.description}")
            lines.append("")
            lines.append(f"**Task:** `{r.scenario.task[:100]}...`" if len(r.scenario.task) > 100 else f"**Task:** `{r.scenario.task}`")
            lines.append("")
            lines.append(f"**Expected:** {r.scenario.expected_outcome.value}")
            lines.append("")

            lines.append("| Agent | Final State | Duration | Audit Status | Notes |")
            lines.append("|-------|-------------|----------|--------------|-------|")

            ctrl = r.control_result
            exp = r.experimental_result

            ctrl_audit = ctrl.audit_result.status if ctrl.audit_result else "N/A"
            exp_audit = exp.audit_result.status if exp.audit_result else "N/A"

            lines.append(f"| Control | {ctrl.final_state} | {ctrl.duration_seconds:.1f}s | {ctrl_audit} | |")
            lines.append(f"| Experimental | {exp.final_state} | {exp.duration_seconds:.1f}s | {exp_audit} | |")
            lines.append("")

            if r.notes:
                lines.append(f"**Notes:** {r.notes}")
                lines.append("")

        return "\n".join(lines)

    def _check_regressions(self, results: List[ScenarioResult]) -> List[str]:
        """Check for cases where experimental performed worse than control."""
        regressions = []

        for r in results:
            ctrl = r.control_result
            exp = r.experimental_result

            # Check for regressions (experimental worse)
            if ctrl.final_state == "ready" and exp.final_state in ("circuit_open", "requires_human"):
                # Could be expected (enforcement working) or regression
                if r.scenario.expected_outcome not in (
                    ExpectedOutcome.CONTROL_PASSES_EXPERIMENTAL_CATCHES,
                    ExpectedOutcome.EXPERIMENTAL_BLOCKS,
                ):
                    regressions.append(
                        f"{r.scenario.id}: Control succeeded but experimental failed ({exp.final_state})"
                    )

            # Check if experimental took much longer without catching anything
            if exp.duration_seconds > ctrl.duration_seconds * 2 and not r.enforcement_caught:
                regressions.append(
                    f"{r.scenario.id}: Experimental took {exp.duration_seconds/ctrl.duration_seconds:.1f}x longer without catching anything"
                )

        return regressions

    def save(
        self,
        json_report: Dict[str, Any],
        md_report: str,
        json_path: Path,
        md_path: Path,
        history_dir: Path,
    ) -> None:
        """Save reports to files."""
        # Ensure directories exist
        json_path.parent.mkdir(parents=True, exist_ok=True)
        md_path.parent.mkdir(parents=True, exist_ok=True)
        history_dir.mkdir(parents=True, exist_ok=True)

        # Save latest
        with open(json_path, "w") as f:
            json.dump(json_report, f, indent=2)

        with open(md_path, "w") as f:
            f.write(md_report)

        # Save to history
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        history_json = history_dir / f"{timestamp}.json"
        history_md = history_dir / f"{timestamp}.md"

        with open(history_json, "w") as f:
            json.dump(json_report, f, indent=2)

        with open(history_md, "w") as f:
            f.write(md_report)
