"""
LLM Watchdog evaluation for Agent Eval.

The Watchdog uses an LLM to evaluate the quality of an agent's work,
providing qualitative feedback beyond pass/fail verification.
"""

import json
from typing import Optional, List
import logging

from ..models.scenario import Scenario
from ..models.result import VerificationResult, WatchdogResult
from ..config import WatchdogConfig
from ..exceptions import WatchdogError

logger = logging.getLogger(__name__)


class Watchdog:
    """LLM-based evaluation of agent output.

    The Watchdog analyzes an agent's work and provides:
    - Understanding assessment (did agent understand the problem?)
    - Approach assessment (was the solution appropriate?)
    - Pattern identification (what worked, what didn't?)
    - Actionable feedback (how to improve?)

    This qualitative feedback complements the deterministic
    verification checks to give a fuller picture of agent performance.

    Usage:
        watchdog = Watchdog(config)
        result = watchdog.evaluate(
            scenario=scenario,
            agent_output=agent_output,
            verification_result=verification_result,
        )
        print(f"Understanding: {result.understanding}")
        print(f"Feedback: {result.feedback_for_agent}")
    """

    def __init__(self, config: WatchdogConfig):
        """Initialize watchdog.

        Args:
            config: Watchdog configuration
        """
        self.config = config
        self._client = None

    @property
    def client(self):
        """Lazy-load Anthropic client."""
        if self._client is None:
            try:
                from anthropic import Anthropic
                self._client = Anthropic()
            except ImportError:
                raise WatchdogError(
                    "anthropic package not installed. "
                    "Install with: pip install anthropic"
                )
            except Exception as e:
                raise WatchdogError(f"Failed to initialize Anthropic client: {e}")
        return self._client

    def evaluate(
        self,
        scenario: Scenario,
        agent_output: str,
        verification_result: VerificationResult,
    ) -> WatchdogResult:
        """Evaluate agent output using LLM.

        Args:
            scenario: The scenario that was run
            agent_output: The agent's text output
            verification_result: Results of verification checks

        Returns:
            WatchdogResult with qualitative assessment
        """
        if not self.config.enabled:
            return WatchdogResult(
                understanding="skipped",
                approach="skipped",
                feedback_for_agent="Watchdog evaluation disabled",
            )

        try:
            prompt = self._build_prompt(scenario, agent_output, verification_result)

            logger.debug(f"Running watchdog evaluation for scenario {scenario.id}")

            response = self.client.messages.create(
                model=self.config.model,
                max_tokens=2000,
                temperature=self.config.temperature,
                messages=[{"role": "user", "content": prompt}],
            )

            raw_response = response.content[0].text
            result = self._parse_response(raw_response)

            logger.debug(
                f"Watchdog evaluation complete: "
                f"understanding={result.understanding}, approach={result.approach}"
            )

            return result

        except WatchdogError:
            raise
        except Exception as e:
            logger.error(f"Watchdog evaluation failed: {e}")
            return WatchdogResult(
                understanding="error",
                approach="error",
                error=str(e),
            )

    def _build_prompt(
        self,
        scenario: Scenario,
        agent_output: str,
        verification_result: VerificationResult,
    ) -> str:
        """Build the evaluation prompt.

        Args:
            scenario: The scenario
            agent_output: Agent's output
            verification_result: Verification results

        Returns:
            Prompt string for the LLM
        """
        # Use custom questions if provided, otherwise defaults
        questions = scenario.watchdog_questions or [
            "Did the agent understand the problem correctly?",
            "Was the solution approach appropriate?",
            "Were there any signs of rushing or shortcuts?",
            "What specific patterns led to success or failure?",
        ]

        # Truncate agent output if too long
        max_output_len = 5000
        truncated_output = agent_output[:max_output_len]
        if len(agent_output) > max_output_len:
            truncated_output += f"\n... [truncated, {len(agent_output)} total chars]"

        # Build verification summary
        verif_summary = []
        for cmd_result in verification_result.command_results:
            status = "PASS" if cmd_result.passed else "FAIL"
            verif_summary.append(f"  [{status}] {cmd_result.cmd}")
        for file_result in verification_result.file_results:
            status = "PASS" if file_result.passed else "FAIL"
            verif_summary.append(f"  [{status}] File: {file_result.path}")

        verif_details = "\n".join(verif_summary) if verif_summary else "  No checks defined"

        return f"""You are evaluating an AI coding agent's work. Be thorough and critical.

## Task Given to Agent
{scenario.prompt}

## Expected Behavior
{scenario.expected_behavior or "Not specified - use your judgment based on the task."}

## Agent Output
```
{truncated_output}
```

## Verification Result
Overall: {"PASSED" if verification_result.passed else "FAILED"}
Details:
{verif_details}

## Questions to Answer
{chr(10).join(f"- {q}" for q in questions)}

## Your Evaluation
Analyze the agent's work carefully. Consider:
- Did the agent actually understand what was being asked?
- Was the approach reasonable, or did they over/under-engineer?
- Did they verify their work, or just assume it was correct?
- What patterns do you see that could help improve future performance?

Return your evaluation as JSON with these exact fields:
{{
    "understanding": "good" | "partial" | "poor",
    "approach": "appropriate" | "over-engineered" | "insufficient",
    "shortcuts_taken": ["list of shortcuts or corners cut, or empty array"],
    "failure_patterns": ["patterns that led to issues, or empty array"],
    "success_patterns": ["what worked well, or empty array"],
    "feedback_for_agent": "specific, actionable feedback to improve future performance",
    "suggested_scenarios": ["new test scenarios that would catch similar issues"],
    "confidence": 0.0-1.0
}}

Be specific and actionable. Vague feedback like "be more careful" is not helpful.
Focus on patterns that can be learned from."""

    def _parse_response(self, response: str) -> WatchdogResult:
        """Parse LLM response into WatchdogResult.

        Args:
            response: Raw LLM response

        Returns:
            Parsed WatchdogResult
        """
        try:
            # Try to extract JSON from response
            # Handle case where response might have text before/after JSON
            start = response.find("{")
            end = response.rfind("}") + 1

            if start >= 0 and end > start:
                json_str = response[start:end]
                data = json.loads(json_str)

                return WatchdogResult(
                    understanding=data.get("understanding", "unknown"),
                    approach=data.get("approach", "unknown"),
                    shortcuts_taken=data.get("shortcuts_taken", []),
                    failure_patterns=data.get("failure_patterns", []),
                    success_patterns=data.get("success_patterns", []),
                    feedback_for_agent=data.get("feedback_for_agent", ""),
                    suggested_scenarios=data.get("suggested_scenarios", []),
                    confidence=float(data.get("confidence", 0.0)),
                    raw_response=response,
                )

        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse watchdog response as JSON: {e}")

        # Fallback: return raw response as feedback
        return WatchdogResult(
            understanding="parse_error",
            approach="parse_error",
            feedback_for_agent=response,
            raw_response=response,
            error="Failed to parse structured response",
        )


class MockWatchdog:
    """Mock watchdog for testing.

    Returns configurable responses without making LLM API calls.
    """

    def __init__(
        self,
        understanding: str = "good",
        approach: str = "appropriate",
        feedback: str = "Mock feedback",
        should_error: bool = False,
        error_message: str = "Mock watchdog error",
    ):
        """Initialize mock watchdog.

        Args:
            understanding: Understanding to return
            approach: Approach to return
            feedback: Feedback to return
            should_error: If True, raise WatchdogError
            error_message: Error message if should_error
        """
        self.understanding = understanding
        self.approach = approach
        self.feedback = feedback
        self.should_error = should_error
        self.error_message = error_message
        self.calls: List[dict] = []

    def evaluate(
        self,
        scenario: Scenario,
        agent_output: str,
        verification_result: VerificationResult,
    ) -> WatchdogResult:
        """Return mock evaluation."""
        self.calls.append({
            "scenario_id": scenario.id,
            "agent_output_len": len(agent_output),
            "verification_passed": verification_result.passed,
        })

        if self.should_error:
            raise WatchdogError(self.error_message)

        return WatchdogResult(
            understanding=self.understanding,
            approach=self.approach,
            feedback_for_agent=self.feedback,
            confidence=0.9,
        )

    @property
    def call_count(self) -> int:
        """Number of times evaluate was called."""
        return len(self.calls)
