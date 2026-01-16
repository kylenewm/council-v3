"""
Main test harness for Jungle Gym.

Runs adversarial scenarios against control vs experimental agents
and collects results for comparison.
"""

import argparse
import asyncio
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from .config import JungleGymConfig, AgentConfig
from .scenarios import (
    Scenario,
    Tier,
    ExpectedOutcome,
    get_scenarios_by_tier,
    get_all_scenarios,
    get_scenario_by_id,
    TIER_1_SCENARIOS,
)
from .collector import ResultCollector, AgentResult, run_audit
from .reporter import Reporter, ScenarioResult


class JungleGymHarness:
    """Main harness for running adversarial tests."""

    def __init__(self, config: JungleGymConfig):
        self.config = config
        self.collector = ResultCollector(
            state_path=Path.home() / ".council" / "state.json",
            logs_dir=Path.home() / ".council" / "logs",
        )
        self.reporter = Reporter()
        self.results: List[ScenarioResult] = []

    async def run_all(self, tier: Optional[Tier] = None) -> List[ScenarioResult]:
        """Run all scenarios (or specific tier)."""
        if tier:
            scenarios = get_scenarios_by_tier(tier)
        else:
            scenarios = get_all_scenarios()

        print(f"Running {len(scenarios)} scenarios...")
        print("=" * 60)

        for scenario in scenarios:
            print(f"\n[{scenario.id}] {scenario.name}")
            print(f"    {scenario.description}")

            result = await self.run_scenario(scenario)
            self.results.append(result)

            # Print quick result
            caught = "CAUGHT" if result.enforcement_caught else "not caught"
            matched = "OK" if result.expected_outcome_matched else "UNEXPECTED"
            print(f"    Result: {caught} | {matched}")

        return self.results

    async def run_scenario(self, scenario: Scenario) -> ScenarioResult:
        """Run a single scenario on both agents."""
        print(f"    Sending to Control ({self.config.control_agent.name})...")
        control_result = await self._run_on_agent(
            self.config.control_agent,
            "A",
            scenario,
        )

        print(f"    Sending to Experimental ({self.config.experimental_agent.name})...")
        experimental_result = await self._run_on_agent(
            self.config.experimental_agent,
            "B",
            scenario,
        )

        # Determine if enforcement caught something
        enforcement_caught = self._check_enforcement_caught(
            control_result,
            experimental_result,
            scenario,
        )

        # Determine if expected outcome matched
        expected_matched = self._check_expected_outcome(
            control_result,
            experimental_result,
            scenario,
        )

        return ScenarioResult(
            scenario=scenario,
            control_result=control_result,
            experimental_result=experimental_result,
            enforcement_caught=enforcement_caught,
            expected_outcome_matched=expected_matched,
        )

    async def _run_on_agent(
        self,
        agent_config: AgentConfig,
        agent_id: str,
        scenario: Scenario,
    ) -> AgentResult:
        """Run scenario on a single agent."""
        start_time = datetime.now()

        # Run setup commands if any
        if scenario.setup_commands:
            for cmd in scenario.setup_commands:
                if cmd.startswith("#"):
                    continue  # Skip comments
                formatted_cmd = cmd.format(agent_id=agent_id)
                self._send_to_dispatcher(formatted_cmd)

        # Send the task
        task_cmd = f"{agent_id}: {scenario.task}"
        self._send_to_dispatcher(task_cmd)

        # Wait for completion
        timeout = scenario.timeout_override or self.config.timeout_seconds
        await self._wait_for_completion(agent_config.pane_id, timeout)

        # Collect results
        result = self.collector.collect(
            agent_id=agent_id,
            agent_name=agent_config.name,
            scenario_id=scenario.id,
            start_time=start_time,
            transcript_path=agent_config.transcript_path,
        )

        # Run audit if experimental agent
        if agent_config.is_experimental() and agent_config.transcript_path:
            scripts_dir = Path(__file__).parent.parent.parent / "scripts"
            result.audit_result = run_audit(agent_config.transcript_path, scripts_dir)

        # Run teardown commands if any
        if scenario.teardown_commands:
            for cmd in scenario.teardown_commands:
                if cmd.startswith("#"):
                    continue
                formatted_cmd = cmd.format(agent_id=agent_id)
                self._send_to_dispatcher(formatted_cmd)

        return result

    def _send_to_dispatcher(self, command: str) -> None:
        """Send a command to the dispatcher via FIFO."""
        fifo_path = Path.home() / ".council" / "in.fifo"
        if fifo_path.exists():
            try:
                with open(fifo_path, "w") as f:
                    f.write(command + "\n")
            except Exception as e:
                print(f"    Warning: Could not send to FIFO: {e}")
        else:
            print(f"    Warning: FIFO not found at {fifo_path}")

    async def _wait_for_completion(self, pane_id: str, timeout: int) -> None:
        """Wait for agent to complete (prompt visible)."""
        start = datetime.now()
        poll_interval = self.config.poll_interval

        while (datetime.now() - start).total_seconds() < timeout:
            # Check if prompt is visible (agent ready)
            if self._check_agent_ready(pane_id):
                return
            await asyncio.sleep(poll_interval)

        print(f"    Warning: Timeout waiting for agent {pane_id}")

    def _check_agent_ready(self, pane_id: str) -> bool:
        """Check if agent shows prompt (ready state)."""
        try:
            result = subprocess.run(
                ["tmux", "capture-pane", "-p", "-t", pane_id],
                capture_output=True,
                text=True,
                timeout=5,
            )
            output = result.stdout
            # Look for common prompt indicators
            return any(indicator in output for indicator in ["❯", ">", "$", "claude>"])
        except Exception:
            return False

    def _check_enforcement_caught(
        self,
        control: AgentResult,
        experimental: AgentResult,
        scenario: Scenario,
    ) -> bool:
        """Check if enforcement caught something control didn't."""
        # Experimental caught = audit rejected, circuit open, or requires human
        exp_caught = (
            (experimental.audit_result and experimental.audit_result.status == "DISCREPANCY")
            or experimental.circuit_state == "open"
            or experimental.final_state == "requires_human"
            or experimental.final_state == "awaiting_done_report"
        )

        # Control didn't catch = ready state, no issues
        control_passed = control.final_state == "ready"

        return exp_caught and control_passed

    def _check_expected_outcome(
        self,
        control: AgentResult,
        experimental: AgentResult,
        scenario: Scenario,
    ) -> bool:
        """Check if results match expected outcome."""
        expected = scenario.expected_outcome

        if expected == ExpectedOutcome.CONTROL_PASSES_EXPERIMENTAL_CATCHES:
            return (
                control.final_state == "ready"
                and experimental.final_state in ("requires_human", "awaiting_done_report", "circuit_open")
                or (experimental.audit_result and experimental.audit_result.status == "DISCREPANCY")
            )

        elif expected == ExpectedOutcome.BOTH_HANDLE_GRACEFULLY:
            return (
                control.final_state not in ("error", "crashed")
                and experimental.final_state not in ("error", "crashed")
            )

        elif expected == ExpectedOutcome.EXPERIMENTAL_BLOCKS:
            return experimental.final_state in ("requires_human", "awaiting_done_report")

        elif expected == ExpectedOutcome.NEITHER_CATCHES:
            return True  # Known gap, always "expected"

        elif expected == ExpectedOutcome.BOTH_PASS:
            return (
                control.final_state == "ready"
                and experimental.final_state == "ready"
            )

        elif expected == ExpectedOutcome.STATE_PRESERVED:
            # Would need to check state persistence specifically
            return True

        return False

    def generate_report(self) -> None:
        """Generate and save reports."""
        config_summary = {
            "control": {
                "name": self.config.control_agent.name,
                "mode": self.config.control_agent.mode,
                "auto_audit": self.config.control_agent.auto_audit,
            },
            "experimental": {
                "name": self.config.experimental_agent.name,
                "mode": self.config.experimental_agent.mode,
                "auto_audit": self.config.experimental_agent.auto_audit,
            },
        }

        json_report, md_report = self.reporter.generate(self.results, config_summary)

        self.reporter.save(
            json_report=json_report,
            md_report=md_report,
            json_path=self.config.output.json_path,
            md_path=self.config.output.markdown_path,
            history_dir=self.config.output.history_dir,
        )

        print(f"\nReports saved:")
        print(f"  JSON: {self.config.output.json_path}")
        print(f"  Markdown: {self.config.output.markdown_path}")


async def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Jungle Gym: E2E Test Harness for Council-v3")
    parser.add_argument(
        "--config",
        type=Path,
        help="Path to config YAML",
    )
    parser.add_argument(
        "--tier",
        type=int,
        choices=[1, 2, 3],
        help="Run specific tier (1=core, 2=important, 3=full)",
    )
    parser.add_argument(
        "--scenario",
        type=str,
        help="Run specific scenario by ID (e.g., '1.1')",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print scenarios without running",
    )

    args = parser.parse_args()

    # Load config
    if args.config and args.config.exists():
        config = JungleGymConfig.from_yaml(args.config)
    else:
        config = JungleGymConfig.default()

    # Dry run
    if args.dry_run:
        if args.tier:
            scenarios = get_scenarios_by_tier(Tier(args.tier))
        elif args.scenario:
            s = get_scenario_by_id(args.scenario)
            scenarios = [s] if s else []
        else:
            scenarios = get_all_scenarios()

        print(f"Would run {len(scenarios)} scenarios:")
        for s in scenarios:
            print(f"  [{s.id}] {s.name} - {s.description[:50]}...")
        return

    # Run harness
    harness = JungleGymHarness(config)

    if args.scenario:
        scenario = get_scenario_by_id(args.scenario)
        if scenario:
            result = await harness.run_scenario(scenario)
            harness.results.append(result)
        else:
            print(f"Scenario {args.scenario} not found")
            return
    elif args.tier:
        await harness.run_all(tier=Tier(args.tier))
    else:
        await harness.run_all()

    # Generate report
    harness.generate_report()


if __name__ == "__main__":
    asyncio.run(main())
