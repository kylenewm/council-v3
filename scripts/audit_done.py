#!/usr/bin/env python3
"""
audit_done.py - Audit DONE_REPORT claims against actual transcript evidence

Reads Claude Code JSONL transcripts and verifies that DONE_REPORT claims
match actual tool outputs. Catches lies like "tests passed" when Bash shows failures.

Usage:
    python scripts/audit_done.py --transcript ~/.claude/projects/.../session.jsonl
    python scripts/audit_done.py --transcript session.jsonl --json
    python scripts/audit_done.py --transcript session.jsonl --last-n 100  # Only check last N entries
"""

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Dict, Any


@dataclass
class Issue:
    category: str  # "TEST_MISMATCH", "FILES_MISMATCH", "INVARIANTS_MISMATCH", "NO_DONE_REPORT"
    description: str
    claimed: Optional[str] = None
    actual: Optional[str] = None


@dataclass
class AuditResult:
    status: str  # "VERIFIED", "DISCREPANCY", "NO_DONE_REPORT"
    issues: List[Issue] = field(default_factory=list)
    done_report: Optional[str] = None
    bash_outputs: List[Dict[str, str]] = field(default_factory=list)

    @property
    def output(self) -> str:
        lines = []
        if self.status == "VERIFIED":
            lines.append("✅ DONE_REPORT verified")
            lines.append(f"   Checked {len(self.bash_outputs)} bash outputs")
        elif self.status == "NO_DONE_REPORT":
            lines.append("⚠️  No DONE_REPORT found in transcript")
        else:
            lines.append("❌ DONE_REPORT discrepancies found:")
            for issue in self.issues:
                lines.append(f"   ❌ {issue.category}: {issue.description}")
                if issue.claimed:
                    lines.append(f"      claimed: {issue.claimed[:100]}...")
                if issue.actual:
                    lines.append(f"      actual: {issue.actual[:100]}...")
        return "\n".join(lines)


def parse_transcript(path: Path, last_n: Optional[int] = None) -> List[Dict[str, Any]]:
    """Parse JSONL transcript file."""
    entries = []
    with open(path, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                entries.append(entry)
            except json.JSONDecodeError:
                continue

    if last_n and last_n > 0:
        entries = entries[-last_n:]

    return entries


def extract_bash_outputs(entries: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    """Extract Bash tool calls and their results from transcript."""
    bash_outputs = []

    # Build a map of tool_use_id -> command
    tool_calls = {}
    for entry in entries:
        if entry.get("type") != "assistant":
            continue
        message = entry.get("message", {})
        content = message.get("content", [])
        for item in content:
            if isinstance(item, dict) and item.get("type") == "tool_use":
                if item.get("name") == "Bash":
                    tool_id = item.get("id")
                    command = item.get("input", {}).get("command", "")
                    tool_calls[tool_id] = command

    # Now find corresponding results
    for entry in entries:
        if entry.get("type") != "user":
            continue
        message = entry.get("message", {})
        content = message.get("content", [])
        for item in content:
            if isinstance(item, dict) and item.get("type") == "tool_result":
                tool_id = item.get("tool_use_id")
                if tool_id in tool_calls:
                    bash_outputs.append({
                        "command": tool_calls[tool_id],
                        "output": item.get("content", "")
                    })

    return bash_outputs


def find_done_report(entries: List[Dict[str, Any]]) -> Optional[str]:
    """Find the last DONE_REPORT in assistant messages."""
    done_report = None

    for entry in reversed(entries):
        if entry.get("type") != "assistant":
            continue
        message = entry.get("message", {})
        content = message.get("content", [])
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                text = item.get("text", "")
                # Look for DONE_REPORT block
                if "DONE_REPORT" in text:
                    # Try to extract the DONE_REPORT section
                    match = re.search(
                        r'DONE_REPORT[:\s]*\n(.*?)(?=\n\n|\n[A-Z]|\Z)',
                        text,
                        re.DOTALL
                    )
                    if match:
                        done_report = match.group(0)
                        return done_report
                    # Fallback: just return the text containing DONE_REPORT
                    done_report = text
                    return done_report

    return done_report


def check_test_claims(done_report: str, bash_outputs: List[Dict[str, str]]) -> List[Issue]:
    """Check if test claims match actual test outputs."""
    issues = []

    # Patterns that indicate test failures
    failure_patterns = [
        r'\d+ failed',
        r'FAILED',
        r'AssertionError',
        r'Error:',
        r'ERRORS?:',
        r'failures?=\d+[1-9]',
        r'exit code [1-9]',
        r'exit status [1-9]',
        r'npm ERR!',
        r'pytest.*failed',
        r'jest.*failed',
    ]

    # Patterns that indicate test success claims in DONE_REPORT
    success_claims = [
        r'test.*pass',
        r'tests?.*passed',
        r'all.*pass',
        r'✅.*test',
        r'test.*✅',
        r'passed',
    ]

    # Check if DONE_REPORT claims tests passed
    report_lower = done_report.lower()
    claims_success = any(re.search(p, report_lower) for p in success_claims)

    if not claims_success:
        return issues  # No test claims to verify

    # Look for test-related bash outputs
    test_outputs = []
    for bash in bash_outputs:
        cmd = bash["command"].lower()
        if any(t in cmd for t in ["test", "pytest", "jest", "npm test", "yarn test", "go test", "cargo test"]):
            test_outputs.append(bash)

    # Check if any test output shows failures
    for test in test_outputs:
        output = test["output"]
        for pattern in failure_patterns:
            if re.search(pattern, output, re.IGNORECASE):
                issues.append(Issue(
                    category="TEST_MISMATCH",
                    description="DONE_REPORT claims tests passed, but transcript shows failures",
                    claimed="tests passed",
                    actual=f"Found '{pattern}' in output of: {test['command'][:50]}"
                ))
                break  # One issue per test command is enough

    return issues


def check_file_claims(done_report: str, bash_outputs: List[Dict[str, str]]) -> List[Issue]:
    """Check if changed_files claim matches git diff outputs."""
    issues = []

    # Extract claimed files from DONE_REPORT
    files_match = re.search(r'changed_files?[:\s]*\[(.*?)\]', done_report, re.DOTALL)
    if not files_match:
        return issues  # No files claim to verify

    claimed_text = files_match.group(1)
    # Parse files from various formats: ["a", "b"] or [a, b] or a, b
    claimed_files = set()
    for f in re.findall(r'["\']?([^,\[\]"\'\s]+)["\']?', claimed_text):
        if f.strip():
            claimed_files.add(f.strip())

    # Find git diff --name-only outputs
    actual_files = set()
    for bash in bash_outputs:
        if "git diff" in bash["command"] and "--name-only" in bash["command"]:
            for line in bash["output"].split("\n"):
                line = line.strip()
                if line and not line.startswith(("diff", "index", "---", "+++")):
                    actual_files.add(line)

    if not actual_files:
        return issues  # No git diff output to compare

    # Check for discrepancies
    if claimed_files and actual_files:
        missing = actual_files - claimed_files
        extra = claimed_files - actual_files
        if missing or extra:
            issues.append(Issue(
                category="FILES_MISMATCH",
                description="changed_files doesn't match actual git diff",
                claimed=str(claimed_files),
                actual=str(actual_files)
            ))

    return issues


def check_invariants_claims(done_report: str, bash_outputs: List[Dict[str, str]]) -> List[Issue]:
    """Check if invariants claim matches check_invariants.py output."""
    issues = []

    # Check if DONE_REPORT claims invariants passed
    if not re.search(r'invariants?[:\s]*(pass|✅|clean|ok)', done_report, re.IGNORECASE):
        return issues  # No invariants claim to verify

    # Find check_invariants.py outputs
    for bash in bash_outputs:
        if "check_invariants" in bash["command"]:
            output = bash["output"]
            # Check for violation indicators
            if any(x in output for x in ["FORBIDDEN", "PROTECTED", "violations found", "❌"]):
                issues.append(Issue(
                    category="INVARIANTS_MISMATCH",
                    description="DONE_REPORT claims invariants passed, but violations were found",
                    claimed="invariants: pass",
                    actual=output[:200]
                ))

    return issues


def audit_transcript(
    transcript_path: Path,
    last_n: Optional[int] = None
) -> AuditResult:
    """Main audit function: check DONE_REPORT against transcript evidence."""
    entries = parse_transcript(transcript_path, last_n)
    bash_outputs = extract_bash_outputs(entries)
    done_report = find_done_report(entries)

    if not done_report:
        return AuditResult(
            status="NO_DONE_REPORT",
            issues=[Issue(
                category="NO_DONE_REPORT",
                description="No DONE_REPORT found in transcript"
            )],
            bash_outputs=bash_outputs
        )

    # Run all checks
    all_issues = []
    all_issues.extend(check_test_claims(done_report, bash_outputs))
    all_issues.extend(check_file_claims(done_report, bash_outputs))
    all_issues.extend(check_invariants_claims(done_report, bash_outputs))

    status = "DISCREPANCY" if all_issues else "VERIFIED"

    return AuditResult(
        status=status,
        issues=all_issues,
        done_report=done_report,
        bash_outputs=bash_outputs
    )


def main():
    parser = argparse.ArgumentParser(
        description="Audit DONE_REPORT claims against transcript evidence"
    )
    parser.add_argument(
        "--transcript",
        required=True,
        help="Path to Claude Code JSONL transcript file"
    )
    parser.add_argument(
        "--last-n",
        type=int,
        help="Only check last N transcript entries (useful for large files)"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON"
    )

    args = parser.parse_args()

    transcript_path = Path(args.transcript)
    if not transcript_path.exists():
        print(f"Error: Transcript file not found: {transcript_path}", file=sys.stderr)
        sys.exit(2)

    result = audit_transcript(transcript_path, args.last_n)

    if args.json:
        output = {
            "status": result.status,
            "issues": [
                {
                    "category": i.category,
                    "description": i.description,
                    "claimed": i.claimed,
                    "actual": i.actual
                }
                for i in result.issues
            ],
            "bash_commands_checked": len(result.bash_outputs),
            "done_report_found": result.done_report is not None
        }
        print(json.dumps(output, indent=2))
    else:
        print(result.output)

    # Exit code: 0 = verified, 1 = discrepancy, 2 = no done report
    if result.status == "VERIFIED":
        sys.exit(0)
    elif result.status == "NO_DONE_REPORT":
        sys.exit(2)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
