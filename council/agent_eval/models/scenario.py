"""
Scenario data models for Agent Eval system.

A Scenario defines:
- What environment to set up (files, commands)
- What prompt to give the agent
- How to verify the agent's work
- Optional metadata (difficulty, tags, etc.)
"""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import List, Optional, Dict, Any

import yaml

from ..exceptions import ScenarioError


class Difficulty(Enum):
    """Difficulty level for scenarios.

    Used for filtering, reporting, and analysis.
    """

    TRIVIAL = "trivial"  # Simple one-liner fix
    EASY = "easy"  # Straightforward task
    MEDIUM = "medium"  # Requires some thought
    HARD = "hard"  # Complex, multi-step
    EXPERT = "expert"  # Requires deep understanding


@dataclass
class FileSpec:
    """Specification for a file to create in the test environment.

    Attributes:
        path: Relative path within the working directory
        content: File contents
        encoding: File encoding (default utf-8)
    """

    path: str
    content: str
    encoding: str = "utf-8"

    def __post_init__(self):
        if not self.path:
            raise ScenarioError("FileSpec path cannot be empty")
        if self.path.startswith("/"):
            raise ScenarioError(
                f"FileSpec path must be relative, not absolute: {self.path}"
            )


@dataclass
class SetupSpec:
    """Specification for environment setup.

    Defines everything needed before the agent runs.
    """

    files: List[FileSpec] = field(default_factory=list)
    commands: List[str] = field(default_factory=list)  # Shell commands to run
    git_init: bool = False  # Initialize git repo
    npm_install: bool = False  # Run npm install
    pip_install: List[str] = field(default_factory=list)  # Packages to pip install


@dataclass
class CommandCheck:
    """Specification for a command-based verification check.

    Run a command and check its output/exit code.
    """

    cmd: str
    expect_exit_code: int = 0
    expect_stdout_contains: Optional[str] = None
    expect_stderr_contains: Optional[str] = None
    expect_stdout_not_contains: Optional[str] = None
    timeout_seconds: int = 30

    def __post_init__(self):
        if not self.cmd:
            raise ScenarioError("CommandCheck cmd cannot be empty")
        if self.timeout_seconds <= 0:
            raise ScenarioError("CommandCheck timeout_seconds must be positive")


@dataclass
class FileCheck:
    """Specification for a file-based verification check.

    Check that a file exists (or doesn't) and optionally verify contents.
    """

    path: str
    exists: bool = True  # Whether file should exist
    contains: Optional[str] = None  # Must contain this string
    not_contains: Optional[str] = None  # Must NOT contain this string
    matches_regex: Optional[str] = None  # Must match this regex

    def __post_init__(self):
        if not self.path:
            raise ScenarioError("FileCheck path cannot be empty")


@dataclass
class VerificationSpec:
    """Specification for all verification checks.

    Combines command checks, file checks, and optional custom verification.
    """

    commands: List[CommandCheck] = field(default_factory=list)
    files: List[FileCheck] = field(default_factory=list)
    custom_verifier: Optional[str] = None  # Path to custom verification script

    @property
    def total_checks(self) -> int:
        """Total number of verification checks."""
        return len(self.commands) + len(self.files) + (1 if self.custom_verifier else 0)


@dataclass
class Scenario:
    """A complete test scenario.

    This is the main unit of testing in Agent Eval. Each scenario:
    1. Sets up an isolated environment
    2. Runs an agent with a prompt
    3. Verifies the agent's output
    4. Optionally evaluates quality via watchdog

    Example YAML:
        scenario:
          id: "fix-type-error-001"
          name: "Fix TypeScript type error"
          description: "Agent should fix a type mismatch"
          prompt: "Fix the type error in src/broken.ts"
          setup:
            files:
              - path: "src/broken.ts"
                content: |
                  function add(a: number, b: string): number {
                    return a + b;  // Type error
                  }
          verification:
            commands:
              - cmd: "npx tsc --noEmit"
                expect_exit_code: 0
            files:
              - path: "src/broken.ts"
                contains: "b: number"
    """

    # Required fields
    id: str
    name: str
    description: str
    prompt: str
    verification: VerificationSpec

    # Optional fields
    setup: SetupSpec = field(default_factory=SetupSpec)
    teardown_commands: List[str] = field(default_factory=list)
    difficulty: Difficulty = Difficulty.MEDIUM
    tags: List[str] = field(default_factory=list)
    timeout_override: Optional[int] = None  # Override agent timeout for this scenario
    watchdog_questions: List[str] = field(default_factory=list)  # Custom eval questions
    expected_behavior: Optional[str] = None  # Description for watchdog
    known_issues: List[str] = field(default_factory=list)  # Document known problems
    metadata: Dict[str, Any] = field(default_factory=dict)  # Arbitrary metadata

    def __post_init__(self):
        if not self.id:
            raise ScenarioError("Scenario id cannot be empty")
        if not self.name:
            raise ScenarioError("Scenario name cannot be empty")
        if not self.prompt:
            raise ScenarioError("Scenario prompt cannot be empty")

        # Convert difficulty string to enum if needed
        if isinstance(self.difficulty, str):
            try:
                self.difficulty = Difficulty(self.difficulty)
            except ValueError:
                valid = [d.value for d in Difficulty]
                raise ScenarioError(
                    f"Invalid difficulty '{self.difficulty}'. Must be one of: {valid}"
                )

    @classmethod
    def from_yaml(cls, path: Path) -> "Scenario":
        """Load scenario from YAML file.

        Args:
            path: Path to YAML file

        Returns:
            Scenario instance

        Raises:
            ScenarioError: If file not found, invalid YAML, or validation fails
        """
        if not path.exists():
            raise ScenarioError(f"Scenario file not found: {path}")

        try:
            with open(path) as f:
                data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise ScenarioError(f"Invalid YAML in {path}: {e}")

        if not data:
            raise ScenarioError(f"Empty scenario file: {path}")

        return cls.from_dict(data, source_path=path)

    @classmethod
    def from_dict(
        cls, data: Dict[str, Any], source_path: Optional[Path] = None
    ) -> "Scenario":
        """Create Scenario from dictionary.

        Args:
            data: Dictionary containing scenario data
            source_path: Optional source path for error messages

        Returns:
            Scenario instance

        Raises:
            ScenarioError: If required fields missing or validation fails
        """
        # Handle both {"scenario": {...}} and direct {...} formats
        scenario_data = data.get("scenario", data)
        source = f" in {source_path}" if source_path else ""

        # Validate required fields
        for required in ["id", "name", "prompt"]:
            if required not in scenario_data:
                raise ScenarioError(f"Missing required field '{required}'{source}")

        try:
            # Parse setup
            setup_data = scenario_data.get("setup", {})
            setup = SetupSpec(
                files=[
                    FileSpec(**f) for f in setup_data.get("files", [])
                ],
                commands=setup_data.get("commands", []),
                git_init=setup_data.get("git_init", False),
                npm_install=setup_data.get("npm_install", False),
                pip_install=setup_data.get("pip_install", []),
            )

            # Parse verification
            verif_data = scenario_data.get("verification", {})
            verification = VerificationSpec(
                commands=[
                    CommandCheck(**_normalize_command_check(c))
                    for c in verif_data.get("commands", [])
                ],
                files=[
                    FileCheck(**f) for f in verif_data.get("files", [])
                ],
                custom_verifier=verif_data.get("custom_verifier"),
            )

            return cls(
                id=scenario_data["id"],
                name=scenario_data["name"],
                description=scenario_data.get("description", ""),
                prompt=scenario_data["prompt"],
                setup=setup,
                verification=verification,
                teardown_commands=scenario_data.get("teardown_commands", []),
                difficulty=scenario_data.get("difficulty", "medium"),
                tags=scenario_data.get("tags", []),
                timeout_override=scenario_data.get("timeout_override"),
                watchdog_questions=scenario_data.get("watchdog_questions", []),
                expected_behavior=scenario_data.get("expected_behavior"),
                known_issues=scenario_data.get("known_issues", []),
                metadata=scenario_data.get("metadata", {}),
            )

        except ScenarioError:
            raise
        except Exception as e:
            raise ScenarioError(f"Failed to parse scenario{source}: {e}")

    def to_dict(self) -> Dict[str, Any]:
        """Convert scenario to dictionary (for serialization)."""
        return {
            "scenario": {
                "id": self.id,
                "name": self.name,
                "description": self.description,
                "prompt": self.prompt,
                "setup": {
                    "files": [
                        {"path": f.path, "content": f.content, "encoding": f.encoding}
                        for f in self.setup.files
                    ],
                    "commands": self.setup.commands,
                    "git_init": self.setup.git_init,
                    "npm_install": self.setup.npm_install,
                    "pip_install": self.setup.pip_install,
                },
                "verification": {
                    "commands": [
                        {
                            "cmd": c.cmd,
                            "expect_exit_code": c.expect_exit_code,
                            "expect_stdout_contains": c.expect_stdout_contains,
                            "expect_stderr_contains": c.expect_stderr_contains,
                            "expect_stdout_not_contains": c.expect_stdout_not_contains,
                            "timeout_seconds": c.timeout_seconds,
                        }
                        for c in self.verification.commands
                    ],
                    "files": [
                        {
                            "path": f.path,
                            "exists": f.exists,
                            "contains": f.contains,
                            "not_contains": f.not_contains,
                            "matches_regex": f.matches_regex,
                        }
                        for f in self.verification.files
                    ],
                    "custom_verifier": self.verification.custom_verifier,
                },
                "teardown_commands": self.teardown_commands,
                "difficulty": self.difficulty.value,
                "tags": self.tags,
                "timeout_override": self.timeout_override,
                "watchdog_questions": self.watchdog_questions,
                "expected_behavior": self.expected_behavior,
                "known_issues": self.known_issues,
                "metadata": self.metadata,
            }
        }

    def to_yaml(self) -> str:
        """Serialize scenario to YAML string."""
        return yaml.dump(self.to_dict(), default_flow_style=False, sort_keys=False)


def _normalize_command_check(data: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize command check data from various YAML formats.

    Handles:
    - {cmd: "...", expect: "exit_code: 0"}  (legacy format)
    - {cmd: "...", expect_exit_code: 0}      (standard format)
    """
    result = dict(data)

    # Handle legacy "expect" format
    if "expect" in result:
        expect = result.pop("expect")
        if isinstance(expect, str):
            if expect.startswith("exit_code:"):
                try:
                    code = int(expect.split(":")[1].strip())
                    result["expect_exit_code"] = code
                except (IndexError, ValueError):
                    pass

    return result
