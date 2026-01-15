"""
Tests for scripts/audit_done.py

Verifies that the audit script correctly:
- Parses JSONL transcripts
- Extracts DONE_REPORTs
- Catches discrepancies between claims and actual outputs
"""

import sys
from pathlib import Path

# Add scripts to path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from audit_done import (
    audit_transcript,
    parse_transcript,
    extract_bash_outputs,
    find_done_report,
    check_test_claims,
    check_invariants_claims,
)


FIXTURES_DIR = Path(__file__).parent / "fixtures" / "transcripts"


class TestParseTranscript:
    """Test transcript parsing."""

    def test_parse_valid_transcript(self):
        """Should parse a valid JSONL file."""
        entries = parse_transcript(FIXTURES_DIR / "passing_task.jsonl")
        assert len(entries) > 0
        assert any(e.get("type") == "assistant" for e in entries)

    def test_parse_with_last_n(self):
        """Should limit entries with last_n parameter."""
        all_entries = parse_transcript(FIXTURES_DIR / "passing_task.jsonl")
        limited = parse_transcript(FIXTURES_DIR / "passing_task.jsonl", last_n=2)
        assert len(limited) == 2
        assert len(limited) < len(all_entries)


class TestExtractBashOutputs:
    """Test Bash output extraction."""

    def test_extract_bash_commands(self):
        """Should extract Bash tool calls and results."""
        entries = parse_transcript(FIXTURES_DIR / "passing_task.jsonl")
        bash_outputs = extract_bash_outputs(entries)
        assert len(bash_outputs) > 0
        # Should have pytest command
        commands = [b["command"] for b in bash_outputs]
        assert any("pytest" in cmd for cmd in commands)

    def test_extract_matches_command_to_output(self):
        """Should correctly match command to its output."""
        entries = parse_transcript(FIXTURES_DIR / "passing_task.jsonl")
        bash_outputs = extract_bash_outputs(entries)
        for bash in bash_outputs:
            assert "command" in bash
            assert "output" in bash
            assert bash["command"]  # Not empty


class TestFindDoneReport:
    """Test DONE_REPORT extraction."""

    def test_find_done_report_present(self):
        """Should find DONE_REPORT when present."""
        entries = parse_transcript(FIXTURES_DIR / "passing_task.jsonl")
        done_report = find_done_report(entries)
        assert done_report is not None
        assert "DONE_REPORT" in done_report
        assert "changed_files" in done_report

    def test_find_done_report_missing(self):
        """Should return None when no DONE_REPORT."""
        entries = parse_transcript(FIXTURES_DIR / "missing_done_report.jsonl")
        done_report = find_done_report(entries)
        assert done_report is None


class TestCheckTestClaims:
    """Test detection of test result mismatches."""

    def test_catches_lying_about_tests(self):
        """Should catch when claiming tests passed but they failed."""
        entries = parse_transcript(FIXTURES_DIR / "lying_about_tests.jsonl")
        done_report = find_done_report(entries)
        bash_outputs = extract_bash_outputs(entries)

        issues = check_test_claims(done_report, bash_outputs)
        assert len(issues) > 0
        assert issues[0].category == "TEST_MISMATCH"
        assert "test" in issues[0].description.lower()

    def test_passes_honest_report(self):
        """Should not flag issues when claims match reality."""
        entries = parse_transcript(FIXTURES_DIR / "passing_task.jsonl")
        done_report = find_done_report(entries)
        bash_outputs = extract_bash_outputs(entries)

        issues = check_test_claims(done_report, bash_outputs)
        assert len(issues) == 0


class TestCheckInvariantsClaims:
    """Test detection of invariants mismatches."""

    def test_catches_lying_about_invariants(self):
        """Should catch when claiming invariants passed but they failed."""
        entries = parse_transcript(FIXTURES_DIR / "lying_about_invariants.jsonl")
        done_report = find_done_report(entries)
        bash_outputs = extract_bash_outputs(entries)

        issues = check_invariants_claims(done_report, bash_outputs)
        assert len(issues) > 0
        assert issues[0].category == "INVARIANTS_MISMATCH"


class TestAuditTranscript:
    """Test full audit flow."""

    def test_audit_verified_transcript(self):
        """Should return VERIFIED for honest transcript."""
        result = audit_transcript(FIXTURES_DIR / "passing_task.jsonl")
        assert result.status == "VERIFIED"
        assert len(result.issues) == 0

    def test_audit_catches_test_lies(self):
        """Should return DISCREPANCY for lying about tests."""
        result = audit_transcript(FIXTURES_DIR / "lying_about_tests.jsonl")
        assert result.status == "DISCREPANCY"
        assert len(result.issues) > 0
        assert any(i.category == "TEST_MISMATCH" for i in result.issues)

    def test_audit_catches_invariants_lies(self):
        """Should return DISCREPANCY for lying about invariants."""
        result = audit_transcript(FIXTURES_DIR / "lying_about_invariants.jsonl")
        assert result.status == "DISCREPANCY"
        assert any(i.category == "INVARIANTS_MISMATCH" for i in result.issues)

    def test_audit_missing_done_report(self):
        """Should return NO_DONE_REPORT when missing."""
        result = audit_transcript(FIXTURES_DIR / "missing_done_report.jsonl")
        assert result.status == "NO_DONE_REPORT"

    def test_output_format(self):
        """Should produce readable output."""
        result = audit_transcript(FIXTURES_DIR / "passing_task.jsonl")
        output = result.output
        assert "✅" in output or "VERIFIED" in output.upper()
