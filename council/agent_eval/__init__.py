"""
Agent Eval - Testing and evaluation system for AI coding agents.

This module provides:
- Scenario-based testing (define tests in YAML)
- Deterministic verification (command + file checks)
- LLM watchdog evaluation (qualitative feedback)
- Metrics collection (timing, tokens, cost)
- Report generation (JSON, Markdown)

Quick start:
    from council.agent_eval import Config, Scenario, AgentEvalRunner

    # Load a scenario
    scenario = Scenario.from_yaml(Path("my_scenario.yaml"))

    # Run it
    runner = AgentEvalRunner()
    result = runner.run_scenario(scenario)

    # Check results
    print(result.summary())
    if not result.passed:
        for failure in result.verification.failures():
            print(f"  - {failure}")

CLI usage:
    python -m council.agent_eval scenarios/ --format markdown
"""

__version__ = "0.1.0"

# Core exports
from .config import Config, AgentConfig, WatchdogConfig, PersistenceConfig, ExecutionConfig
from .exceptions import (
    AgentEvalError,
    ScenarioError,
    EnvironmentError,
    ExecutionError,
    TimeoutError,
    VerificationError,
    WatchdogError,
    PersistenceError,
    ConfigurationError,
)

# Model exports
from .models import (
    # Scenario models
    Difficulty,
    FileSpec,
    SetupSpec,
    CommandCheck,
    FileCheck,
    VerificationSpec,
    Scenario,
    # Result models
    ResultStatus,
    CommandResult,
    FileResult,
    VerificationResult,
    WatchdogResult,
    Metrics,
    RunResult,
)

# Orchestration exports
from .orchestration import AgentEvalRunner, DryRunner

# Reporting exports
from .reporting import Report, Reporter, ComparisonReporter

__all__ = [
    # Version
    "__version__",
    # Config
    "Config",
    "AgentConfig",
    "WatchdogConfig",
    "PersistenceConfig",
    "ExecutionConfig",
    # Exceptions
    "AgentEvalError",
    "ScenarioError",
    "EnvironmentError",
    "ExecutionError",
    "TimeoutError",
    "VerificationError",
    "WatchdogError",
    "PersistenceError",
    "ConfigurationError",
    # Scenario models
    "Difficulty",
    "FileSpec",
    "SetupSpec",
    "CommandCheck",
    "FileCheck",
    "VerificationSpec",
    "Scenario",
    # Result models
    "ResultStatus",
    "CommandResult",
    "FileResult",
    "VerificationResult",
    "WatchdogResult",
    "Metrics",
    "RunResult",
    # Orchestration
    "AgentEvalRunner",
    "DryRunner",
    # Reporting
    "Report",
    "Reporter",
    "ComparisonReporter",
]
