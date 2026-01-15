"""
Integration tests for Tier-3 enforcement system.

Tests the full flow: invariants check + audit working together.
"""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

# Add scripts to path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from check_invariants import check_invariants
from audit_done import audit_transcript


FIXTURES_DIR = Path(__file__).parent / "fixtures"
SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"


class TestCLIIntegration:
    """Test CLI interfaces work correctly."""

    def test_check_invariants_cli_clean(self):
        """check_invariants.py CLI should exit 0 for clean diff."""
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPTS_DIR / "check_invariants.py"),
                "--diff", "HEAD~1",
                "--invariants", str(FIXTURES_DIR / "repos" / "clean_diff" / ".council" / "invariants.yaml"),
                "--repo", str(FIXTURES_DIR / "repos" / "clean_diff"),
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "No invariant violations" in result.stdout

    def test_check_invariants_cli_forbidden(self):
        """check_invariants.py CLI should exit 1 for forbidden violations."""
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPTS_DIR / "check_invariants.py"),
                "--diff", "HEAD~1",
                "--invariants", str(FIXTURES_DIR / "repos" / "forbidden_touched" / ".council" / "invariants.yaml"),
                "--repo", str(FIXTURES_DIR / "repos" / "forbidden_touched"),
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1
        assert "FORBIDDEN" in result.stdout

    def test_check_invariants_cli_json_output(self):
        """check_invariants.py --json should output valid JSON."""
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPTS_DIR / "check_invariants.py"),
                "--diff", "HEAD~1",
                "--invariants", str(FIXTURES_DIR / "repos" / "clean_diff" / ".council" / "invariants.yaml"),
                "--repo", str(FIXTURES_DIR / "repos" / "clean_diff"),
                "--json",
            ],
            capture_output=True,
            text=True,
        )
        data = json.loads(result.stdout)
        assert "status" in data
        assert data["status"] == "PASS"

    def test_audit_done_cli_verified(self):
        """audit_done.py CLI should exit 0 for verified transcript."""
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPTS_DIR / "audit_done.py"),
                "--transcript", str(FIXTURES_DIR / "transcripts" / "passing_task.jsonl"),
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "verified" in result.stdout.lower()

    def test_audit_done_cli_discrepancy(self):
        """audit_done.py CLI should exit 1 for discrepancies."""
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPTS_DIR / "audit_done.py"),
                "--transcript", str(FIXTURES_DIR / "transcripts" / "lying_about_tests.jsonl"),
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1
        assert "discrepanc" in result.stdout.lower()

    def test_audit_done_cli_json_output(self):
        """audit_done.py --json should output valid JSON."""
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPTS_DIR / "audit_done.py"),
                "--transcript", str(FIXTURES_DIR / "transcripts" / "passing_task.jsonl"),
                "--json",
            ],
            capture_output=True,
            text=True,
        )
        data = json.loads(result.stdout)
        assert "status" in data
        assert data["status"] == "VERIFIED"


class TestEnforcementFlow:
    """Test the combined enforcement flow."""

    def test_both_pass_for_clean_work(self):
        """Both invariants and audit should pass for clean work."""
        # Invariants check
        inv_result = check_invariants(
            invariants_path=FIXTURES_DIR / "repos" / "clean_diff" / ".council" / "invariants.yaml",
            diff_ref="HEAD~1",
            repo_path=FIXTURES_DIR / "repos" / "clean_diff",
        )
        assert inv_result.exit_code == 0

        # Audit check
        audit_result = audit_transcript(FIXTURES_DIR / "transcripts" / "passing_task.jsonl")
        assert audit_result.status == "VERIFIED"

    def test_invariants_blocks_even_with_honest_report(self):
        """Invariants violation should block even if DONE_REPORT is honest."""
        # Invariants should fail
        inv_result = check_invariants(
            invariants_path=FIXTURES_DIR / "repos" / "forbidden_touched" / ".council" / "invariants.yaml",
            diff_ref="HEAD~1",
            repo_path=FIXTURES_DIR / "repos" / "forbidden_touched",
        )
        assert inv_result.exit_code == 1

        # Even if audit passes, invariants failure is blocking
        audit_result = audit_transcript(FIXTURES_DIR / "transcripts" / "passing_task.jsonl")
        # Audit might pass, but overall flow should fail due to invariants

    def test_audit_catches_lies_even_with_clean_invariants(self):
        """Audit should catch lies even if invariants pass."""
        # Invariants pass
        inv_result = check_invariants(
            invariants_path=FIXTURES_DIR / "repos" / "clean_diff" / ".council" / "invariants.yaml",
            diff_ref="HEAD~1",
            repo_path=FIXTURES_DIR / "repos" / "clean_diff",
        )
        assert inv_result.exit_code == 0

        # But audit catches the lie
        audit_result = audit_transcript(FIXTURES_DIR / "transcripts" / "lying_about_tests.jsonl")
        assert audit_result.status == "DISCREPANCY"


class TestHookIntegration:
    """Test hook scripts work correctly."""

    def test_strict_v2_outputs_done_report_format(self):
        """strict_v2.sh should output DONE_REPORT format instructions."""
        hook_path = Path.home() / ".council" / "hooks" / "strict_v2.sh"
        if not hook_path.exists():
            pytest.skip("strict_v2.sh not installed")

        result = subprocess.run(
            ["bash", str(hook_path)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "DONE_REPORT" in result.stdout
        assert "changed_files" in result.stdout
        assert "invariants" in result.stdout

    def test_review_sh_outputs_review_format(self):
        """review.sh should output review mode instructions."""
        hook_path = Path.home() / ".council" / "hooks" / "review.sh"
        if not hook_path.exists():
            pytest.skip("review.sh not installed")

        result = subprocess.run(
            ["bash", str(hook_path)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "REVIEW MODE" in result.stdout
        assert "BLOCKERS" in result.stdout
        assert "VERDICT" in result.stdout

    def test_inject_router_handles_review(self):
        """inject.sh should handle review mode."""
        inject_path = Path.home() / ".council" / "hooks" / "inject.sh"
        mode_file = Path.home() / ".council" / "current_inject.txt"

        if not inject_path.exists():
            pytest.skip("inject.sh not installed")

        # Temporarily set review mode
        original_mode = mode_file.read_text() if mode_file.exists() else None
        try:
            mode_file.write_text("review")
            result = subprocess.run(
                ["bash", str(inject_path)],
                capture_output=True,
                text=True,
            )
            assert "REVIEW MODE" in result.stdout
        finally:
            # Restore original mode
            if original_mode:
                mode_file.write_text(original_mode)
            elif mode_file.exists():
                mode_file.unlink()
