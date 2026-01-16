"""
Data models for Agent Eval system.

Public exports:
- Scenario and related specs (FileSpec, SetupSpec, VerificationSpec, etc.)
- Result types (RunResult, VerificationResult, WatchdogResult, Metrics)
- Enums (Difficulty, ResultStatus)
"""

from .scenario import (
    Difficulty,
    FileSpec,
    SetupSpec,
    CommandCheck,
    FileCheck,
    VerificationSpec,
    Scenario,
)

from .result import (
    ResultStatus,
    CommandResult,
    FileResult,
    VerificationResult,
    WatchdogResult,
    Metrics,
    RunResult,
)

__all__ = [
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
]
