#!/usr/bin/env python3
"""Python file checker hook - runs ruff and basedpyright on edited Python files.

Based on claude-codepro's file_checker_python.py implementation.
PostToolUse hook that auto-formats and checks Python files.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

RED = "\033[0;31m"
GREEN = "\033[0;32m"
NC = "\033[0m"


def find_git_root() -> Path | None:
    """Find git repository root."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            return Path(result.stdout.strip())
    except Exception:
        pass
    return None


def auto_format(file_path: Path) -> None:
    """Auto-format file with ruff/black before checks."""
    # Try ruff first (preferred)
    ruff_bin = shutil.which("ruff")
    if ruff_bin:
        try:
            # Fix imports
            subprocess.run(
                [ruff_bin, "check", "--select", "I,RUF022", "--fix", str(file_path)],
                capture_output=True,
                check=False,
            )
            # Format
            subprocess.run(
                [ruff_bin, "format", str(file_path)],
                capture_output=True,
                check=False,
            )
            return
        except Exception:
            pass

    # Fall back to black
    black_bin = shutil.which("black")
    if black_bin:
        try:
            subprocess.run(
                [black_bin, str(file_path)],
                capture_output=True,
                check=False,
            )
        except Exception:
            pass


def run_ruff_check(file_path: Path) -> tuple[bool, str]:
    """Run ruff check."""
    ruff_bin = shutil.which("ruff")
    if not ruff_bin:
        return False, ""

    try:
        result = subprocess.run(
            [ruff_bin, "check", str(file_path)],
            capture_output=True,
            text=True,
            check=False,
        )
        output = result.stdout + result.stderr
        has_issues = bool(output and "All checks passed" not in output)
        return has_issues, output
    except Exception:
        return False, ""


def run_basedpyright_check(file_path: Path) -> tuple[bool, str]:
    """Run basedpyright check."""
    basedpyright_bin = shutil.which("basedpyright")
    if not basedpyright_bin:
        # Try pyright as fallback
        basedpyright_bin = shutil.which("pyright")
    if not basedpyright_bin:
        return False, ""

    try:
        result = subprocess.run(
            [basedpyright_bin, "--outputjson", str(file_path.resolve())],
            capture_output=True,
            text=True,
            check=False,
        )
        output = result.stdout + result.stderr
        try:
            data = json.loads(output)
            error_count = data.get("summary", {}).get("errorCount", 0)
            has_issues = error_count > 0
            return has_issues, output
        except json.JSONDecodeError:
            has_issues = bool('error"' in output or " error" in output)
            return has_issues, output
    except Exception:
        return False, ""


def display_ruff_result(output: str) -> None:
    """Display ruff results."""
    lines = output.splitlines()
    error_lines = [
        line for line in lines if line and line[0] in "FEWCB" and ":" in line
    ]
    error_count = len(error_lines)
    plural = "issue" if error_count == 1 else "issues"

    print("", file=sys.stderr)
    print(f"Ruff: {error_count} {plural}", file=sys.stderr)
    print("-------------------------------------------", file=sys.stderr)

    for line in error_lines[:10]:  # Limit output
        print(f"  {line}", file=sys.stderr)

    if len(error_lines) > 10:
        print(f"  ... and {len(error_lines) - 10} more", file=sys.stderr)

    print("", file=sys.stderr)


def display_basedpyright_result(output: str) -> None:
    """Display basedpyright results."""
    try:
        data = json.loads(output)
        error_count = data.get("summary", {}).get("errorCount", 0)
        plural = "issue" if error_count == 1 else "issues"

        print("", file=sys.stderr)
        print(f"Pyright: {error_count} {plural}", file=sys.stderr)
        print("-------------------------------------------", file=sys.stderr)

        for diag in data.get("generalDiagnostics", [])[:10]:  # Limit output
            file_name = Path(diag.get("file", "")).name
            line = diag.get("range", {}).get("start", {}).get("line", 0)
            msg = diag.get("message", "").split("\n")[0]
            print(f"  {file_name}:{line} - {msg}", file=sys.stderr)

        total = len(data.get("generalDiagnostics", []))
        if total > 10:
            print(f"  ... and {total - 10} more", file=sys.stderr)

    except json.JSONDecodeError:
        print("", file=sys.stderr)
        print("Pyright: issues found", file=sys.stderr)
        print("-------------------------------------------", file=sys.stderr)
        print(output[:500], file=sys.stderr)  # Limit raw output

    print("", file=sys.stderr)


def get_edited_file_from_stdin() -> Path | None:
    """Get the edited file path from PostToolUse hook stdin."""
    try:
        import select

        if select.select([sys.stdin], [], [], 0)[0]:
            data = json.load(sys.stdin)
            tool_input = data.get("tool_input", {})
            file_path = tool_input.get("file_path")
            if file_path:
                return Path(file_path)
    except Exception:
        pass
    return None


def main() -> int:
    """Main entry point."""
    git_root = find_git_root()
    if git_root:
        os.chdir(git_root)

    target_file = get_edited_file_from_stdin()
    if not target_file or not target_file.exists():
        return 0

    if target_file.suffix != ".py":
        return 0

    # Skip test files (optional - can remove if you want checks on tests too)
    if "test" in target_file.name or "spec" in target_file.name:
        return 0

    has_ruff = shutil.which("ruff") is not None
    has_basedpyright = shutil.which("basedpyright") is not None or shutil.which("pyright") is not None

    if not (has_ruff or has_basedpyright):
        return 0

    # Auto-format first
    auto_format(target_file)

    results = {}
    has_issues = False

    if has_ruff:
        ruff_issues, ruff_output = run_ruff_check(target_file)
        if ruff_issues:
            has_issues = True
            results["ruff"] = ruff_output

    if has_basedpyright:
        pyright_issues, pyright_output = run_basedpyright_check(target_file)
        if pyright_issues:
            has_issues = True
            results["basedpyright"] = pyright_output

    if has_issues:
        print("", file=sys.stderr)
        try:
            rel_path = target_file.relative_to(Path.cwd())
        except ValueError:
            rel_path = target_file
        print(
            f"{RED}Python Issues in: {rel_path}{NC}",
            file=sys.stderr,
        )

        if "ruff" in results:
            display_ruff_result(results["ruff"])

        if "basedpyright" in results:
            display_basedpyright_result(results["basedpyright"])

        print(f"{RED}Fix Python issues above before continuing{NC}", file=sys.stderr)
        return 2
    else:
        print("", file=sys.stderr)
        print(f"{GREEN}Python: All checks passed{NC}", file=sys.stderr)
        return 0


if __name__ == "__main__":
    sys.exit(main())
