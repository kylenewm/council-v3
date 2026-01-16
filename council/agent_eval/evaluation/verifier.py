"""
Deterministic verification for Agent Eval.

The Verifier runs command and file checks to determine if
an agent's work meets the success criteria defined in a scenario.
"""

import subprocess
import re
import time
import json
from pathlib import Path
from typing import List, Optional, Dict, Any
import logging

from ..models.scenario import VerificationSpec, CommandCheck, FileCheck
from ..models.result import VerificationResult, CommandResult, FileResult
from ..exceptions import VerificationError

logger = logging.getLogger(__name__)


class Verifier:
    """Deterministic verification of agent output.

    Runs verification checks defined in a scenario's VerificationSpec
    and returns structured results.

    Verification types:
    - Command checks: Run commands and check exit codes/output
    - File checks: Check file existence and contents
    - Custom verifiers: Run custom verification scripts

    Usage:
        verifier = Verifier()
        result = verifier.verify(scenario.verification, workdir)
        if result.passed:
            print("All checks passed!")
        else:
            for failure in result.failures():
                print(f"Failed: {failure}")
    """

    def verify(
        self,
        spec: VerificationSpec,
        workdir: Path,
    ) -> VerificationResult:
        """Run all verification checks.

        Args:
            spec: Verification specification from scenario
            workdir: Working directory to run checks in

        Returns:
            VerificationResult with all check results
        """
        command_results: List[CommandResult] = []
        file_results: List[FileResult] = []
        custom_result: Optional[Dict[str, Any]] = None
        overall_error: Optional[str] = None

        # Run command checks
        for cmd_spec in spec.commands:
            try:
                result = self._check_command(cmd_spec, workdir)
                command_results.append(result)
            except Exception as e:
                logger.error(f"Command check failed unexpectedly: {cmd_spec.cmd}: {e}")
                command_results.append(CommandResult(
                    cmd=cmd_spec.cmd,
                    exit_code=-1,
                    expected_exit_code=cmd_spec.expect_exit_code,
                    stdout="",
                    stderr=str(e),
                    passed=False,
                    duration_seconds=0.0,
                    error=str(e),
                ))

        # Run file checks
        for file_spec in spec.files:
            try:
                result = self._check_file(file_spec, workdir)
                file_results.append(result)
            except Exception as e:
                logger.error(f"File check failed unexpectedly: {file_spec.path}: {e}")
                file_results.append(FileResult(
                    path=file_spec.path,
                    exists=False,
                    expected_exists=file_spec.exists,
                    passed=False,
                    error=str(e),
                ))

        # Run custom verifier if specified
        if spec.custom_verifier:
            try:
                custom_result = self._run_custom_verifier(spec.custom_verifier, workdir)
            except Exception as e:
                logger.error(f"Custom verifier failed: {e}")
                custom_result = {"passed": False, "error": str(e)}
                overall_error = f"Custom verifier failed: {e}"

        # Determine overall pass/fail
        all_passed = (
            all(r.passed for r in command_results)
            and all(r.passed for r in file_results)
            and (custom_result is None or custom_result.get("passed", False))
        )

        return VerificationResult(
            command_results=command_results,
            file_results=file_results,
            custom_result=custom_result,
            passed=all_passed,
            error=overall_error,
        )

    def _check_command(
        self,
        spec: CommandCheck,
        workdir: Path,
    ) -> CommandResult:
        """Execute a command and check expectations.

        Args:
            spec: Command check specification
            workdir: Working directory

        Returns:
            CommandResult with check outcome
        """
        start_time = time.time()

        try:
            result = subprocess.run(
                spec.cmd,
                cwd=workdir,
                capture_output=True,
                text=True,
                timeout=spec.timeout_seconds,
                shell=True,
            )
        except subprocess.TimeoutExpired:
            duration = time.time() - start_time
            return CommandResult(
                cmd=spec.cmd,
                exit_code=-1,
                expected_exit_code=spec.expect_exit_code,
                stdout="",
                stderr="",
                passed=False,
                duration_seconds=duration,
                error=f"Command timed out after {spec.timeout_seconds}s",
            )

        duration = time.time() - start_time

        # Check all expectations
        passed = True
        failure_reasons = []

        # Exit code check
        if result.returncode != spec.expect_exit_code:
            passed = False
            failure_reasons.append(
                f"exit code {result.returncode} != expected {spec.expect_exit_code}"
            )

        # Stdout contains check
        if spec.expect_stdout_contains:
            if spec.expect_stdout_contains not in result.stdout:
                passed = False
                failure_reasons.append(
                    f"stdout missing expected content: {spec.expect_stdout_contains[:50]}..."
                )

        # Stderr contains check
        if spec.expect_stderr_contains:
            if spec.expect_stderr_contains not in result.stderr:
                passed = False
                failure_reasons.append(
                    f"stderr missing expected content: {spec.expect_stderr_contains[:50]}..."
                )

        # Stdout NOT contains check
        if spec.expect_stdout_not_contains:
            if spec.expect_stdout_not_contains in result.stdout:
                passed = False
                failure_reasons.append(
                    f"stdout contains forbidden content: {spec.expect_stdout_not_contains[:50]}..."
                )

        error_msg = "; ".join(failure_reasons) if failure_reasons else None

        return CommandResult(
            cmd=spec.cmd,
            exit_code=result.returncode,
            expected_exit_code=spec.expect_exit_code,
            stdout=result.stdout,
            stderr=result.stderr,
            passed=passed,
            duration_seconds=duration,
            error=error_msg,
        )

    def _check_file(
        self,
        spec: FileCheck,
        workdir: Path,
    ) -> FileResult:
        """Check file existence and contents.

        Args:
            spec: File check specification
            workdir: Working directory

        Returns:
            FileResult with check outcome
        """
        file_path = workdir / spec.path
        exists = file_path.exists()

        # If file should not exist
        if not spec.exists:
            return FileResult(
                path=spec.path,
                exists=exists,
                expected_exists=False,
                passed=(not exists),
                error="File exists but should not" if exists else None,
            )

        # If file should exist but doesn't
        if not exists:
            return FileResult(
                path=spec.path,
                exists=False,
                expected_exists=True,
                passed=False,
                error="File does not exist",
            )

        # File exists, check contents
        try:
            content = file_path.read_text()
        except Exception as e:
            return FileResult(
                path=spec.path,
                exists=True,
                expected_exists=True,
                passed=False,
                error=f"Could not read file: {e}",
            )

        passed = True
        failure_reasons = []

        # Contains check
        contains_found = True
        if spec.contains:
            contains_found = spec.contains in content
            if not contains_found:
                passed = False
                failure_reasons.append(
                    f"missing expected content: {spec.contains[:50]}..."
                )

        # Not contains check
        if spec.not_contains:
            if spec.not_contains in content:
                passed = False
                failure_reasons.append(
                    f"contains forbidden content: {spec.not_contains[:50]}..."
                )

        # Regex match check
        if spec.matches_regex:
            if not re.search(spec.matches_regex, content):
                passed = False
                failure_reasons.append(
                    f"does not match regex: {spec.matches_regex}"
                )

        error_msg = "; ".join(failure_reasons) if failure_reasons else None

        return FileResult(
            path=spec.path,
            exists=True,
            expected_exists=True,
            contains_check=spec.contains,
            contains_found=contains_found,
            passed=passed,
            error=error_msg,
        )

    def _run_custom_verifier(
        self,
        script_path: str,
        workdir: Path,
    ) -> Dict[str, Any]:
        """Run a custom verification script.

        Custom verifiers must:
        - Be executable Python scripts
        - Output JSON to stdout
        - Include a "passed" boolean in the output

        Args:
            script_path: Path to the custom verifier script
            workdir: Working directory

        Returns:
            Dict parsed from the script's JSON output

        Raises:
            VerificationError: If script fails or output is invalid
        """
        # Resolve script path
        if not Path(script_path).is_absolute():
            script_full_path = workdir / script_path
        else:
            script_full_path = Path(script_path)

        if not script_full_path.exists():
            raise VerificationError(f"Custom verifier not found: {script_path}")

        try:
            result = subprocess.run(
                ["python3", str(script_full_path)],
                cwd=workdir,
                capture_output=True,
                text=True,
                timeout=60,
            )
        except subprocess.TimeoutExpired:
            raise VerificationError("Custom verifier timed out after 60s")

        if result.returncode != 0:
            raise VerificationError(
                f"Custom verifier exited with code {result.returncode}: {result.stderr}"
            )

        try:
            output = json.loads(result.stdout)
        except json.JSONDecodeError as e:
            raise VerificationError(
                f"Custom verifier output is not valid JSON: {e}\n"
                f"Output was: {result.stdout[:200]}"
            )

        if "passed" not in output:
            raise VerificationError(
                "Custom verifier output missing 'passed' field"
            )

        return output


class QuickVerifier:
    """Simplified verifier for common checks.

    Provides convenience methods for single-check verification
    without needing to construct full VerificationSpec objects.
    """

    def __init__(self, workdir: Path):
        """Initialize with working directory.

        Args:
            workdir: Working directory for checks
        """
        self.workdir = workdir
        self._verifier = Verifier()

    def command_succeeds(self, cmd: str, timeout: int = 30) -> bool:
        """Check if a command succeeds (exit code 0).

        Args:
            cmd: Command to run
            timeout: Timeout in seconds

        Returns:
            True if command exits with code 0
        """
        spec = CommandCheck(cmd=cmd, expect_exit_code=0, timeout_seconds=timeout)
        result = self._verifier._check_command(spec, self.workdir)
        return result.passed

    def command_output_contains(
        self,
        cmd: str,
        expected: str,
        timeout: int = 30,
    ) -> bool:
        """Check if command output contains expected string.

        Args:
            cmd: Command to run
            expected: Expected string in stdout
            timeout: Timeout in seconds

        Returns:
            True if stdout contains expected string
        """
        spec = CommandCheck(
            cmd=cmd,
            expect_exit_code=0,
            expect_stdout_contains=expected,
            timeout_seconds=timeout,
        )
        result = self._verifier._check_command(spec, self.workdir)
        return result.passed

    def file_exists(self, path: str) -> bool:
        """Check if file exists.

        Args:
            path: Relative path to file

        Returns:
            True if file exists
        """
        return (self.workdir / path).exists()

    def file_contains(self, path: str, content: str) -> bool:
        """Check if file contains string.

        Args:
            path: Relative path to file
            content: Expected content

        Returns:
            True if file exists and contains content
        """
        spec = FileCheck(path=path, exists=True, contains=content)
        result = self._verifier._check_file(spec, self.workdir)
        return result.passed

    def tests_pass(self, framework: str = "auto") -> bool:
        """Check if tests pass.

        Args:
            framework: Test framework (auto, pytest, npm, etc.)

        Returns:
            True if tests pass
        """
        if framework == "auto":
            framework = self._detect_test_framework()

        if framework == "pytest":
            return self.command_succeeds("python3 -m pytest", timeout=120)
        elif framework == "npm":
            return self.command_succeeds("npm test", timeout=120)
        elif framework == "jest":
            return self.command_succeeds("npx jest", timeout=120)
        else:
            logger.warning(f"Unknown test framework: {framework}")
            return False

    def _detect_test_framework(self) -> str:
        """Auto-detect test framework.

        Returns:
            Detected framework name
        """
        if (self.workdir / "pytest.ini").exists():
            return "pytest"
        if (self.workdir / "pyproject.toml").exists():
            content = (self.workdir / "pyproject.toml").read_text()
            if "pytest" in content:
                return "pytest"
        if (self.workdir / "package.json").exists():
            return "npm"
        if (self.workdir / "jest.config.js").exists():
            return "jest"

        # Default to pytest for Python projects
        if list(self.workdir.glob("**/*.py")):
            return "pytest"

        return "unknown"
